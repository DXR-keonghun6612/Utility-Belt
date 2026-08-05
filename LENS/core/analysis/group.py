"""가르기 오케스트레이션 — **도메인 단위**로 움직인다. 정본을 안 읽는다.

계산은 :func:`~.cluster.fit` 이 다 하고 여기는 배선만 든다: 어느 도메인이 낡았나 → 필요한 잣대
좌표를 **한 번의 순회로** 모아(:func:`_load`) → 도메인마다 ``fit`` → 배정과 통계를 store 에 앉힌다.

**적재 축과 가르기 축이 다르다.** 파일은 저장 feature 단위인데 가르기는 잣대 단위라, 잣대마다
따로 적재하면 같은 파일을 잣대 수만큼 다시 읽는다. 그래서 적재는 한 번이고 그 산출을 축 루프와
종합이 나눠 쓴다.

옛 구현은 class 단위였다(``members_by_class`` 로 묶어 class 마다 ``split_class``). class 가 배정에
안 들어가면서 그 축이 통째로 사라졌고, 대신 **도메인**이 단위가 됐다 — 도메인끼리 직교라 하나를
다시 갈라도 나머지는 안 건드린다.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from .cluster import (
    JOINT, POOL, centers, components, equalize, fit, gauge_params, impute, join, knn,
    NORM_EQUALIZE, NORM_FLOOR, NORM_FLOOR_Q, NORM_NONE, members_of, merge_totals, neighbors_of,
    norm_from_totals, normalize_of, stats_of, threshold_of, totals_of, type_neighbors, welds_of)
from . import cache
from .extract import Fold
from .store import Cluster_Bucket

Progress = Callable[[str, int, int], None] | None


def domain_signature(keys: list[str], signs: dict, params: dict, domain: str) -> str:
    """한 도메인의 **입력 서명** — 이게 그대로면 다시 가를 이유가 없다.

    구성원 명단만으로는 부족하다: 같은 표본 집합이어도 **내용이 편집되면**(mask 수정 → feature
    변경) 중심이 거짓이 된다. 그래서 명단에 표본별 sign 을 함께 엮는다.

    설정 쪽은 **그 도메인 값만** 넣는다(:func:`~.cluster.gauge_params`) — 남의 도메인 값을 바꿨다고
    이 도메인을 다시 가를 이유가 없다. 한때 ``min_members`` 만 전역이라, 그 하나를 만지면 안 건드린
    게이지까지 전부 다시 돌았다.

    **class 는 안 들어간다.** class 는 obj 에 붙은 정보라 배정에 영향을 주지 않으므로, 라벨을
    고쳐도 재군집이 일어나지 않는다.
    """
    _doc = {"members": sorted([[_k, str(signs.get(_k, ""))] for _k in keys]),
            **gauge_params(params, domain)}
    return hashlib.blake2b(
        json.dumps(_doc, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=5).hexdigest()


def build(bucket: Cluster_Bucket, params: dict, *, domains: list[str] | None = None,
          progress: Progress = None) -> list[str]:
    """**바뀐 도메인만** 다시 가른다.

    축을 다 돈 뒤 **종합 판정**을 한 번 더 낸다(:data:`~.cluster.JOINT`) — 켠 축들의 곱집합이다.
    축 하나만 다시 갈려도 곱이 달라지므로 종합은 증분이 없다. 값이 이미 index 에 있어 싸다.

    Args:
        bucket: 산출물 store.
        params: ``threshold``·``thresholds``·``neighbors``·``neighbor_counts``·``min_members``.
        domains: 가를 도메인 (None = 계약 전부). 뺀 도메인은 **서명과 무관**하므로 나중에 다시
            넣으면 그때 돈다 — 비용이 채널 수에 비례해(``radial_outline`` 512 vs scalar 다섯 합쳐
            23) 안 볼 도메인을 빼 두는 것이 실제로 의미가 있다. **종합도 켠 축만 곱한다.**
        progress: ``(라벨, 한 것, 전체)``.

    Returns:
        다시 가른 도메인 목록 (종합을 냈으면 :data:`~.cluster.JOINT` 포함).
    """
    _index = bucket.Index()
    _keys = sorted(_index)
    _signs = {_k: _r.get("sign", "") for _k, _r in _index.items()}
    _cfg = bucket.Cluster_cfg()
    _known = dict(_cfg.get("signatures") or {})
    _all = bucket.Domains()
    _domains = [_d for _d in _all if domains is None or _d in set(domains)]
    _ensure_norm(bucket, _domains, _keys, params, progress)
    _norm = _norms(bucket, params)

    _todo = []
    for _d in _domains:
        _sig = domain_signature(_keys, _signs, params, _d)
        if _known.get(_d) != _sig:
            _todo.append((_d, _sig))

    for _d in [_d for _d in _known if _d not in _all and _d != JOINT]:   # 계약에서 빠진 도메인
        _known.pop(_d, None)
        bucket.Drop_stats(_d)

    # **설정은 가르기와 무관하게 먼저 쓴다.** 이 한 장에는 가르는 값만이 아니라 화면이 읽는 값
    # (``max_axis_types``)도 산다. 그런 값은 일부러 서명에 안 넣어 재군집을 안 부르는데, 그러다 보니
    # 그것만 바꾸면 ``_todo`` 가 비어 아래 루프가 안 돌고 **설정이 디스크에 닿지 못했다** — 화면은
    # 계속 옛 값으로 판단했다. 쓰기는 가르기의 부산물이 아니다.
    bucket.Set_cluster_cfg({**dict(params), "signatures": _known})

    # **적재는 한 번이다.** 축 루프와 종합이 같은 좌표를 쓰고, 한 사이드카에서 모든 잣대가 나온다
    # (:func:`_load`). 종합이 돌 것 같으면 그 축들도 미리 함께 싣는다 — 아래에서 서명을 다시
    # 확인해 정말 필요할 때만 쓰고, 모자라면 그때 채운다.
    _axes = [_d for _d in _domains if _d != JOINT]
    _ahead = {_d: dict(_todo).get(_d, _known.get(_d, "")) for _d in _axes}
    _want = {_d for _d, _ in _todo}
    if len(_axes) >= 2 and _known.get(JOINT) != joint_signature(params, _ahead):
        _want |= set(_axes)
    _coords = _load(bucket, sorted(_want), _keys, _norm, progress) if _want else {}

    for _i, (_dom, _sig) in enumerate(_todo, 1):
        _X, _used = _coords.get(_dom, _EMPTY)
        if not len(_used):
            continue
        _lab, _dist, _stats, _ = fit(
            _X, threshold_of(params, _dom), members_of(params, _dom),
            neighbors=neighbors_of(params, _dom),
            progress=(lambda _t, _a, _b, _d=_dom: progress(f"[{_d}] {_t}", _a, _b))
            if progress is not None else None)
        bucket.Set_stats(_dom, _stats)
        bucket.Set_assignment(_dom, dict(zip(_used, _lab.tolist())),
                              dict(zip(_used, _dist.tolist())))
        _known[_dom] = _sig
        # **도메인마다 함께 쓴다** — 통계만 새것이고 index 가 옛것으로 남으면 배정과 구조가 어긋난다.
        bucket.Set_cluster_cfg({**dict(params), "signatures": _known})
        if progress is not None:
            progress(f"가르기 ({len(_todo)} 도메인)", _i, len(_todo))

    # **종합 서명 = 축 서명들 + 종합 자기 설정.** 축 label 을 통째로 해싱하면 6만×축 을 매번 도는데,
    # 축이 안 바뀌면 label 도 안 바뀌므로 축 서명이 그 사실을 이미 답한다.
    _sig = joint_signature(params, {_d: _known.get(_d, "") for _d in _axes})
    _ran = False
    if _known.get(JOINT) != _sig and len(_axes) >= 2:
        _late = [_d for _d in _axes if _d not in _coords]   # 위 예측이 빗나갔으면 그때 채운다
        if _late:
            _coords.update(_load(bucket, _late, _keys, _norm, progress))
        _build_joint(bucket, params, _axes, _keys, _coords, progress)
        _known[JOINT] = _sig
        bucket.Set_cluster_cfg({**dict(params), "signatures": _known})
        _ran = True
    elif len(_axes) < 2:
        bucket.Set_joint(_axes, [], {}, {})            # 축이 하나면 종합은 그 축과 같다
        _known.pop(JOINT, None)
    if not _todo and not _ran and progress is not None:
        progress("바뀐 것 없음 — 저장분 사용", 0, 0)
    return [_d for _d, _ in _todo] + ([JOINT] if _ran else [])


def joint_signature(params: dict, axis_signatures: dict[str, str]) -> str:
    """종합의 입력 서명 — **축 서명들 + 종합 자기 설정**(메우기 한계·병합 여부).

    축이 안 바뀌면 label 도 안 바뀌므로 축 서명이 그 사실을 대신 답한다. label 배열을 통째로
    해싱하던 자리인데, 6만×축 을 매번 도는 비용이 얻는 것에 비해 컸다.
    """
    return hashlib.blake2b(
        json.dumps({"axes": dict(sorted(axis_signatures.items())),
                    "bound": float(params.get("impute_bound", 0.3)),
                    # 축마다 다르므로 **켠 축의 목록**을 해싱한다 — 전역 bool 만 보면 한 축의
                    # 병합을 꺼도 종합이 안 다시 돈다.
                    "weld": sorted(_d for _d in axis_signatures if welds_of(params, _d))},
                   sort_keys=True).encode("utf-8"), digest_size=5).hexdigest()


def _build_joint(bucket: Cluster_Bucket, params: dict, domains: list[str], keys: list[str],
                 coords: dict[str, tuple[np.ndarray, list[str]]], progress: Progress) -> None:
    """켠 축들을 합쳐 종합 자리에 앉힌다.

    두 걸음이다::

        ① impute   기권한 축을 **다른 축을 참고해** 메운다 (:func:`~.cluster.impute`)
        ② join     메운 label 로 조합을 만들고(쪼갬), **자의적인 경계는 도로 붙인다**(병합)

    ①이 좌표를 쓰므로 ``coords`` 를 받는다 — 호출 측이 축 루프에서 이미 실은 것을 그대로 넘긴다
    (여기서 다시 실으면 전수를 축 수만큼 또 읽는다).

    **종합은 자기 장부에 앉는다** — ``index.types`` 에 안 섞는다. 거기 있는 것은 잣대가 문턱을 넘어
    인정한 값이고, 메운 자리는 추정이라 수명도 뜻도 다르다.

    호출 측이 **낼지 말지를 이미 정한다** — 여기는 내는 일만 한다.

    Args:
        bucket: 산출물 store.
        params: 묶기 설정 (``impute_bound`` · ``weld_types`` · 축별 ``k``·이웃 수).
        domains: 곱할 축 이름.
        keys: 표본 key — ``labels`` 의 자리 순서를 정한다.
        coords: :func:`_load` 의 산출 ``{도메인: ((n, D), 쓴 키)}``. 키가 ``keys`` 전부가 아닌
            축은 메우기에서 빠진다(자리가 안 맞으면 거리를 엉뚱한 표본에 붙인다).
        progress: ``(라벨, 한 것, 전체)``.
    """
    _use = list(domains)
    _index = bucket.Index()
    _labels = {_d: np.asarray([int((_index.get(_k, {}).get("types") or {}).get(_d, POOL))
                              for _k in keys]) for _d in _use}

    _coords, _centers = {}, {}
    for _d in _use:
        _X, _used = coords.get(_d, _EMPTY)
        if len(_used) == len(keys):
            _coords[_d] = _X
        _centers[_d] = bucket.Centers(_d)
    _bound = float(params.get("impute_bound", 0.3))
    _filled: dict[str, list[int]] = {}
    if _bound > 0 and _coords:
        _labels, _filled = impute(_labels, _coords, _centers, _bound)

    # **축마다 켜고 끈다.** 빠진 축은 `_merge_cells` 에서 "같을 때만" 붙으므로 그 축이 가른 것이
    # 지켜진다 — 실루엣은 경계가 흔들려 붙일 값어치가 있지만 구멍이 가른 것은 지켜야 한다
    # (:func:`~.cluster.welds_of` 의 실측표).
    _edges = {_d: type_neighbors(bucket.Centers(_d), threshold_of(params, _d),
                                 neighbors_of(params, _d))
              for _d in _use if welds_of(params, _d)} or None
    _lab, _members = join(_labels, _edges)
    _assign = {_k: int(_t) for _k, _t in zip(keys, _lab.tolist()) if _t >= 0}
    _imputed: dict[str, dict[str, int]] = {}
    for _d, _rows in _filled.items():
        for _i in _rows:
            _imputed.setdefault(keys[_i], {})[_d] = int(_labels[_d][_i])
    bucket.Set_joint(_use, _members, _assign, _imputed)
    if progress is not None:
        progress(f"종합 (축 {len(_use)} · type {len(_members)} · 메움 "
                 f"{sum(len(_v) for _v in _filled.values())})", 1, 1)



def _ensure_norm(bucket: Cluster_Bucket, domains: list[str], keys: list[str], params: dict,
                 progress: Progress) -> dict:
    """정규화 상수가 **없는 도메인만** 채운다 — 재추출 없이.

    ``norm`` 은 잣대 좌표의 값이라 잣대를 바꾸면 낡는다. 그런데 쓰는 자리가 추출뿐이라, config 에
    축을 더하면 상수가 안 생기고 :func:`~.cluster.equalize` 가 원 단위로 통과시킨다 — 그러면 ``k``
    가 σ 가 아니라 px 를 재게 되어 **아무도 안 붙는다**(실측 64,336건 100% 미배정).

    모델은 안 태운다. 저장된 feature 를 접기만 하면 되므로 사이드카 읽기 한 바퀴다 — 그 한 바퀴는
    :func:`_folded` 가 적재와 **같은 경로**로 돈다. 다만 표준화는 못 한다(그 상수를 지금 구하는
    중이라) — 접은 값을 그대로 누적한다.
    """
    _norm = dict(bucket.Norm())
    # `equalize` 를 쓰는 축만 잰다 — `none`·`floor` 는 mean/std 를 안 본다(한 바퀴가 공짜가 아니다).
    _missing = [_d for _d in domains
                if _d not in _norm and _d != JOINT and normalize_of(params, _d) == NORM_EQUALIZE]
    if not _missing:
        return _norm
    _totals = [totals_of({_d: _v for _d, (_v, _) in _chunk.items()})
               for _chunk in _folded(bucket, _lens(bucket, _missing), keys, progress, "정규화 상수")]
    if not _totals:
        return _norm
    _norm.update(norm_from_totals([merge_totals(_totals)]))
    bucket.Set_norm(_norm)
    return _norm


#: 접기를 한 번에 태울 표본 수 — 버퍼는 원본 feature 라 ``radial_rle (512, 8)`` 기준 16 MB 다.
_CHUNK = 1024

#: 좌표가 없을 때 내는 빈 자리 ``(빈 배열, 빈 키)`` — **읽기 전용**. ``.get()`` 의 기본값으로만 쓴다.
_EMPTY: tuple[np.ndarray, list[str]] = (np.zeros((0, 0), np.float32), [])


def _norms(bucket: Cluster_Bucket, params: dict) -> dict[str, dict]:
    """도메인별 정규화 상수에 **이번에 쓸 방법**을 얹는다 — :func:`~.cluster.equalize` 가 이 dict 만 본다.

    방법을 인자로 따로 흘리지 않는 이유는 소비처가 넷(:func:`_load`·:func:`pool_groups`·
    :func:`propagate`·화면)이라서다 — 상수와 방법이 갈라져 다니면 한쪽만 넘기는 자리가 생긴다.
    """
    _n = dict(bucket.Norm())
    return {_d: {**dict(_n.get(_d) or {}), "method": normalize_of(params, _d)}
            for _d in set(_n) | set(bucket.Gauges())}


def _scaled(bucket: Cluster_Bucket, domain: str, X: np.ndarray, norm_d: dict) -> np.ndarray:
    """축척을 맞춘 좌표. **최근접거리 분포를 같이 재서** ``norm`` 에 남긴다 — 없을 때 한 번만.

    한 번의 ``knn(X, 1)`` 이 둘을 다 낸다:

    - ``floor`` — 그 분포의 하위 분위수(:data:`~.cluster.NORM_FLOOR_Q`). 축척이 된다.
    - ``nn`` — **최종 좌표 단위**의 ``[10%, 50%, 90%]``. ``k`` 추천의 근거다
      (:meth:`~.store.Cluster_Bucket.Suggest_k`) — 표본이 이웃 하나라도 가지려면 ``k`` 가 자기
      최근접거리를 넘어야 하므로, ``k = q90`` 이면 표본의 90% 가 최소한 하나와 이어진다.

    바닥은 ``1/√dim`` 까지 적용된 좌표에서 잰다. 나눗셈이라 순서는 상관없지만(``x/floor/√D`` ==
    ``x/√D/floor``) 재는 쪽과 쓰는 쪽의 단위가 같아야 ``k`` 가 "바닥의 몇 배" 로 읽힌다.
    """
    _n = dict(norm_d or {})
    _need = (_n.get("method") == NORM_FLOOR and not _n.get("floor")) or not _n.get("nn")
    if _need and len(X) > 1:
        _raw = equalize(X, {"method": NORM_NONE})            # /√D 만 — 원 단위
        _d1 = knn(_raw, 1)[0][:, 0]
        if _n.get("method") == NORM_FLOOR and not _n.get("floor"):
            _n["floor"] = max(float(np.quantile(_d1, NORM_FLOOR_Q)), 1e-6)
        # 최종 좌표는 원 좌표를 상수로 나눈 것이라 최근접거리도 같은 상수로 나뉜다.
        _by = (float(_n["std"]) if _n.get("method") == NORM_EQUALIZE and "std" in _n
               else float(_n["floor"]) if _n.get("method") == NORM_FLOOR else 1.0)
        _n["nn"] = [float(_q) for _q in np.quantile(_d1 / max(_by, 1e-12), (0.1, 0.5, 0.9))]
        _all = dict(bucket.Norm())
        _all.setdefault(str(domain), {}).update(
            {_k: _n[_k] for _k in ("floor", "nn") if _k in _n})
        bucket.Set_norm(_all)
    return equalize(X, _n).astype(np.float32)


def _lens(bucket: Cluster_Bucket, domains) -> dict[str, tuple[str, tuple[str, ...]]]:
    """요청한 이름 중 **계약에 있는** 잣대만 ``{도메인: (원본 feature, 접기)}``."""
    _g = bucket.Gauges()
    return {_d: _g[_d] for _d in domains if _d in _g}


def _folded(bucket: Cluster_Bucket, lens: dict, keys: list[str], progress: Progress = None,
            label: str = "적재"):
    """저장된 값을 **묶음마다 한 번씩** 읽어 잣대별로 접는다 — ``{도메인: (접힌 배치, 그 키들)}``.

    **묶음을 전부 연다.** 어느 묶음에 무엇이 들었는지는 npz 가 답하지 index 가 답하지 않는다 —
    index 의 class 로 열 묶음을 고르면 라벨을 고치는 순간 읽히는 표본이 달라지고, 그러면 **class 가
    군집 입력이 된다**(형상만 봐야 하는 자리다).

    한 번 읽으면 그 표본의 **모든 잣대**가 나온다 — ``signed`` 와 ``outline`` 은 같은 ``radial_rle``
    에서 접힌다. 접기는 묶음을 통째로 태운다(표본마다 torch 를 왕복하면 접기가 적재보다 비싸진다).

    Args:
        bucket: 표본 store.
        lens: :func:`_lens` 의 산출 ``{도메인: (feature, 접기)}``.
        keys: 쓸 item key — 이 중 캐시에 있는 것만 나온다.
        progress: ``(라벨, 한 것, 전체)``.
        label: 진행 라벨의 머리말.

    Yields:
        ``{도메인: ((m, …) 접힌 값, [그 m 개의 키])}``.
    """
    if not lens:
        return
    _want = set(keys)
    _groups = cache.Groups(bucket, cache.CLASS)
    _label = f"{label} ({' · '.join(lens)})"
    for _i, _g in enumerate(_groups, 1):
        _got = cache.Load(bucket, cache.CLASS, _g)
        if progress is not None:
            progress(_label, _i, len(_groups))
        if _got is None:
            continue
        _ks, _rows = _got
        _take = [_j for _j, _k in enumerate(_ks) if _k in _want]
        if not _take:
            continue
        _rows, _use = _rows[_take], [_ks[_j] for _j in _take]
        yield {_d: (Fold(_folds, _rows, batched=True), _use)
               for _d, (_, _folds) in lens.items()}


def _load(bucket: Cluster_Bucket, domains: list[str], keys: list[str], norm: dict,
          progress: Progress = None) -> dict[str, tuple[np.ndarray, list[str]]]:
    """잣대들을 **한 번의 순회로** 표준화 좌표에 쌓는다 — ``{도메인: ((n, D) float32, 쓴 키)}``.

    값을 못 읽은 표본은 **그 잣대의 키 목록에서도 뺀다**. 배열만 짧아지면 뒤이은
    ``zip(used, lab)`` 이 배정을 엉뚱한 표본에 붙인다 — 조용히 어긋나는 자리라 둘을 함께 낸다.
    빠지는 표본이 잣대마다 다를 수 있어 키 목록도 잣대마다다.

    Args:
        bucket: 표본 store.
        domains: 쌓을 잣대 이름들. 계약에 없는 이름은 결과에 안 담는다.
        keys: 순회할 item key — 결과의 순서가 이걸 따른다.
        norm: ``{도메인: {mean, std}}`` (:meth:`~.store.Cluster_Bucket.Norm`).
        progress: ``(라벨, 한 것, 전체)``.

    Returns:
        ``{도메인: ((n, D) 좌표, 그 순서의 키)}``.
    """
    _lens_d = _lens(bucket, domains)
    _out: dict[str, list[np.ndarray]] = {_d: [] for _d in _lens_d}
    _used: dict[str, list[str]] = {_d: [] for _d in _lens_d}
    for _chunk in _folded(bucket, _lens_d, keys, progress):
        for _d, (_v, _ks) in _chunk.items():
            _out[_d].append(np.asarray(_v, np.float32).reshape(len(_ks), -1))
            _used[_d] += _ks
    # **축척은 마지막에 한 번** — `floor` 는 그 축의 전수를 봐야 잴 수 있다(청크마다 재면 값이 다르다).
    return {_d: (_scaled(bucket, _d, np.concatenate(_out[_d]), norm.get(_d, {}))
                 if _out[_d] else _EMPTY[0], _used[_d])
            for _d in _lens_d}


def pool_groups(bucket: Cluster_Bucket, domain: str,
                progress: Progress = None) -> list[list[str]]:
    """보류(:data:`POOL`)를 **최근접 이웃으로** 이어 하위 무리로 나눈다 — 크기 내림차순 key 목록들.

    보류는 "어디에도 안 붙은 것"이라 한 덩어리로 쌓이는데, 그 안에 서로 닮은 것들이 섞여 있어도
    목록에서는 안 보인다. 여기서 그것만 드러낸다.

    **type 을 만들지 않는다.** 결과를 저장하지도, ``index`` 에 배정하지도 않는다 — 보류는 이 데이터로
    가를 근거가 부족하다는 판정이고 그 판정은 그대로 남아야 한다. 이건 **보기 정리**이지 배정이 아니다.
    (같은 이유로 보류를 가장 가까운 type 에 흡수시키지도 않는다 — 그 소속은 데이터가 지지하지 않는다.)

    **상호성을 안 따진다** — 각 표본을 자기 최근접 이웃과 잇고 연결 성분을 센다. 보류는 애초에
    ``mutual_edges`` 의 문턱을 못 넘어 온 것들이라 상호성을 다시 요구하면 대부분 혼자 남는다. 대신
    사슬로 이어지므로(A→B, B→C 면 셋이 한 무리) 무리가 헐겁다 — 판정이 아니라 훑어보기용이라는 뜻이다.

    Args:
        bucket:  표본 store.
        domain:  잣대 이름 (종합 ``JOINT`` 은 좌표가 없어 빈 목록).
        progress: 좌표 적재 진행 콜백.

    Returns:
        무리마다 key 목록 (큰 것부터). 보류가 1건 이하면 그것만 담은 목록 하나.
    """
    if str(domain) == JOINT:                      # 종합엔 좌표가 없다 — 이웃을 잴 것이 없다
        return []
    _keys = bucket.Keys(domain, POOL)
    if len(_keys) < 2:
        return [[_k] for _k in _keys]
    _X, _used = _load(bucket, [domain], _keys, _norms(bucket, bucket.Cluster_cfg()),
                      progress).get(domain, _EMPTY)
    if len(_used) < 2:
        return [[_k] for _k in _used]
    _, _idx = knn(_X, 1)                          # 각자의 최근접 하나 — 그것이 곧 간선이다
    _edges = np.stack([np.arange(len(_used)), _idx[:, 0].astype(int)], 1)
    _lab = components(len(_used), _edges, 1)      # min_members=1 — 아무도 안 떨어뜨린다
    _out: dict[int, list[str]] = {}
    for _k, _l in zip(_used, _lab.tolist()):
        _out.setdefault(int(_l), []).append(_k)
    return [_out[_l] for _l in sorted(_out)]      # components 가 이미 크기 내림차순으로 번호를 준다


def class_usage(bucket: Cluster_Bucket,
                domains: list[str] | None = None) -> tuple[dict[str, int], dict[str, Counter]]:
    """id_map 을 정리할 때 필요한 두 가지 — ``({class: 표본 수}, {class: {겹친 class: 표본 수}})``.

    재배정이 끝나면 "이제 무엇을 지우고 무엇을 합치나" 가 남는데, 그 답의 재료는 **데이터에 있지
    사람의 기억에 있지 않다**. 다만 둘의 성격이 다르다:

    - **표본 0** — 아무 객체도 그 번호를 안 쓴다. 지워도 잃을 것이 없는 **자명한 후보**다.
    - **겹침** — 한 type 안에 함께 있었다는 **관찰일 뿐 후보가 아니다.** 여러 class 가 한 type 에
      드는 것은 "같은 물건" 이 아니라 *"이 잣대로 안 갈린다"* 는 뜻이고([`README.md`](README.md)),
      잣대가 못 보는 차이일 수 있다(작은 class 가 큰 class 안에 들어앉은 형태 · 잣대 해상도 한계).
      그래서 여기서 "합쳐라" 라고 말하지 않는다 — 숫자만 내고 판단은 사람이 한다.

    **겹침은 방향이 있다** — ``겹침[a][b]`` 는 *a 의 표본 중 b 와 같은 type 에 든 수*다. b 쪽 수가
    아니다. 둘은 다르고(큰 class 에 작은 class 가 들어앉으면 크게 어긋난다) 어느 쪽인지 안 정해 두면
    쌍을 볼 때 순회 순서에 따라 답이 달라진다.

    Args:
        bucket:  표본 store.
        domains: 겹침을 볼 잣대 (없으면 지금 보는 도메인 전부).

    Returns:
        ``(표본 수, 겹침)``. 겹침은 **한 도메인 안에서는 type 마다 더하고**(type 이 다르면 표본이
        다르다) **도메인끼리는 가장 센 것**을 남긴다(같은 표본을 축마다 다시 세지 않게).
    """
    _counts = Counter(str(_r.get("class", "")) for _r in bucket.Index().values())
    _ov: dict[str, Counter] = {}
    for _d in (domains if domains is not None else bucket.View_domains()):
        _per: dict[str, Counter] = {}
        for _t, _acc in bucket.Composition(_d).items():
            if _t < 0 or len(_acc) < 2:            # 미배정·단일 class 는 겹침이 아니다
                continue
            for _c, _n in _acc.items():
                _row = _per.setdefault(str(_c), Counter())
                for _o in _acc:
                    if str(_o) != str(_c):
                        _row[str(_o)] += int(_n)   # **자기** 표본 수 — type 마다 더한다
        for _c, _row in _per.items():
            _dst = _ov.setdefault(_c, Counter())
            for _o, _n in _row.items():
                _dst[_o] = max(_dst[_o], _n)       # 도메인끼리는 최대 (같은 표본을 두 번 안 세게)
    return dict(_counts), _ov


#: 병합 제안의 문턱 — 겹침이 **양쪽 표본에서 차지하는 몫**(작은 쪽 기준)이다.
#: 큰 class 안에 작은 class 가 통째로 들어앉으면 한쪽만 봤을 때 100% 가 나오는데, 그건 "같다" 가
#: 아니라 "포함" 이라 합치면 큰 쪽이 작은 쪽을 삼킨다. 그래서 **min** 을 쓴다.
STRONG_OVERLAP = 0.8
WEAK_OVERLAP   = 0.3


@dataclass(frozen=True)
class Hint:
    """id_map 정리 **제안** 하나 — 판단이 아니라 근거와 세기다.

    Attributes:
        kind:    지금은 ``merge`` 뿐. **삭제는 제안하지 않는다** (:func:`cleanup_hints` 참고).
        level:   ``strong`` / ``weak`` — 세기지 확신이 아니다. 강해도 실행은 사람이 정한다.
        classes: 대상 class 이름 둘.
        n:       근거가 된 표본 수.
        why:     사람이 읽을 근거 한 줄.
    """

    kind:    str
    level:   str
    classes: tuple[str, ...]
    n:       int
    why:     str


def cleanup_hints(bucket: Cluster_Bucket, domains: list[str] | None = None,
                  usage: tuple[dict, dict] | None = None) -> list[Hint]:
    """재배정 결과에서 id_map **병합 제안**을 뽑는다 (강한 것 먼저).

    :func:`class_usage` 가 낸 **관찰**(표본 수·겹침) 위에 세기를 매긴 것이다. 둘을 가른 이유는
    수명이 달라서다 — 숫자는 데이터가 정하고 문턱은 사람이 정한다.

    **삭제는 제안하지 않는다.** id_map 은 데이터셋 요약이 아니라 **부품 목록**이라, 표본 0 은
    "없는 물건" 이 아니라 *"아직 못 찍었다"* 다 — 반드시 존재하지만 아직 확보 못 한 부품의 번호를
    지우면 그 자리가 사라지고, 압축이 뒤 번호를 전부 민다(이득 0, 대가 있음). 단종·중복 등재 같은
    진짜 삭제 사유는 데이터 밖에 있으므로 표본 수는 **관찰로만** 내보이고 판단은 사람이 한다.

    **병합도 "해라" 가 아니다.** 여러 class 가 한 type 에 드는 것은 "같은 물건" 이 아니라
    *"이 잣대로 안 갈린다"* 는 뜻이라([`README.md`](README.md)) 잣대의 해상도 한계일 수 있다 —
    실측으로 1.1px 차이를 못 보는 구간이 있었다. 그래서 실행은 늘 사람이
    :class:`~core.format.id_map.Id_map` 편집으로 한다.

    Args:
        bucket:  표본 store.
        domains: 겹침을 볼 잣대 (없으면 지금 보는 도메인 전부).
        usage:   이미 구한 :func:`class_usage` 결과 (없으면 여기서 구한다) — 화면이 관찰과 제안을
            함께 보일 때 index(수십 MB)를 두 번 읽지 않게 하는 자리다.

    Returns:
        제안들 — ``strong`` 먼저, 같은 세기 안에서는 근거 표본이 많은 것부터.
    """
    _counts, _ov = usage if usage is not None else class_usage(bucket, domains)
    _out: list[Hint] = []
    _seen: set[tuple[str, str]] = set()
    for _a, _row in _ov.items():
        for _b in _row:
            _key = (_a, _b) if _a < _b else (_b, _a)
            if _key in _seen:
                continue
            _seen.add(_key)
            # **양쪽을 각자의 몫으로 본다** — 한쪽만 보면 포함 관계가 100% 로 보인다.
            _na = _ov.get(_key[0], {}).get(_key[1], 0)
            _nb = _ov.get(_key[1], {}).get(_key[0], 0)
            _share = min(_na / max(_counts.get(_key[0], 0), 1),
                         _nb / max(_counts.get(_key[1], 0), 1))
            _n = min(_na, _nb)
            if _share >= STRONG_OVERLAP:
                _out.append(Hint("merge", "strong", _key, _n,
                                 f"양쪽 표본의 {_share:.0%} 가 같은 type — 이 잣대로 거의 안 갈린다"))
            elif _share >= WEAK_OVERLAP:
                _out.append(Hint("merge", "weak", _key, _n,
                                 f"양쪽 표본의 {_share:.0%} 가 같은 type — 일부만 겹친다"))

    return sorted(_out, key=lambda _h: (_h.level != "strong", -_h.n))


#: **응집** 문턱 — 배정된 표본 중 가장 큰 type 이 담는 몫.
COHERENT_SHARE = 0.8

#: id 별 판정 — **응집(내가 하나인가) × 배타(남과 갈리나)** 네 갈래. 조치가 갈래마다 다르다.
DISTINCT  = "distinct"     # 구분   — 응집 ○ 배타 ○ · 이 잣대로는 제 자리를 가진다
DUPLICATE = "duplicate"    # 중복   — 응집 ○ 배타 ✘ · 뭉쳐 있는데 남과 같은 type 에 든다
CONFUSED  = "confused"     # 혼동   — 응집 ✘ 배타 ○ · 자기 표본이 흩어졌다
UNCLEAR   = "unclear"      # 판단 불가 — 둘 다 ✘ 이거나 배정이 아예 없다

_TRUST_ORDER = {UNCLEAR: 0, DUPLICATE: 1, CONFUSED: 2, DISTINCT: 3}


@dataclass(frozen=True)
class Class_stat:
    """class id 하나의 **신뢰도** — 이 잣대가 그 번호를 지지하는가.

    두 물음을 함께 답한다. 한쪽만 보면 틀린다 — 실측에서 ``c131``(2,989건)과 ``c93``(1,477건)은
    각자 놓고 보면 응집 98% 로 완벽한데, 서로의 98% 가 같은 type 에 든다. 응집만 재면 둘 다
    **구분**이 나오고, 그런 자리가 **26종**이었다.

    ==========  ==================================  ====================================
    /           배타 ○ (남과 갈린다)                배타 ✘
    ==========  ==================================  ====================================
    응집 ○      :data:`DISTINCT` — 구분             :data:`DUPLICATE` — 중복
    응집 ✘      :data:`CONFUSED` — 혼동             :data:`UNCLEAR` — 판단 불가
    ==========  ==================================  ====================================

    **판정은 이 잣대에 대한 진술이다** — "c131 = c93" 이 아니라 "이 feature 로 안 갈림" 이다.

    **판정의 분모는 배정된 표본이다 — 보류는 안 센다.** 보류는 "이 잣대가 자리를 못 정했다" 는
    말이라 그 표본에 대해 응집도 배타도 관측이 없다. 분모에 넣으면 없는 관측이 *불리한* 관측처럼
    작동해, 절반이 보류인 class 는 나머지가 완벽히 뭉쳐 있어도 응집이 0.5 로 눌린다. 보류를 두고
    무엇을 할지는 아직 화면이 없으므로(→ [`TODO.md`](TODO.md)) 관측으로만 내보인다.

    Attributes:
        name:        class 이름.
        n:           표본 수 (보류 포함 — 이 class 가 몇 건인가).
        types:       걸친 type 수 (보류 제외) — 많을수록 흩어져 있다.
        top_share:   **배정된 표본 중** 가장 큰 type 이 담는 몫 — **응집**. 1.0 이면 배정된 것이
            통째로 한 type 이다.
        pool_share:  전체 중 어디에도 안 붙은 몫 — **판정에 안 들어가는 관측**이다. 형상이
            불안정하거나 표본이 특이하다는 뜻이고, 크면 위 두 몫이 얇은 근거 위에 서 있다.
        rival:       가장 크게 겹치는 class (없으면 ``""``).
        rival_share: 그 겹침의 **대칭 몫** — 양쪽의 *배정된* 표본에서 차지하는 몫 중 작은 쪽
            (:data:`STRONG_OVERLAP` 참고). 한쪽만 보면 포함 관계가 100% 로 보인다.
        level:       위 표의 네 갈래.
    """

    name:        str
    n:           int
    types:       int
    top_share:   float
    pool_share:  float
    rival:       str
    rival_share: float
    level:       str


def class_trust(bucket: Cluster_Bucket, domain: str,
                usage: tuple[dict, dict] | None = None) -> list[Class_stat]:
    """class id 마다 **신뢰도**를 낸다 (약한 것 먼저) — 축 2 의 답이 이 목록이다.

    재료는 둘 다 이미 있었지만 갈라져 있었다: **응집**은 배정을 접으면 나오고(한 class 가 몇 type 에
    흩어졌나), **배타**는 :func:`class_usage` 의 겹침이 답한다(남과 같은 type 에 드나). 여기가
    그 둘을 id 한 줄로 합치는 자리다 — 조치가 둘의 **조합**으로 갈리기 때문이다
    (:class:`Class_stat` 의 표).

    겹침은 **대칭 몫**으로 잰다(:data:`STRONG_OVERLAP` 과 같은 식) — 한쪽만 보면 큰 class 에
    작은 class 가 들어앉은 자리가 100% 로 보인다.

    **두 몫 다 분모가 배정 수다** — 보류는 관측이 없는 자리라 판정에서 뺀다
    (:class:`Class_stat` 참고). 보류 자체는 열로 남겨 관측으로 보인다.

    **저장된 배정만 쓴다** — 좌표를 다시 안 읽으므로 6만 표본에서도 즉시 돈다.

    Args:
        bucket: 표본 store.
        domain: 볼 잣대. 종합(:data:`~.cluster.JOINT`)이면 자기 장부의 배정을 쓴다.
        usage:  이미 구한 :func:`class_usage` 결과 (없으면 여기서 구한다) — 화면이 제안
            (:func:`cleanup_hints`)과 함께 보일 때 index(수십 MB)를 두 번 읽지 않게 하는 자리다.

    Returns:
        ``Class_stat`` 목록 — 약한 갈래 먼저(:data:`UNCLEAR` → :data:`DUPLICATE` →
        :data:`CONFUSED` → :data:`DISTINCT`), 같은 갈래 안에서는 표본이 많은 것부터(영향이 크다).
    """
    _index = bucket.Index()
    _assign = bucket.Joint().get("assign", {}) if str(domain) == JOINT else None
    # 표본 수는 안 쓴다 — 분모가 **배정 수**라 아래에서 직접 센다.
    _ov = (usage if usage is not None else class_usage(bucket, [str(domain)]))[1]

    _by_class: dict[str, list[int]] = {}
    for _k, _rec in _index.items():
        _t = int(_assign.get(_k, POOL) if _assign is not None
                 else (_rec.get("types") or {}).get(str(domain), POOL))
        _by_class.setdefault(str(_rec.get("class", "")), []).append(_t)

    # **판정의 분모는 배정된 표본이다** — 보류는 빠진다(:attr:`Class_stat.pool_share` 참고).
    _placed = {_c: sum(1 for _t in _s if _t >= 0) for _c, _s in _by_class.items()}

    _out: list[Class_stat] = []
    for _c, _seats_of in _by_class.items():
        _n = len(_seats_of)
        _seats = Counter(_t for _t in _seats_of if _t >= 0)
        _top = _seats.most_common(1)[0][1] if _seats else 0
        _top_share = _top / max(_placed[_c], 1)
        _pool_share = (_n - _placed[_c]) / max(_n, 1)
        # 배타 — 가장 크게 겹치는 상대. **양쪽을 각자의 몫으로** 본다(포함을 겹침으로 안 읽게).
        # 겹침 수는 배정된 표본에서만 나오므로 분모도 배정 수다 — 전체로 나누면 보류가 많은 class
        # 일수록 덜 겹치는 것처럼 보인다.
        _rival, _share = "", 0.0
        for _o in _ov.get(_c, {}):
            _s = min(_ov.get(_c, {}).get(_o, 0) / max(_placed.get(_c, 0), 1),
                     _ov.get(_o, {}).get(_c, 0) / max(_placed.get(_o, 0), 1))
            if _s > _share:
                _rival, _share = str(_o), _s
        # **배정이 하나도 없으면 판정하지 않는다.** 겹칠 상대가 없는 것이 "남과 갈린다" 로 읽히면
        # 아직 안 가른 축이 전부 "혼동" 으로 나온다 — 흩어진 게 아니라 안 잰 것이다.
        _tight = _top_share >= COHERENT_SHARE
        _apart = _share < WEAK_OVERLAP
        _out.append(Class_stat(
            _c, _n, len(_seats), _top_share, _pool_share, _rival, _share,
            UNCLEAR if not _seats else
            DISTINCT if (_tight and _apart) else DUPLICATE if _tight else
            CONFUSED if _apart else UNCLEAR))
    return sorted(_out, key=lambda _s: (_TRUST_ORDER[_s.level], -_s.n))


def propagate(bucket: Cluster_Bucket, params: dict, progress: Progress = None) -> dict[str, int]:
    """종합이 **메운 자리를 축에 반영한다** — 사람이 누를 때만 도는, 되돌릴 수 없는 한 걸음.

    :func:`~.cluster.impute` 가 낸 값은 종합 전용이라 축 화면은 계속 "모른다"고 말한다. 그건 옳다 —
    추정이니까. 다만 사람이 그 추정을 보고 **맞다고 판단하면** 축에도 앉혀야 그 뒤 계산(구성표·중심·
    거리)이 그 표본을 포함한다. 그 결정을 자동으로 하지 않으려고 버튼으로 갈라 둔다.

    세 가지를 함께 한다 — 하나라도 빠지면 장부가 어긋난다::

        ① index    types/dists 에 메운 값을 앉힌다 (그 축의 중심까지 거리를 함께)
        ② stats    그 축을 다시 세어 중심·퍼짐이 새 멤버를 포함하게
        ③ joint    메울 것이 없어졌으니 종합을 다시 낸다

    **재군집은 안 한다.** type 경계는 잣대가 정한 그대로고, 여기서 하는 것은 **붙이기**뿐이다 —
    경계를 다시 그리면 사람이 보고 판단한 그 그림이 사라진다.

    Args:
        bucket: 산출물 store.
        params: 묶기 설정 (종합을 다시 낼 때 쓴다).
        progress: ``(라벨, 한 것, 전체)``.

    Returns:
        ``{도메인: 반영한 표본 수}`` — 없으면 빈 dict.
    """
    _imputed = dict(bucket.Joint().get("imputed") or {})
    if not _imputed:
        return {}
    _index = bucket.Index()
    _by_domain: dict[str, dict[str, int]] = {}
    for _k, _per in _imputed.items():
        if _k not in _index:
            continue
        for _d, _t in _per.items():
            _by_domain.setdefault(str(_d), {})[str(_k)] = int(_t)
    if not _by_domain:
        return {}

    _keys = sorted(_index)
    _norm = _norms(bucket, params)
    _axes = sorted(_by_domain) or bucket.Domains()
    # 반영할 축과 종합이 곱할 축을 **한 번에** 싣는다 — 아래 루프와 `_build_joint` 가 나눠 쓴다.
    _coords = _load(bucket, sorted(set(_by_domain) | set(_axes)), _keys, _norm, progress)
    _done: dict[str, int] = {}
    for _d, _assign in _by_domain.items():
        _X, _used = _coords.get(_d, _EMPTY)
        if not len(_used):
            continue
        _at = {_k: _i for _i, _k in enumerate(_used)}
        _lab = np.asarray([int((_index.get(_k, {}).get("types") or {}).get(_d, POOL))
                           for _k in _used])
        for _k, _t in _assign.items():
            if _k in _at:
                _lab[_at[_k]] = _t
        _stats = stats_of(_X, _lab)
        _C = centers(_stats)
        _dist = {_k: float(np.linalg.norm(_X[_at[_k]] - _C[_t]))
                 for _k, _t in _assign.items() if _k in _at and _t < len(_C)}
        bucket.Set_stats(_d, _stats)
        bucket.Set_assignment(_d, _assign, _dist)
        _done[_d] = len(_assign)
        if progress is not None:
            progress(f"[{_d}] 반영 {len(_assign)}건", len(_done), len(_by_domain))

    _build_joint(bucket, params, _axes, _keys, _coords, progress)
    return _done
