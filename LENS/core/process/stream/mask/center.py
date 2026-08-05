from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ....schema import Build, Data_Ref
from ....format import rle
from ....func.cv.geom import Box_center, Center_offset, Mask_centroid
from .. import PROCESS_REGISTRY, Base_Process


def _center_of(obj: Data_Ref) -> tuple[float, float] | None:
    """객체 무게중심 ``(cx, cy)`` — 자기 mask 우선(rle 무게중심), 없으면 bbox 중앙, 그것도 없으면 None.

    ``Order_objects._center_of`` 와 같은 규약이다 — 정렬의 기준과 저장되는 값이 다르면 "가까운 순"과
    "중심에서 얼마"가 어긋난다.
    """
    _m = obj.Attr("mask", None)
    if isinstance(_m, dict):                             # 인라인 rle mask
        _c = Mask_centroid(rle.To_mask(_m))
        if _c is not None:
            return _c
    _b = obj.Attr("bbox", None)
    if isinstance(_b, (list, tuple)) and len(_b) == 4:
        return Box_center([float(_x) for _x in _b])
    return None


@PROCESS_REGISTRY.Register_module()
@dataclass
class Mask_center(Base_Process, outputs=("object",), category="마스크/분리"):
    """객체마다 mask 무게중심을 재서 ``center`` · ``center_offset`` 인라인 값으로 **얹는다**.

    mask 를 안 바꾼다 — 이미 있는 사실(무게중심)을 **읽을 수 있는 자리로 옮기는** 유닛이다. 무게중심은
    rle 를 풀어야 나오는데, 하류(분석 순회 등)가 그걸 매번 풀면 6만 객체에서 순회가 인메모리라 싸다는
    성질이 깨진다. 그래서 만들 때 한 번 재어 ``class_id``·``bbox`` 옆에 인라인으로 둔다.

    두 값을 함께 두는 이유:

    - ``center`` — ``[cx, cy]`` 원본 픽셀 좌표. 위치 그 자체(오버레이·정렬·재계산의 근거).
    - ``center_offset`` — 이미지 중심에서의 거리를 **대각선으로 정규화**한 ``[0, 1]``
      (:func:`~core.func.cv.geom.Center_offset`). ``center`` 에서 파생되지만, 파생하려면 **프레임
      크기**가 있어야 한다. 그 크기는 정본 어디에도 인라인으로 없어서 하류가 알려면 이미지를 열어야
      한다 — 6만 프레임에서 그건 못 한다. 그래서 프레임을 이미 든 여기서 굳힌다.

    ``unit: frame`` — 프레임 크기를 ``frame`` 에서 얻는다(shape 만 쓴다). 무게중심을 못 구한 객체는
    두 값 없이 원본 그대로 물려준다(조용히 0 을 넣지 않는다 — 부재와 "중심에 있음"은 다르다).
    프레임이 없으면 ``center`` 만 얹고 ``center_offset`` 은 생략한다. 객체가 없으면 빈 dict("스킵").
    """

    def Run(self, object: list[Data_Ref], frame: np.ndarray | None = None, **kwargs) -> dict:
        if not object:
            return {}
        _shape = frame.shape[:2] if frame is not None else None
        _new: list[Data_Ref] = []
        for _o in object:
            _c = _center_of(_o)
            if _c is None:                               # 잴 근거가 없다 — 원본 그대로
                _new.append(_o)
                continue
            _add = {"center": {"format": ("", "list"),
                               "info": {"value": [float(_c[0]), float(_c[1])]}}}
            if _shape is not None:
                _add["center_offset"] = {"format": ("", "float"),
                                         "info": {"value": Center_offset(_shape, _c)}}
            _new.append(Data_Ref(info={**dict(_o.info), **Build(_add)}))
        return {"object": _new}
