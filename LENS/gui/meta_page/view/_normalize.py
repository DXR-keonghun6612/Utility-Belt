"""저장 직전 정돈 — 편집한 mask 에 맞춰 파생값을 다시 맞춘다.

**편집 중에는 안 한다.** 붓질 한 번마다 bbox 가 따라 움직이면 상자를 잡고 있을 수가 없고(핸들이
손 밑에서 도망간다), 객체 순서가 바뀌면 트리에서 겨누던 줄이 튄다. 편집 중 bbox 는 **자르는
기준**으로 남고(`Clip_to_box`), 맞추는 것은 저장 한 번에 몰아 한다.

네 가지를 이 순서로 한다 — **뒤가 앞에 의존한다**::

    ① bbox          ← mask 외접 상자        (mask 가 truth 고 상자는 그 요약이다)
    ② 중심점(비저장)  ← mask 무게중심, 없으면 bbox 중앙
    ③ pose·offset   ← ②의 자리 + mask 주축각 · ②와 프레임 중심의 거리
    ④ order         ← ②의 거리 순          (②가 없으면 정렬 기준이 없다)

**중심점은 더 이상 저장하지 않는다.** ``center`` attr 은 걷혔고 그 자리는 `pose` 의 앞 두 칸이다 —
자리를 두 곳에 적으면 한쪽만 갱신되어 조용히 갈린다(옛 ``center`` 를 읽는 코드는 애초에 없었고,
실제 소비처는 ``center_offset`` 하나였다). 옛 데이터의 ``center`` 는 저장할 때 **걷는다**.

``center_offset`` 은 남는다 — 자세가 아니라 **프레임 안에서 얼마나 가장자리인가**라는 다른 물음이고,
[`core.analysis.inject`](../../../core/analysis/inject.py) 가 mask 를 디코드하지 않고 표본을 거르는
근거로 쓴다(그러려고 정본에 굳혀 둔 값이다).

계산은 전부 [`core.func`](../../../core/func/) 이 든다 — 여기는 트리를 아는 계층이라 **어디서 읽어
어디에 쓸지**만 정한다. flow 의 ``Mask_center``·``Order_objects`` 와 같은 규약이라, 같은 정본을
flow 로 돌려도 값이 안 흔들린다. **회전만 예외로 [`core.process`](../../../core/process/stream/mask/shape.py)
의 사슬이 든다** — 그 각은 feature 파이프라인이 형상을 재기 전에 이미 구하는 값이라, 여기서 다시 재면
사람이 적은 자세와 학습이 쓰는 정렬이 서로 다른 정면을 본다.

**여기와 flow 는 같은 일을 한다.** flow 의 ``Radial_profile`` 이 객체를 만들면서 ``pose``·배열을 함께
얹고, 이 모듈은 **사람이 고친 한 stem** 에 같은 것을 다시 얹는다 — 사슬이 하나라 값이 안 갈린다.
"""

from __future__ import annotations

import numpy as np

from core.format import pose, rle
from core.func.cv.geom import Box_center, Center_offset, Mask_centroid, Mask_to_box
from core.func.mask.instance import Order_by_center
from core.process.stream.mask import profile
from core.schema import Data_Ref

from ._node_tree import Node

#: 서술자 format — flow 가 만드는 것과 **같은 모양**이어야 한다(`Mask_center` · `Split_objects`).
_BBOX_FMT   = ("region", "bbox", "xyxy")
_OFFSET_FMT = ("", "float")
#: 자세는 자기 도메인을 갖는다 — ``(pose, quat)`` (`core/port/domain/pose.py`). 값은 인라인 dict 이고
#: 그 구조는 `core/format/pose.py` 가 소유한다 (``rle`` 이 같은 자리의 선례 — 인라인 dict 구조).
_POSE_FMT   = ("pose", "quat")
#: 눈금(``profile_spec``)의 라우팅 — dict 이라 params 에 yaml 한 장으로 앉는다(`id_map` 과 같은 자리).
_SPEC_PARAM_SPEC = {"to": "storage", "type": "docs", "format": "yaml"}


def _mask_of(obj: Node) -> np.ndarray | None:
    """그 객체의 mask (인라인 rle) — 없거나 비면 None."""
    _ref = obj.ref.Get("mask")
    _val = _ref.info.get("value") if _ref is not None else None
    return rle.To_mask(_val) if _val else None


def _put(obj: Node, name: str, fmt: tuple, value) -> None:
    """인라인 attr 을 만들거나 갱신한다 — 값 자리만 바꾸고 서술자는 그대로 둔다."""
    _ref = obj.ref.Get(name)
    if _ref is None:
        obj.ref.Push(name, Data_Ref(format=fmt, info={"value": value}))
    else:
        _ref.info["value"] = value


