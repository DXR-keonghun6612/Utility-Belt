from __future__ import annotations

from dataclasses import dataclass

from ....schema import Data_Ref
from ...func.mask.instance import Order_by_center
from .. import PROCESS_REGISTRY, Base_Process, GRAY_IMAGE


def _bbox(obj: Data_Ref) -> list[float] | None:
    """object 의 ``bbox`` 인라인 값 ``[x0,y0,x1,y1]`` (없거나 형식 불량이면 None)."""
    _v = obj.Attr("bbox", None)
    if not (isinstance(_v, (list, tuple)) and len(_v) == 4):
        return None
    return [float(_x) for _x in _v]


@PROCESS_REGISTRY.Register_module()
@dataclass
class Order_objects(Base_Process, outputs=("segment", "object"), category="마스크/분리"):
    """객체를 **이미지 중심에서 가까운 순**으로 정렬해 ``obj_id`` 를 0부터 다시 부여한다.

    정렬·재라벨 계산은 ``func.mask.instance.Order_by_center``(self-heal 규칙 포함). 이 유닛은 객체
    컨테이너에서 bbox 를 꺼내 넘기고, 돌려받은 순서로 객체 리스트를 다시 세우는 일만 한다.
    ``class_id``·bbox 등 객체 데이터는 그대로 유지된다. 객체가 없으면 빈 dict("스킵").

    **라벨맵에 자리가 없는 객체는 여기서 제거된다** — 편집이 남긴 빈 객체(bbox 를 안 그렸거나 mask 가
    빈 것)가 그것이다. 그래서 이 유닛이 도는 자리(= 명시적 저장)가 곧 **정합을 되찾는 자리**다:
    obj_id 의 구멍은 압축되고, 유령 객체는 사라진다.
    """

    def Run(self, segment: GRAY_IMAGE, object: list[Data_Ref], **kwargs) -> dict:
        if not object:
            return {}

        _seg, _order = Order_by_center(segment, [_bbox(_o) for _o in object])
        _new = [Data_Ref(info=dict(object[_i].info)) for _i in _order]
        return {"segment": _seg, "object": _new}
