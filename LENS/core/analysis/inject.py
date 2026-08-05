"""전수 1회 — 정본을 훑어 **목록을 세우고 표본 벡터를 묶음별로 모은다.**

전수를 도는 자리는 여기 하나다. 이후는 bucket 안에서 class·type 단위로만 움직인다.

## 여기는 계산하지 않는다

표본 하나의 값은 **flow 가 만들어 정본에 넣는다**(``process/stream/mask/profile.py``). 이 모듈이 하는
일은 그것을 **읽어 묶는 것**뿐이다 — 무엇을 어떻게 만들지는 여기가 정하지 않는다.

한때 여기서 마스크를 태워 feature 를 뽑았다(``Mask_Geometry``). 그 구조에서는 같은 계산이 flow 와
분석 두 곳에 있었고, **분석을 돌려야만 값이 생겼다** — flow 로 만든 정본을 그대로 쓸 수가 없었다.
지금은 만들기가 flow 한 곳이고 여기는 배선이다.

이 모듈이 드는 것은 사실상 **무엇을 안 하는가** 다:

- **안 바뀐 표본은 정본 표현을 풀지도 않는다.** 판별 근거가 저장 표현의 서명이고 그건 디코드 없이
  나온다(인라인 rle 는 수백 바이트, 디코드는 600×800 배열 3.3 ms — 6만이면 그 차이가 수 분이다).
- **class 를 서명에 안 넣는다.** 라벨을 고쳐도 다시 모으지 않는다(입력 leaf 만 해싱한다).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Iterator

import numpy as np

from ..constant import MODIFIED, STAGED, UNCLASSIFIED_ID
from ..schema import Data_Ref
from ..typing import Arg_Info as UI
from . import cache
from .cluster import merge_totals, norm_from_totals, totals_of
from .extract import Extract_Spec
from .store import Address, Cluster_Bucket

#: 진행 통지 간격 — 항목마다 알리면 6만 표본에서 교차스레드 시그널 6만 번이라 통지가 일보다 비싸진다.
_TICK = 500

FRAME  = "frame"
OBJECT = "object"

#: 표본 벡터가 사는 정본 leaf — flow 의 ``Radial_profile`` 이 stem 마다 ``(n_obj, NT, K)`` 로 넣는다.
DEFAULT_LEAF = "radial_rle"


@dataclass
class Source_Spec:
    """분석 대상 선택 — **순회 축 + 입력 배선.** 필드가 곧 GUI 폼이다.

    Attributes:
        unit: ``"object"``(프레임의 객체마다) | ``"frame"``(프레임 하나가 한 표본).
        obj_index: object 단위에서 **특정 번호만** 볼 때 그 번호. ``None`` 이면 모든 객체.
        leaf: 읽을 정본 leaf 이름 — flow 가 만든 표본 벡터가 사는 자리.
        classes: class 필터. ``None`` = 전체.
        center_limit: 프레임 중심에서 이만큼보다 먼 객체는 **안 본다**. 단위는 정본의
            ``center_offset`` 과 같은 무차원 비율(중심 0, 모서리 0.5 — 대각선으로 정규화).
            ``None`` = 끄기. 값이 없는 객체는 **거르지 않는다** (:meth:`Accepts_center`).
    """

    unit: Annotated[str, UI(label="순회 단위", tip="object=객체마다 / frame=프레임 하나")] = OBJECT
    obj_index: int | None = 0
    leaf: str = DEFAULT_LEAF
    classes: list[str] | None = None
    center_limit: float | None = None

    def Accepts_center(self, offset: Any) -> bool:
        """그 객체의 ``center_offset`` 이 :attr:`center_limit` 안인가 (끄면 늘 True).

        **값이 없으면 통과시킨다.** 백필 전 정본이나 무게중심을 못 구한 객체가 여기 걸려 조용히
        사라지면, 화면에는 "필터가 걸렀다"와 "애초에 값이 없다"가 똑같이 보인다 — 없는 것을 근거로
        버리지 않는다(그 객체가 문제면 값을 채우는 것이 답이다).
        """
        if self.center_limit is None or offset is None:
            return True
        try:
            return float(offset) <= float(self.center_limit)
        except (TypeError, ValueError):
            return True                                   # 형식 불량 — 근거가 없으니 안 거른다


@dataclass(frozen=True)
class Candidate:
    """순회가 낸 대상 하나 — **주소·class 는 즉시, 벡터는 나중에 묶어서.**

    Attributes:
        address: ``(stem, obj_index)``.
        class_id: 그 대상의 현재 class (정본 값 — 라벨의 진실은 거기다).
        sign: 정본 저장 표현의 서명. **디코드 없이** 나온다.
    """

    address:  Address
    class_id: str
    sign:     str


def _sign_of(store, path: tuple[str, ...], name: str, ref: Data_Ref | None) -> str:
    """저장 표현 자체의 짧은 서명 — **디코드 없이**.

    인라인 leaf(rle·polygon)는 값이 이미 사이드카에 있으므로 그걸 해싱한다. 파일 leaf 는 값을 안 읽고
    **파일의 정체**(크기·mtime)를 쓴다.
    """
    if ref is None:
        return ""
    _val = ref.info.get("value")
    if _val is not None:
        _raw = (_val.get("counts") if isinstance(_val, dict) and "counts" in _val
                else json.dumps(_val, sort_keys=True, ensure_ascii=False, default=str))
        _b = _raw if isinstance(_raw, bytes) else str(_raw).encode("utf-8")
        return hashlib.blake2b(_b, digest_size=6).hexdigest()
    _p = store.Path_of(path, name, ref)
    if _p is None or not _p.exists():
        return ""
    _s = _p.stat()
    return hashlib.blake2b(f"{_s.st_size}:{_s.st_mtime_ns}".encode("utf-8"),
                           digest_size=6).hexdigest()


def _targets(frame: Data_Ref, spec: Source_Spec) -> Iterator[tuple[int, str | None, Data_Ref]]:
    """이 프레임의 대상들 ``(obj_index, obj_id, 노드)`` — 순회 축이 여기서 갈린다."""
    if spec.unit == FRAME:
        yield 0, None, frame
        return
    _objs = list(frame.Branches().items())
    if spec.obj_index is not None:
        _i = int(spec.obj_index)
        if _i < len(_objs):
            yield _i, _objs[_i][0], _objs[_i][1]
        return
    for _i, (_oid, _obj) in enumerate(_objs):
        yield _i, _oid, _obj


def iter_candidates(store, spec: Source_Spec, category: str) -> Iterator[Candidate]:
    """``category`` 버킷을 ``spec`` 대로 돌며 :class:`Candidate` 를 낸다.

    **버킷 순회 자체는 인메모리라 싸다**(6만에 ~0.01 초). 표본 벡터는 여기서 안 읽는다 — stem 마다 한
    배열에 살아서 **묶어 읽어야** 싸기 때문이다(:func:`cache.Collect`).

    표본 벡터가 사는 leaf 는 **프레임(stem) 것이다** — 객체마다 행 하나다. 그래서 그 leaf 가 없는
    프레임은 통째로 대상이 아니다(flow 를 아직 안 돌린 stem).

    **거르기는 전부 디코드 앞이다.** class·중심거리 모두 인라인 attr 이라 rle 를 안 풀고 판정된다 —
    그래서 순회가 싸다는 성질이 필터를 더해도 유지된다(무게중심을 그 자리에서 재려 했으면 걸러 버릴
    객체까지 전부 디코드해야 했다. ``center_offset`` 을 정본에 굳혀 둔 이유가 이것이다).
    """
    for _stem, _frame in store.Bucket(category).items():
        _ref = _frame.Get(spec.leaf)
        if _ref is None:                                     # flow 를 안 돌린 stem — 대상 아님
            continue
        _sign = _sign_of(store, (category, _stem), spec.leaf, _ref)
        for _idx, _oid, _node in _targets(_frame, spec):
            _cls = str(_node.Attr("class_id") or UNCLASSIFIED_ID)
            if spec.classes is not None and _cls not in spec.classes:
                continue
            if not spec.Accepts_center(_node.Attr("center_offset", None)):
                continue
            # 서명은 **그 stem 배열 한 장**의 것이다 — 객체 하나가 바뀌면 배열이 통째로 다시 쓰이므로
            # 같은 stem 의 형제들도 함께 무효가 된다. 값을 묶어 읽는 대가이고, 읽기는 어차피 묶음
            # 단위라 손해가 없다(옛 구조는 표본마다 사이드카를 열어 서명도 표본마다였다).
            yield Candidate(address=(_stem, _idx), class_id=_cls, sign=f"{_sign}#{_idx}")


def inject(store, bucket: Cluster_Bucket, spec: Source_Spec, contract: Extract_Spec,
           progress: Callable[[str, int, int], None] | None = None) -> dict[str, dict]:
    """정본 전수를 훑어 bucket 을 채운다 — **읽어서 class 별 캐시로 모은다.**

    모으면서 도메인마다 ``n·Σx·Σx²`` 를 더해 **정규화 상수**를 정한다(이미 있으면 안 바꾼다 — 확정
    값이라 표본이 늘었다고 흔들리면 안 된다). 표본별 기록(서명·class)은 ``index`` 한 장에 모인다.

    **캐시 축이 class 인 이유** — 묶기 전에 쓸 수 있는 축이 그것뿐이다(type 은 묶기가 낸 결과다).
    묶기가 끝나면 :func:`regroup` 이 type 축으로 다시 편성한다.

    Args:
        store: 정본 ``Dataset_Meta``.
        bucket: 산출물 ``Cluster_Bucket``.
        spec: 순회 축 + 입력 배선.
        contract: 계약 (잣대 목록 — 정규화 상수를 그 좌표에서 잰다).
        progress: ``(라벨, 한 것, 전체)`` 진행 콜백.

    Returns:
        ``{상태: {"total": 대상 수, "collected": 새로 모은 수}}``.
    """
    _index = bucket.Index()
    _totals, _out = [], {}
    _seen: set[str] = set()
    _by_class: dict[str, list[Address]] = {}
    _stale: set[str] = set()                      # 다시 모아야 하는 class

    for _cat in (STAGED, MODIFIED):
        _total = len(store.Bucket(_cat))
        _fresh, _n = 0, 0
        for _i, _cand in enumerate(iter_candidates(store, spec, _cat), 1):
            _key = bucket.Key(_cand.address)
            _rec = _index.get(_key)
            if _rec is None or _rec.get("sign") != _cand.sign:
                _stale.add(_cand.class_id)                   # 이 묶음의 캐시가 낡았다
                _fresh += 1
            elif str(_rec.get("class", "")) != _cand.class_id:
                _stale.add(_cand.class_id)                   # 라벨이 옮겨 왔다 — 이 묶음에 더해야
                _stale.add(str(_rec.get("class", "")))       # 떠난 묶음에서도 빼야
            _by_class.setdefault(_cand.class_id, []).append(_cand.address)
            # 배정(``types``·``dists``)은 **가르기가 쓴다** — 여기서는 옛 값을 이어받기만 한다.
            _index[_key] = {"sign": _cand.sign, "class": _cand.class_id, "state": _cat,
                            "types": dict((_rec or {}).get("types") or {}),
                            "dists": dict((_rec or {}).get("dists") or {})}
            _seen.add(_key)
            _n += 1
            _tick(progress, f"{_cat} 목록", _i, _total)
        _out[_cat] = {"total": _n, "collected": _fresh}

    for _key in [_k for _k in _index if _k not in _seen]:        # 정본에서 사라진 표본
        _stale.add(str(_index[_key].get("class", "")))
        _index.pop(_key)
    bucket.Set_index(_index)

    # ── 낡은 묶음만 다시 모은다 ────────────────────────────────────────────────
    _todo = [_c for _c in _by_class if _c in _stale] or []
    for _i, _cls in enumerate(sorted(_todo), 1):
        _got = cache.Collect(store, _by_class[_cls], spec.leaf, bucket.Key)
        if _got is None:
            cache.Drop(bucket, cache.CLASS, _cls)
            continue
        cache.Save(bucket, cache.CLASS, _cls, *_got)
        # 정규화 상수는 **잣대 값**에서 나온다 — 가르기가 그 좌표에서 도니까.
        _totals.append(totals_of(contract.Measure_batch(_got[1])))
        _tick(progress, "묶음 적재", _i, len(_todo))
    for _cls in [_c for _c in cache.Groups(bucket, cache.CLASS) if _c not in _by_class]:
        cache.Drop(bucket, cache.CLASS, _cls)                   # 통째로 사라진 class

    if not bucket.Norm() and _totals:
        bucket.Set_norm(norm_from_totals(_totals))
    return _out


def reclass(store, bucket: Cluster_Bucket, spec: Source_Spec, moves: list,
            progress: Callable[[str, int, int], None] | None = None) -> dict[str, int]:
    """class 이동만 반영한다 — **떠난 묶음과 도착 묶음만** 다시 모은다.

    :func:`inject` 를 다시 도는 것과 다른 점은 **정본 전수 순회가 없다**는 것이다. 무엇이 어디로
    갔는지는 호출 측이 이미 알고 있으므로(적용 목록), 그 두 묶음만 정본에서 다시 읽으면 된다.

    ``index.class`` 와 캐시 묶음을 **같은 걸음에서** 고친다 — 둘이 갈라지면 그 표본의 행을 영영
    못 찾는다(묶음 주소가 곧 class 다).

    **군집 결과와 정규화 상수는 안 건드린다.** class 는 배정에 안 들어가고, 상수는 전체에서 나온
    값이라 몇 건이 옮겨졌다고 흔들릴 이유가 없다.

    Args:
        store: 정본 ``Dataset_Meta``.
        bucket: 산출물 ``Cluster_Bucket``.
        spec: 순회 축 (여기선 ``leaf`` 만 쓴다).
        moves: ``[((stem, obj), 새 class), …]`` — 적용이 정본에 쓴 목록 그대로.
        progress: ``(라벨, 한 것, 전체)``.

    Returns:
        ``{class: 그 묶음의 표본 수}`` — 다시 모은 묶음만.
    """
    _index = bucket.Index()
    _touched: set[str] = set()
    for _addr, _cid in moves:
        _rec = _index.get(bucket.Key(_addr))
        if _rec is None:
            continue
        _touched.add(str(_rec.get("class", "")))
        _touched.add(str(_cid))
        _rec["class"] = str(_cid)
    if not _touched:
        return {}
    bucket.Set_index(_index)

    _members: dict[str, list] = {}
    for _k, _rec in _index.items():
        _c = str(_rec.get("class", ""))
        if _c in _touched:
            _members.setdefault(_c, []).append(bucket.Address(_k))

    _out: dict[str, int] = {}
    for _i, _c in enumerate(sorted(_touched), 1):
        _tick(progress, "묶음 재적재", _i, len(_touched))
        _got = cache.Collect(store, _members.get(_c, []), spec.leaf, bucket.Key)
        if _got is None:
            cache.Drop(bucket, cache.CLASS, _c)      # 통째로 비었다
            continue
        cache.Save(bucket, cache.CLASS, _c, *_got)
        _out[_c] = len(_got[0])
    return _out


def regroup(bucket: Cluster_Bucket, domain: str,
            progress: Callable[[str, int, int], None] | None = None) -> int:
    """묶기가 끝난 뒤 캐시를 **type 축으로 다시 편성한다.** 만든 묶음 수 반환.

    class 축 캐시는 묶기 **전에** 쓰려고 있는 것이라(정본이 아는 유일한 축), 배정이 나오면 그 축으로는
    type 하나를 읽으려고 여러 class 파일을 다 열어야 한다. 재편성하면 type 하나가 한 파일이다 —
    템플릿·재군집이 그 단위로 돈다.

    **class 축을 지우지 않는다** — 라벨이 바뀌면 :func:`inject` 가 그 축으로 다시 모으고, type 은
    재군집마다 다시 선다. 둘은 수명이 다르다.

    Args:
        bucket: 산출물 store.
        domain: 배정을 읽을 도메인 (그 도메인의 type 축으로 편성한다).
        progress: ``(라벨, 한 것, 전체)``.

    Returns:
        만든 type 묶음 수.
    """
    _seat = {_k: int((_r.get("types") or {}).get(domain, -1))
             for _k, _r in bucket.Index().items()}
    _rows: dict[int, tuple[list[str], list[np.ndarray]]] = {}
    # **묶음을 전부 연다.** 어느 묶음에 무엇이 들었는지는 npz 가 답한다 — index 의 class 로 고르면
    # 라벨이 옮겨진 표본의 행이 옛 묶음에 남아 type 축 캐시에서 조용히 빠진다.
    _groups = cache.Groups(bucket, cache.CLASS)
    for _i, _g in enumerate(_groups, 1):
        _tick(progress, "재편성", _i, len(_groups))
        _got = cache.Load(bucket, cache.CLASS, _g)
        if _got is None:
            continue
        for _k, _v in zip(*_got):
            _t = _seat.get(_k, -1)
            if _t < 0:                                  # 배정이 없다(미배정) — type 축에 자리가 없다
                continue
            _slot = _rows.setdefault(_t, ([], []))
            _slot[0].append(_k)
            _slot[1].append(_v)

    for _t in cache.Groups(bucket, cache.TYPE):          # 옛 편성을 걷는다 (type 번호는 재계산된다)
        cache.Drop(bucket, cache.TYPE, _t)
    for _t, (_keys, _vals) in _rows.items():
        cache.Save(bucket, cache.TYPE, str(_t), _keys, np.stack(_vals))
    return len(_rows)


def _tick(progress, label: str, done: int, total: int) -> None:
    """진행 통지 — :data:`_TICK` 마다, 그리고 마지막에 한 번(끝을 정확히 보이게)."""
    if progress is not None and (done % _TICK == 0 or done == total):
        progress(label, done, total)