def _drop(obj: Node, name: str) -> None:
    """그 attr 을 걷는다 — **잴 근거가 없어졌으면 옛값을 남기지 않는다**(거짓말이 된다)."""
    if obj.ref.Get(name) is not None:
        obj.ref.info.pop(name, None)


def Fit_bbox(obj: Node) -> bool:
    """① ``bbox`` 를 mask 외접 상자로 맞춘다. 고쳤으면 True.

    mask 가 없는 객체는 **안 건드린다** — 그 객체의 bbox 는 사람이 그린 것이고 그것이 유일한 근거다.
    mask 가 있는데 비었으면(다 지웠으면) 상자도 뜻이 없으므로 걷는다.
    """
    _m = _mask_of(obj)
    if _m is None:
        return False
    _box = Mask_to_box(_m)
    if _box is None:                                 # mask 를 다 지웠다 — 상자도 근거가 없다
        _drop(obj, "bbox")
        return True
    _new = [float(_v) for _v in _box]
    _ref = obj.ref.Get("bbox")
    if _ref is not None and list(_ref.info.get("value") or ()) == _new:
        return False
    _put(obj, "bbox", _BBOX_FMT, _new)
    return True


def Center_of(obj: Node) -> tuple[float, float] | None:
    """② 이 객체의 중심점 ``(x, y)`` — **저장하지 않는다**(pose 의 자리이자 정렬의 근거).

    **mask 무게중심 우선, 없으면 bbox 중앙**이다 — flow 의 ``Mask_center._center_of`` 와 같은 규약이라야
    "가까운 순" 과 "중심에서 얼마" 가 어긋나지 않는다.

    옛 ``center`` attr 이 이 값을 들었는데, 자리는 이제 `pose` 가 든다 — 같은 값을 두 곳에 적으면 한쪽만
    갱신되어 조용히 갈린다. 다만 **상자만 그린 객체**(mask 없음)는 자세를 못 만들어도 정렬·거리는 재야
    하므로, 그 경우 이 값은 pose 로 안 가고 여기서만 쓰인다.
    """
    _m = _mask_of(obj)
    _c = Mask_centroid(_m) if _m is not None else None
    if _c is not None:
        return _c
    _b = obj.ref.Get("bbox")
    _v = _b.info.get("value") if _b is not None else None
    return Box_center([float(_x) for _x in _v]) if _v and len(_v) == 4 else None


def Fit_offset(obj: Node, shape: tuple[int, int] | None,
               center: tuple[float, float] | None) -> None:
    """② ``center_offset`` 을 얹는다 — 프레임 안에서 **얼마나 가장자리인가**(자세가 아니다).

    자리는 `pose` 가 들지만 이 스칼라는 남는다 — [`core.analysis.inject`](../../../core/analysis/inject.py)
    가 mask 도 pose 도 디코드하지 않고 표본을 거르는 근거로 쓴다(그러려고 정본에 굳혀 둔 값이다).

    중심이나 ``shape`` 이 없으면 **걷는다** — 프레임 대각선으로 정규화하는 값이라 프레임 없이는 못
    만들고, 옛값을 남기면 크기가 바뀐 뒤에도 맞는 척한다.
    """
    _drop(obj, "center")                             # 옛 표현 — 자리는 이제 pose 가 든다
    if center is None or shape is None:
        _drop(obj, "center_offset")
        return
    _put(obj, "center_offset", _OFFSET_FMT, Center_offset(shape, center))


def Fit_pose(obj: Node, center: tuple[float, float] | None, spec: dict) -> bool:
    """③ ``pose`` 를 **②의 자리 + mask 주축각**으로 맞춘다. 고쳤으면 True.

    자리를 여기서 다시 구하지 않고 ②가 잰 중심을 받는다 — 정렬(`Order_by_center`)이 쓰는 점과 자세의
    자리가 **같은 점**이어야 "가까운 순"과 자세가 서로 다른 곳을 가리키지 않는다.

    회전의 근거는 mask 뿐이다 — 상자만 그린 객체는 **안 건드린다**(사람이 적어 둔 자세가 있으면 그게
    유일한 근거다). mask 가 있는데 비었거나 중심을 못 구했으면 걷는다.

    각은 flow 의 ``Radial_profile`` 과 **같은 사슬**에서 나온다(``spec`` 이 그 눈금) — 여기서 따로
    재면 사람이 적은 자세와 학습이 쓰는 정렬이 서로 다른 정면을 본다.

    **각의 신뢰도는 아직 안 적는다.** 사슬은 ``anisotropy``(주축이 실재하는가)와 ``flip_margin``
    (앞뒤 확정이 견고한가)을 함께 내는데, 원환·n≥3 회전대칭 부품에서는 전자가 **정확히 0** 이라 그
    각이 노이즈다. 지금은 자세 하나만 남기므로 **읽는 쪽이 그 사실을 알 길이 없다** — 함께 적을지는
    [`../TODO.md`](../TODO.md) 의 열린 질문이다.
    """
    _m = _mask_of(obj)
    if _m is None:
        return False                                 # 회전의 근거가 애초에 없다 — 손대지 않는다
    _out = profile.Chain_for(spec).Profile(_m) if center is not None else None
    if _out is None:                                 # mask 를 다 지웠다 — 자세도 근거가 없다
        _drop(obj, "pose")
        return True
    _put(obj, "pose", _POSE_FMT, pose.From_2d(center, _out[1][0]))
    return True


