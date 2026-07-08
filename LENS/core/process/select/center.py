"""중심거리 측정 — object 중심이 이미지 중심에서 얼마나 떨어졌나 (대각선 정규화 [0,1]).

Run(unit=object)에서 프레임 이미지 크기 + object 위치(mask centroid 우선, 없으면 bbox center)로 거리를
재 ``center_dist`` attr 로 낸다 — **측정은 정본(Run)**, 그 값으로 거르는 **선택은 gate**([`gate.py`](gate.py))가
Sample 에서 한다(경계 규칙: 정본은 손실 없이, 파생이 솎아냄). ``max_dist`` 를 주면 Run 에서도 gate 로 쓴다.
``Order_objects``(mask/order.py)의 중심거리 정렬과 같은 기하 — 이쪽은 값을 attr 로 남기는 측정 유닛.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, BBOX, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Center_distance(Base_Process, outputs=("center_dist",), category="선택/게이트"):
    """object 중심 ↔ 이미지 중심 거리(대각선 정규화)를 ``center_dist`` 로 낸다.

    중심은 ``mask``(전경 픽셀 무게중심) 우선, 없으면 ``bbox``([x0,y0,x1,y1]) 중앙. 이미지 크기는 ``frame``
    (shape 만 사용). ``max_dist`` 지정 시 초과하면 빈 dict("스킵") — Run 에서 바로 게이트도 된다(측정만
    원하면 미지정). mask·bbox 둘 다 없으면 스킵.
    """

    max_dist: Annotated[float | None, UI(label="최대 거리 (0~1, 초과 시 스킵)", min=0.0, max=1.0, step=0.01)] = None

    def Run(self, frame: np.ndarray,
            mask: GRAY_IMAGE | None = None, bbox: BBOX | None = None, **kwargs) -> dict:
        _h, _w = frame.shape[:2]
        if mask is not None and np.any(mask):
            _ys, _xs = np.nonzero(mask)
            _cx, _cy = float(_xs.mean()), float(_ys.mean())
        elif bbox is not None and len(bbox) == 4:
            _cx, _cy = (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0
        else:
            return {}                                    # 위치 정보 없음 → 스킵
        _dist = float(np.hypot(_cx - _w / 2.0, _cy - _h / 2.0) / np.hypot(_w, _h))
        if self.max_dist is not None and _dist > self.max_dist:
            return {}                                    # Run 게이트 (측정+거르기 겸용)
        return {"center_dist": _dist}
