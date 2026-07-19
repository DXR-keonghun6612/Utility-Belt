from __future__ import annotations

from dataclasses import dataclass

from ....schema import Data_Ref
from ....func.cv.geom import Box_within_roi
from .. import PROCESS_REGISTRY, Base_Process, BBOX, GRAY_IMAGE


def _bbox(obj: Data_Ref) -> list[float] | None:
    """object 의 ``bbox`` 인라인 값 ``[x0,y0,x1,y1]`` (없거나 형식 불량이면 None)."""
    _v = obj.Attr("bbox", None)
    if not (isinstance(_v, (list, tuple)) and len(_v) == 4):
        return None
    return [float(_x) for _x in _v]


@PROCESS_REGISTRY.Register_module()
@dataclass
class Filter_by_roi(Base_Process, outputs=("object",), category="마스크/분리"):
    """roi 밖에 걸치는 객체를 목록에서 **통째** 제거한다 (bbox 가 roi 외접박스에 완전히 들 때만 유지).

    ``unit: frame`` — ctx 의 ``object``(프레임 객체 목록)에서 roi 외접박스를 벗어나는 것을 떨군다. detect
    등이 프레임 전체를 보고 만든 객체 중 **관심영역 밖 검출을 걸러내는** 자리다. 픽셀을 잘라 남기지 않고
    인스턴스째 제거한다 — 경계에 걸친 검출은 관심영역의 것이 아니다.

    **bbox 로 판정하는 것이 mask 로 판정하는 것과 같다** — detect·split 의 bbox 는 mask 의 tight 외접
    박스라 "bbox 가 roi 밖" ⟺ "mask 가 roi 밖"이다. roi 는 대략적 한정이라 그 외접박스로 본다
    (``func.cv.geom.Box_within_roi``). ``roi``(params)는 producer 없이 엔진이 ctx 로 얹는다. roi 가 없으면
    전부 유지, 객체가 없으면 빈 dict("스킵").

    걸러낸 목록만 ``object`` 로 내므로 sink(``Replace_branches``)가 정본 객체 집합을 교체한다 — 모두
    제거되면 빈 리스트가 되어 정본이 비워진다(LEAF 는 보존). 라벨맵 ``segment``(쓰는 flow 라면)의 정합·
    재라벨은 downstream ``order_objects`` 가 맡는다 — 여긴 목록만 손댄다.
    """

    def Run(self, object: list[Data_Ref],
            roi: BBOX | GRAY_IMAGE | None = None, **kwargs) -> dict:
        if not object:
            return {}
        _kept = [_o for _o in object if Box_within_roi(_bbox(_o), roi)]
        return {"object": _kept}
