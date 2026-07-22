from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ....schema import Data_Ref
from ....format import rle
from ....func.cv.geom import Box_center, Mask_centroid
from ....func.mask.instance import Order_by_center
from .. import PROCESS_REGISTRY, Base_Process


def _bbox(obj: Data_Ref) -> list[float] | None:
    """object 의 ``bbox`` 인라인 값 ``[x0,y0,x1,y1]`` (없거나 형식 불량이면 None)."""
    _v = obj.Attr("bbox", None)
    if not (isinstance(_v, (list, tuple)) and len(_v) == 4):
        return None
    return [float(_x) for _x in _v]


def _center_of(obj: Data_Ref) -> tuple[float, float] | None:
    """객체 무게중심 ``(cx, cy)`` — 자기 mask 우선(rle 무게중심), 없으면 bbox 중앙, 그것도 없으면 None.

    객체가 자기 ``mask`` 를 든다(mask 도메인) — in-flow ctx 값은 인라인 rle 라 그걸 풀어 전경 무게중심을
    쓴다. mask 가 없거나 비면 bbox 중앙으로 떨어진다.
    """
    _m = obj.Attr("mask", None)
    if isinstance(_m, dict):                             # 인라인 rle mask
        _c = Mask_centroid(rle.To_mask(_m))
        if _c is not None:
            return _c
    _b = _bbox(obj)
    return Box_center(_b) if _b is not None else None


@PROCESS_REGISTRY.Register_module()
@dataclass
class Order_objects(Base_Process, outputs=("object",), category="마스크/분리"):
    """객체를 **mask 무게중심이 이미지 중심에서 가까운 순**으로 정렬해 목록을 다시 세운다.

    정렬 계산은 ``func.mask.instance.Order_by_center``. 이 유닛은 객체별 무게중심(``_center_of``: 자기
    rle mask → bbox 중앙 순)을 넘기고, 돌려받은 순서로 객체 리스트를 다시 세운다. ``class_id``·bbox·mask
    등 객체 데이터는 그대로 물려주고, 위치를 못 구한 객체는 정렬 근거가 없어 떨어진다. obj_id 는 sink 가
    순번으로 부여한다. 객체가 없으면 빈 dict("스킵").

    거리 기준인 이미지 크기는 ``frame`` 에서 얻는다(shape 만 쓴다). 라벨맵을 안 보므로 객체가 각자 mask 를
    드는 정본 모델과 그대로 맞는다 — 뒤처리(재sync) 단계가 없다.
    """

    def Run(self, object: list[Data_Ref], frame: np.ndarray | None = None, **kwargs) -> dict:
        if not object:
            return {}
        if frame is None:                                # 정렬 기준(이미지 크기)이 없다
            return {}
        _order = Order_by_center(frame.shape[:2], [_center_of(_o) for _o in object])
        _new = [Data_Ref(info=dict(object[_i].info)) for _i in _order]
        return {"object": _new}
