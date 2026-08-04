"""가르기 오케스트레이션 — **도메인 단위**로 움직인다. 정본을 안 읽는다.

계산은 :func:`~.cluster.fit` 이 다 하고 여기는 배선만 든다: 어느 도메인이 낡았나 → 그 도메인
좌표를 모아 → ``fit`` → 배정과 통계를 store 에 앉힌다.

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
    members_of, merge_totals, neighbors_of, norm_from_totals, stats_of, threshold_of,
    totals_of, type_neighbors)
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
    _norm = _ensure_norm(bucket, _domains, _keys, progress)

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

    for _i, (_dom, _sig) in enumerate(_todo, 1):
        _X, _used = _stack(bucket, _dom, _keys, _norm.get(_dom), progress)
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
    _axes = [_d for _d in _domains if _d != JOINT]
    _sig = joint_signature(params, {_d: _known.get(_d, "") for _d in _axes})
    _ran = False
    if _known.get(JOINT) != _sig and len(_axes) >= 2:
        _build_joint(bucket, params, _axes, _keys, _norm, progress)
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
                    "weld": bool(params.get("weld_types", True))},
                   sort_keys=True).encode("utf-8"), digest_size=5).hexdigest()


def _build_joint(bucket: Cluster_Bucket, params: dict, domains: list[str], keys: list[str],
                 norm: dict, progress: Progress) -> None:
    """켠 축들을 합쳐 종합 자리에 앉힌다 — 낼 것이 없으면 걷고 ``None``.

    두 걸음이다::

        ① impute   기권한 축을 **다른 축을 참고해** 메운다 (:func:`~.cluster.impute`)
        ② join     메운 label 로 조합을 만들고(쪼갬), **자의적인 경계는 도로 붙인다**(병합)

    ①이 좌표를 필요로 하므로 축마다 한 번 더 쌓는다. 축 루프에서 이미 읽어 트리에 앉혀 뒀으면
    사이드카를 다시 안 탄다(``_resolved`` 캐시).

    **종합은 자기 장부에 앉는다** — ``index.types`` 에 안 섞는다. 거기 있는 것은 잣대가 문턱을 넘어
    인정한 값이고, 메운 자리는 추정이라 수명도 뜻도 다르다.

    호출 측이 **낼지 말지를 이미 정한다** — 여기는 내는 일만 한다.
    """
    _use = list(domains)
    _index = bucket.Index()
    _labels = {_d: np.asarray([int((_index.get(_k, {}).get("types") or {}).get(_d, POOL))
                              for _k in keys]) for _d in _use}

    _coords, _centers = {}, {}
    for _d in _use:
        _X, _used = _stack(bucket, _d, keys, norm.get(_d), progress)
        if len(_used) == len(keys):
            _coords[_d] = _X
        _centers[_d] = bucket.Centers(_d)
    _bound = float(params.get("impute_bound", 0.3))
    _filled: dict[str, list[int]] = {}
    if _bound > 0 and _coords:
        _labels, _filled = impute(_labels, _coords, _centers, _bound)

    _edges = ({_d: type_neighbors(bucket.Centers(_d), threshold_of(params, _d),
                                  neighbors_of(params, _d)) for _d in _use}
              if params.get("weld_types", True) else None)
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



def _ensure_norm(bucket: Cluster_Bucket, domains: list[str], keys: list[str],
                 progress: Progress) -> dict:
    """정규화 상수가 **없는 도메인만** 채운다 — 재추출 없이.

    ``norm`` 은 잣대 좌표의 값이라 잣대를 바꾸면 낡는다. 그런데 쓰는 자리가 추출뿐이라, config 에
    축을 더하면 상수가 안 생기고 :func:`~.cluster.equalize` 가 원 단위로 통과시킨다 — 그러면 ``k``
    가 σ 가 아니라 px 를 재게 되어 **아무도 안 붙는다**(실측 64,336건 100% 미배정).

    모델은 안 태운다. 저장된 feature 를 접기만 하면 되므로 사이드카 읽기 한 바퀴다.
    """
    _norm = dict(bucket.Norm())
    _missing = [_d for _d in domains if _d not in _norm and _d != JOINT]
    if not _missing:
        return _norm
    _totals = []
    for _i, _k in enumerate(keys):
        _v = bucket.Measure(bucket.Address(_k), _missing)
        if _v:
            _totals.append(totals_of(_v))
        if progress is not None and (_i + 1) % 2000 == 0:
            progress(f"정규화 상수 ({' · '.join(_missing)})", _i + 1, len(keys))
    if not _totals:
        return _norm
    _norm.update(norm_from_totals([merge_totals(_totals)]))
    bucket.Set_norm(_norm)
    return _norm


def _stack(bucket: Cluster_Bucket, domain: str, keys: list[str], norm_d: dict | None,
           progress: Progress) -> tuple[np.ndarray, list[str]]:
    """그 도메인의 전 표본을 **표준화 좌표**로 쌓는다 ``(n, D) float32``.

    상주는 도메인 **하나치**다(실측 ``radial_outline`` 512채널 × 6만 = 132 MB). 도메인이 직교라
    한 번에 하나만 들면 되고, :func:`~.cluster.fit` 이 블록으로 거리를 재므로 스트리밍으로는 안 된다.

    값을 못 읽은 표본은 **키 목록에서도 뺀다**. 배열만 짧아지면 뒤이은 ``zip(used, lab)`` 이 배정을
    엉뚱한 표본에 붙인다 — 조용히 어긋나는 자리라 둘을 함께 낸다.

    Returns:
        ``((n, D) 좌표, 실제로 쌓인 키)`` — 순서가 같다.
    """
    _rows, _used = [], []
    for _i, _k in enumerate(keys):
        _v = bucket.Measure(bucket.Address(_k), [domain]).get(domain)
        if _v is None:
            continue                                  # 값이 없다 — 이 표본은 가를 대상이 아니다
        _rows.append(equalize(np.asarray(_v)[None], norm_d)[0].astype(np.float32))
        _used.append(_k)
        if progress is not None and (_i + 1) % 5000 == 0:
            progress(f"[{domain}] 적재", _i + 1, len(keys))
    if not _rows:
        return np.zeros((0, 0), np.float32), []
    return np.stack(_rows), _used


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
    _X, _used = _stack(bucket, domain, _keys, bucket.Norm().get(domain), progress)
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


#: class 응집도 등급의 문턱 — 가장 큰 type 이 담는 몫과 보류 몫.
COHERENT_SHARE = 0.8
LOOSE_SHARE    = 0.5


@dataclass(frozen=True)
class Class_stat:
    """한 class 가 **자기 안에서** 얼마나 한 덩어리인가 — 분류 결과를 믿을 근거.

    지금까지 본 것(type → 어떤 class 들이 들었나)의 **반대 방향**이다. 같은 번호를 단 것들끼리
    비교해서, 그 번호가 실제로 한 물건을 가리키는지 묻는다.

    Attributes:
        name:       class 이름.
        n:          표본 수.
        types:      걸친 type 수 (보류 제외) — 많을수록 흩어져 있다.
        top_share:  가장 큰 type 이 담는 몫 — **응집도**. 1.0 이면 통째로 한 type 이다.
        pool_share: 어디에도 안 붙은 몫 — 형상이 불안정하거나 표본이 특이하다.
        d_med:      중심까지 거리 중앙값 (보류는 뺀다) — 같은 type 안에서도 가장자리인가.
        level:      ``strong`` / ``medium`` / ``weak``.
    """

    name:       str
    n:          int
    types:      int
    top_share:  float
    pool_share: float
    d_med:      float
    level:      str


def class_coherence(bucket: Cluster_Bucket, domain: str) -> list[Class_stat]:
    """class 마다 **자기 표본끼리의 응집도**를 잰다 (약한 것 먼저).

    ``cleanup_hints`` 가 *"이 둘이 안 갈린다"* 를 본다면 여기는 *"이 하나가 하나인가"* 를 본다.
    한 class 의 표본이 여러 type 에 흩어져 있으면 둘 중 하나다 — **라벨이 섞였거나**(다른 물건이
    같은 번호를 달았다) **그 부품이 원래 여러 모습**이거나(자세·변형). 어느 쪽인지는 데이터가 아니라
    사람이 알지만, **흩어졌다는 사실**은 여기서 나온다.

    **저장된 배정만 쓴다** — 좌표를 다시 안 읽으므로 6만 표본에서도 즉시 돈다.

    Args:
        bucket: 표본 store.
        domain: 볼 잣대. 종합(:data:`~.cluster.JOINT`)이면 자기 장부의 배정을 쓴다.

    Returns:
        ``Class_stat`` 목록 — ``weak`` 먼저, 같은 등급 안에서는 표본이 많은 것부터(영향이 크다).
    """
    _index = bucket.Index()
    _dist = bucket.Distances(domain)
    _assign = bucket.Joint().get("assign", {}) if str(domain) == JOINT else None

    _by_class: dict[str, list[tuple[int, float]]] = {}
    for _k, _rec in _index.items():
        _t = int(_assign.get(_k, POOL) if _assign is not None
                 else (_rec.get("types") or {}).get(str(domain), POOL))
        _by_class.setdefault(str(_rec.get("class", "")), []).append((_t, _dist.get(_k, np.inf)))

    _out: list[Class_stat] = []
    for _c, _rows in _by_class.items():
        _n = len(_rows)
        _seats = Counter(_t for _t, _ in _rows if _t >= 0)
        _pool = sum(1 for _t, _ in _rows if _t < 0)
        _top = _seats.most_common(1)[0][1] if _seats else 0
        _fin = [_d for _t, _d in _rows if _t >= 0 and np.isfinite(_d)]
        _top_share, _pool_share = _top / max(_n, 1), _pool / max(_n, 1)
        if _top_share >= COHERENT_SHARE and _pool_share <= (1 - COHERENT_SHARE):
            _level = "strong"
        elif _top_share < LOOSE_SHARE or _pool_share > LOOSE_SHARE:
            _level = "weak"
        else:
            _level = "medium"
        _out.append(Class_stat(_c, _n, len(_seats), _top_share, _pool_share,
                               float(np.median(_fin)) if _fin else float("inf"), _level))
    _order = {"weak": 0, "medium": 1, "strong": 2}
    return sorted(_out, key=lambda _s: (_order[_s.level], -_s.n))


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
    _norm = bucket.Norm()
    _done: dict[str, int] = {}
    for _d, _assign in _by_domain.items():
        _X, _used = _stack(bucket, _d, _keys, _norm.get(_d), progress)
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

    _build_joint(bucket, params, sorted(_by_domain) or bucket.Domains(), _keys, _norm, progress)
    return _done