def Fit_profile(meta, key: str) -> int:
    """⑤ 이 stem 의 ``radial_rle`` 배열을 다시 뜬다 — **정렬이 끝난 뒤에** 부른다. 쓴 행 수 반환.

    **행이 곧 obj_id 라서 순서가 확정돼야 한다** — ``Reorder`` 가 번호를 다시 매기므로 그 전에 쓰면
    행과 객체가 어긋난다. 그래서 트리 노드가 아니라 **store 에서 다시 읽는다**(재부여 후의 진실).

    눈금은 정본 ``params/profile_spec`` 이 답한다 — 없으면 유닛 기본값으로 뽑고 **그 값을 적어 둔다**.
    눈금이 다른 배열은 같은 자 위에 있지 않으므로, 한 객체만 다시 뽑을 때도 처음 쓴 눈금이어야 한다.

    객체가 없거나 mask 가 하나도 없으면 **leaf 를 걷는다** — 근거가 사라졌는데 옛 배열을 남기면 다음에
    여는 사람이 그게 낡았다는 걸 알 길이 없다(``bbox``·``pose`` 와 같은 규칙).

    Args:
        meta: 정본 store (``Dataset_Meta``).
        key: 이 stem 의 item key.

    Returns:
        배열에 담긴 행 수 (= 마지막 obj_id + 1). 걷었으면 0.
    """
    _path = meta.Item_path(key)
    _item = meta.Find(key)
    if _path is None or _item is None:
        return 0
    _objs = {int(_i): _o for _i, _o in _item.Branches().items() if str(_i).isdigit()}
    _masks: list[np.ndarray | None] = []
    for _i in range(max(_objs) + 1 if _objs else 0):
        _val = _objs[_i].Attr("mask", None) if _i in _objs else None
        _masks.append(rle.To_mask(_val) if isinstance(_val, dict) else None)

    _spec = meta.Param(profile.SPEC_PARAM) or profile.Default_spec()
    _stack = profile.Stack(_masks, profile.Chain_for(_spec)) if _masks else None
    if _stack is None:                               # 뜰 근거가 없다 — 옛 배열을 남기지 않는다
        if _item.Get(profile.LEAF) is not None:
            meta.Delete_node(tuple(_path), profile.LEAF)
        return 0
    if meta.Param(profile.SPEC_PARAM) is None:       # 무엇으로 뽑았는지를 정본이 스스로 답하게
        meta.Put_param(profile.SPEC_PARAM, dict(_SPEC_PARAM_SPEC), dict(_spec))
    meta.Add_leaf(tuple(_path), profile.LEAF, dict(profile.LEAF_SPEC), _stack)
    return int(_stack.shape[0])


def Normalize(objects: list[Node], shape: tuple[int, int] | None,
              spec: dict | None = None) -> list[str]:
    """네 가지를 한 번에 — ``(bbox 맞춤 → 중심 재기 → offset·pose 얹기 → 정렬 순서)``.

    Args:
        objects: 이 stem 의 객체 노드들 (트리 순서 그대로).
        shape: 프레임 ``(H, W)``. 없으면 ``center_offset`` 과 정렬을 건너뛴다.
        spec: 자세를 잴 눈금 (정본 ``params/profile_spec``). 없으면 유닛 기본값.

    Returns:
        ``obj_id`` 를 **이미지 중심에서 가까운 순**으로 나열한 목록. 위치를 못 구한 객체는 여기
        안 들어가는데, ``store.Reorder`` 가 목록에 없는 자식을 **원래 순서로 뒤에 붙이므로**
        사라지지 않는다 — flow 의 ``Order_objects`` 는 그것들을 떨구지만 여기서는 안 된다
        (편집 중인 정본에서 객체가 조용히 없어지면 안 되므로).
        정렬할 것이 없으면 빈 목록.
    """
    _spec = spec or profile.Default_spec()
    _centers: list[tuple[float, float] | None] = []
    for _o in objects:
        Fit_bbox(_o)
        _c = Center_of(_o)
        Fit_offset(_o, shape, _c)
        Fit_pose(_o, _c, _spec)
        _centers.append(_c)
    if shape is None or not any(_c is not None for _c in _centers):
        return []
    return [objects[_i].name for _i in Order_by_center(shape, _centers)]
