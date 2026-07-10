from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ...func.cv.filter import Threshold_signed
from ...func.cv.geom import Mask_within_roi
from .. import PROCESS_REGISTRY, Base_Process, UI, BBOX, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Threshold_score(Base_Process, outputs=("mask",), category="마스크/이진화"):
    """스코어/거리 맵 ``dist`` 를 임계(+hysteresis +면적 +ROI)로 이진화해 mask 를 만든다.

    이진화는 ``func.cv.filter.Threshold_signed``(적용 순서 strong→면적→weak, ``invert`` 부호 규칙),
    ROI 한정은 ``func.cv.geom.Mask_within_roi``(외접 박스). 결과가 비면 빈 dict("스킵").
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
        _obj = Threshold_signed(
            dist, k=self.k, k_weak=self.k_weak, invert=self.invert,
            min_area=self.min_area, max_area=self.max_area or None)   # 0 = 상한 없음

        if roi is not None:
            _obj = Mask_within_roi(_obj, roi)
            if _obj is None:
                return {}

        return {"mask": _obj} if _obj.any() else {}
