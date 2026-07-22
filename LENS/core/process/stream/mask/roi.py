from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from ....schema import Data_Ref
from ....func.cv.geom import Box_roi_overlap
from .. import PROCESS_REGISTRY, Base_Process, UI, BBOX, GRAY_IMAGE


def _bbox(obj: Data_Ref) -> list[float] | None:
    """object 의 ``bbox`` 인라인 값 ``[x0,y0,x1,y1]`` (없거나 형식 불량이면 None)."""
    _v = obj.Attr("bbox", None)
    if not (isinstance(_v, (list, tuple)) and len(_v) == 4):
        return None
    return [float(_x) for _x in _v]


@PROCESS_REGISTRY.Register_module()
@dataclass
class Filter_by_roi(Base_Process, outputs=("object",), category="마스크/분리"):
    """roi 와 겹치는 비율이 ``min_overlap`` 미만인 객체를 목록에서 **통째** 제거한다.

    ``unit: frame`` — ctx 의 ``object``(프레임 객체 목록)에서 각 bbox 가 roi 외접박스와 겹치는 면적
    비율(bbox 면적 대비)을 재, ``min_overlap`` 미만이면 떨군다. detect 등이 프레임 전체를 보고 만든 객체
    중 **관심영역에 충분히 안 든 검출을 걸러내는** 자리다. 픽셀을 잘라 남기지 않고 인스턴스째 제거한다.

    **"조금이라도 밖에 걸치면 제거"가 아니라 겹침 비율로 판정한다** — 경계에 살짝 물린 검출은 남기고
    대부분 밖으로 나간 것만 떨군다. ``min_overlap=1.0`` 이면 완전히 든 것만(옛 동작), ``0.0`` 이면 전부 유지.

    **bbox 로 판정하는 것이 mask 로 판정하는 것과 같다** — detect·split 의 bbox 는 mask 의 tight 외접
    박스다. roi 는 대략적 한정이라 그 외접박스로 본다(``func.cv.geom.Box_roi_overlap``). ``roi``(params)는
    producer 없이 엔진이 ctx 로 얹는다. roi 가 없으면 전부 유지, 객체가 없으면 빈 dict("스킵").

    걸러낸 목록만 ``object`` 로 내므로 sink(``Replace_branches``)가 정본 객체 집합을 교체한다 — 모두
    제거되면 빈 리스트가 되어 정본이 비워진다(LEAF 는 보존). 객체가 자기 mask 를 들므로 목록만 손대면
    되고, 라벨맵 재sync 같은 뒤처리가 없다.
    """

    min_overlap: Annotated[float, UI(label="roi 겹침 최소 비율 (0~1)",
                                     tip="bbox 면적 중 roi 안에 드는 비율이 이 값 미만이면 인스턴스째 제거",
                                     min=0.0, max=1.0, step=0.05)] = 0.8

    def Run(self, object: list[Data_Ref],
            roi: BBOX | GRAY_IMAGE | None = None, **kwargs) -> dict:
        if not object:
            return {}
        _kept = [_o for _o in object
                 if Box_roi_overlap(_bbox(_o), roi) >= self.min_overlap]
        return {"object": _kept}
