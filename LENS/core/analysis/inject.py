"""전수 1회 — 정본을 훑어 바뀐 표본만 추출해 담고, 담으며 index·정규화 상수를 낸다.

전수를 도는 자리는 여기 하나다. 이후는 bucket 안에서 class·type 단위로만 움직인다.

이 모듈이 드는 것은 사실상 **무엇을 안 하는가** 다:

- **안 바뀐 표본은 정본 표현을 풀지도 않는다.** 판별 근거가 저장 표현의 서명이고 그건 디코드 없이
  나온다(인라인 rle 는 수백 바이트, 디코드는 600×800 배열 3.3 ms — 6만이면 그 차이가 수 분이다).
- **class 를 서명에 안 넣는다.** 라벨을 고쳐도 재추출이 없다(입력 leaf 만 해싱한다).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Iterator

from ..constant import MODIFIED, STAGED, UNCLASSIFIED_ID
from ..schema import Data_Ref
from ..typing import Arg_Info as UI
from .cluster import merge_totals, norm_from_totals, totals_of
from .extract import Base_Extractor
from .store import Address, Cluster_Bucket

#: 진행 통지 간격 — 항목마다 알리면 6만 표본에서 교차스레드 시그널 6만 번이라 통지가 일보다 비싸진다.
_TICK = 500

FRAME  = "frame"
OBJECT = "object"


@dataclass
class Source_Spec:
    """분석 대상 선택 — **순회 축 + 입력 배선.** 필드가 곧 GUI 폼이다.

    Attributes:
        unit: ``"object"``(프레임의 객체마다) | ``"frame"``(프레임 하나가 한 표본).
        obj_index: object 단위에서 **특정 번호만** 볼 때 그 번호. ``None`` 이면 모든 객체.
        inputs: ``{추출기 파라미터: 정본 leaf 이름}``. 비면 파라미터 이름을 그대로 leaf 이름으로 본다.
        classes: class 필터. ``None`` = 전체.
        center_limit: 프레임 중심에서 이만큼보다 먼 객체는 **안 본다**. 단위는 정본의
            ``center_offset`` 과 같은 무차원 비율(중심 0, 모서리 0.5 — 대각선으로 정규화).
            ``None`` = 끄기. 값이 없는 객체는 **거르지 않는다** (:meth:`Accepts_center`).
    """

    unit: Annotated[str, UI(label="순회 단위", tip="object=객체마다 / frame=프레임 하나")] = OBJECT
    obj_index: int | None = 0
    inputs: dict[str, str] = field(default_factory=dict)
    classes: list[str] | None = None
    center_limit: float | None = None

    def Leaf_of(self, param: str) -> str:
        """추출기 파라미터 → 읽을 정본 leaf 이름 (미지정이면 파라미터 이름 그대로)."""
        return self.inputs.get(param, param)

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
    """순회가 낸 대상 하나 — **주소·class 는 즉시, 입력 실물은 부를 때.**

    Attributes:
        address: ``(stem, obj_index)``.
        class_id: 그 대상의 현재 class (정본 값 — 라벨의 진실은 거기다).
        sign: 정본 저장 표현의 서명. **디코드 없이** 나온다.
        decode: ``() -> {추출기 파라미터: 값}`` — 여기서 비로소 rle 가 배열이 된다.
    """

    address:  Address
    class_id: str
    sign:     str
    decode:   Callable[[], dict]


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


def iter_candidates(store, spec: Source_Spec, extractor: Base_Extractor,
                    category: str) -> Iterator[Candidate]:
    """``category`` 버킷을 ``spec`` 대로 돌며 :class:`Candidate` 를 낸다.

    **버킷 순회 자체는 인메모리라 싸다**(6만에 ~0.01 초). 비싼 것은 정본 표현의 디코드라 그것만 지연
    호출로 미룬다.

    입력 leaf 는 **대상 노드에서 먼저 찾고 없으면 프레임에서** 찾는다 — 객체마다 다른 것(mask)과
    프레임이 공유하는 것(image)을 한 추출기가 함께 받을 수 있게 하는 주소 규칙이다.

    **거르기는 전부 디코드 앞이다.** class·중심거리 모두 인라인 attr 이라 rle 를 안 풀고 판정된다 —
    그래서 순회가 싸다는 성질이 필터를 더해도 유지된다(무게중심을 그 자리에서 재려 했으면 걸러 버릴
    객체까지 전부 디코드해야 했다. ``center_offset`` 을 정본에 굳혀 둔 이유가 이것이다).
    """
    _params = extractor.INPUTS
    for _stem, _frame in store.Bucket(category).items():
        for _idx, _oid, _node in _targets(_frame, spec):
            _refs = {_p: (_node.Get(spec.Leaf_of(_p)) or _frame.Get(spec.Leaf_of(_p)))
                     for _p in _params}
            if any(_r is None for _r in _refs.values()):      # 입력이 없다 — 대상 아님
                continue
            _cls = str(_node.Attr("class_id") or UNCLASSIFIED_ID)
            if spec.classes is not None and _cls not in spec.classes:
                continue
            if not spec.Accepts_center(_node.Attr("center_offset", None)):
                continue
            _path = (category, _stem) + ((_oid,) if _oid is not None else ())
            _sign = "|".join(_sign_of(store, _path, spec.Leaf_of(_p), _refs[_p])
                             for _p in _params)

            def _decode(_p=_path, _r=dict(_refs)):
                return {_param: store.Decode(_p, spec.Leaf_of(_param), _ref, "npy")
                        for _param, _ref in _r.items()}

            yield Candidate(address=(_stem, _idx), class_id=_cls, sign=_sign, decode=_decode)


def inject(store, bucket: Cluster_Bucket, extractor: Base_Extractor, spec: Source_Spec,
           progress: Callable[[str, int, int], None] | None = None) -> dict[str, dict]:
    """정본 전수를 훑어 bucket 을 채운다 — **바뀐 표본만** 추출한다.

    담으면서 도메인마다 ``n·Σx·Σx²`` 를 더해 **정규화 상수**를 정한다(이미 있으면 안 바꾼다 — 확정
    값이라 표본이 늘었다고 흔들리면 안 된다). 표본별 기록(서명·class)은 ``index`` 한 장에 모인다.

    Args:
        store: 정본 ``Dataset_Meta``.
        bucket: 산출물 ``Cluster_Bucket``.
        extractor: 계약을 든 추출기.
        spec: 순회 축 + 입력 배선.
        progress: ``(라벨, 한 것, 전체)`` 진행 콜백.

    Returns:
        ``{상태: {"total": 대상 수, "extracted": 다시 뽑은 수}}``.
    """
    _index = bucket.Index()
    _contract = extractor.Spec()
    _specs = _contract.Route_specs()
    _totals, _out = [], {}
    _seen: set[str] = set()

    for _cat in (STAGED, MODIFIED):
        _total = len(store.Bucket(_cat))
        _made, _n = 0, 0
        for _i, _cand in enumerate(iter_candidates(store, spec, extractor, _cat), 1):
            _key = bucket.Key(_cand.address)
            _rec = _index.get(_key)
            if _rec is None or _rec.get("sign") != _cand.sign:   # 다르면 그때만 정본을 푼다
                _values = extractor(**_cand.decode())
                if not _values:                                 # 추출기가 "대상 아님" 이라 했다
                    _tick(progress, f"{_cat} 특징화", _i, _total)
                    continue
                bucket.Put_features(_cand.address, _values, _specs, _cat)
                # 정규화 상수는 **잣대 값**에서 나온다 — 가르기가 그 좌표에서 도니까. feature 에서
                # 재면 접기가 바뀔 때 상수가 조용히 안 맞는다.
                _totals.append(totals_of(_contract.Measure(_values)))
                _made += 1
            # 배정(``types``·``dists``)은 **가르기가 쓴다** — 여기서는 옛 값을 이어받기만 한다.
            # feature 가 바뀌면 ``sign`` 이 달라져 도메인 서명이 흔들리므로 `group.build` 가 그
            # 도메인을 다시 가른다. 라벨(``class``)만 바뀌면 배정은 그대로다 — class 는 obj 에 붙은
            # 정보라 가르기에 안 들어간다.
            _index[_key] = {"sign": _cand.sign, "class": _cand.class_id, "state": _cat,
                            "types": dict((_rec or {}).get("types") or {}),
                            "dists": dict((_rec or {}).get("dists") or {})}
            _seen.add(_key)
            _n += 1
            _tick(progress, f"{_cat} 특징화", _i, _total)
        _out[_cat] = {"total": _n, "extracted": _made}

    for _key in [_k for _k in _index if _k not in _seen]:        # 정본에서 사라진 표본
        _index.pop(_key)
        if bucket.Has(_key):
            bucket.Delete(_key)
    bucket.Set_index(_index)
    if not bucket.Norm() and _totals:
        bucket.Set_norm(norm_from_totals(_totals))
    return _out


def _tick(progress, label: str, done: int, total: int) -> None:
    """진행 통지 — :data:`_TICK` 마다, 그리고 마지막에 한 번(끝을 정확히 보이게)."""
    if progress is not None and (done % _TICK == 0 or done == total):
        progress(label, done, total)
