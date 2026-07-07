from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from ..utils.mask import Roi_to_box, Threshold_hysteresis
from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, BBOX, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Threshold_score(Base_Process, outputs=("mask",), category="마스크/이진화"):
    """스코어/거리 맵 ``dist`` 를 임계(+hysteresis +면적 +ROI)로 이진화해 mask 를 만든다.

    ``invert=True`` 면 스코어 작은 픽셀이 전경(배경 추출, hysteresis 방향도 반전). 적용 순서
    (strong→면적→weak)·용례는 ``README.md``. 결과가 비면 빈 dict("스킵").
    """

    k:        Annotated[float,        UI(label="k (strong 임계, σ배수)", min=0.1, max=10.0, step=0.05)] = 1.2
    k_weak:   Annotated[float | None, UI(label="k_weak (hysteresis)",   min=0.1, max=10.0, step=0.05)] = None
    invert:   Annotated[bool,         UI(label="배경 추출 (전경↔배경 반전)")]                            = False
    min_area: Annotated[int,          UI(label="최소 영역 크기 (px², 0=하한없음)", min=0, max=100000,  step=1)] = 0
    max_area: Annotated[int,          UI(label="최대 영역 크기 (px², 0=상한없음)", min=0, max=1000000, step=1)] = 0

    def Run(
        self, dist: np.ndarray,
        roi: BBOX | GRAY_IMAGE | None = None, **kwargs,
    ) -> dict:
        _max_area = self.max_area or None        # 0 = 상한 없음
        if self.invert:  # 배경: 스코어 작은 픽셀 — -dist 에 음수 임계로 hysteresis 반전
            _k  = -self.k if self.k_weak is None else -self.k_weak
            _kw = None    if self.k_weak is None else -self.k
            _obj = Threshold_hysteresis(-dist, _k, _kw, self.min_area, _max_area)
        else:            # 전경: 스코어 큰 픽셀 = 객체
            _obj = Threshold_hysteresis(dist, self.k, self.k_weak, self.min_area, _max_area)

        if roi is not None:
            _box = Roi_to_box(roi)
            if _box is None:
                return {}
            _y0, _y1, _x0, _x1 = _box
            _roi_mask = np.zeros(_obj.shape, np.uint8)
            _roi_mask[_y0:_y1, _x0:_x1] = 255
            _obj = cv2.bitwise_and(_obj, _roi_mask)

        if not _obj.any():
            return {}
        return {"mask": _obj}
