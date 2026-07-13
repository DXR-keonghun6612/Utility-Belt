from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ...func.cv.filter import Band_threshold, Threshold_signed
from ...func.cv.geom import Mask_within_roi
from .. import PROCESS_REGISTRY, Base_Process, UI, BBOX, IMAGE, GRAY_IMAGE


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


@PROCESS_REGISTRY.Register_module()
@dataclass
class Intensity_band(Base_Process, outputs=("mask",), category="마스크/이진화"):
    """gray 값이 ``[low, high]`` 밴드 안인 픽셀만 골라 mask 를 만든다 — ``func.cv.filter.Band_threshold``.

    ``Threshold_score`` 와 달리 스코어가 아니라 **절대 밝기 밴드**다: 아래로 어두운 배경, 위로 포화된
    광원(255)을 함께 잘라 물체 반사 띠만 남긴다(무채색 씬). 입력은 채널 무관 ``IMAGE`` 라 gray·다채널을
    함께 받고, 다채널은 gray 로 접는다. ROI 밖은 버린다. 결과가 비면 빈 dict("스킵").

    잡티 제거(면적 하한·morphology)는 이 유닛의 일이 아니다 — 뒤에 ``morph_mask``(OPEN)를 잇는다.
    """

    low:  Annotated[int, UI(label="하단 임계 (이보다 어두우면 버림)", min=0, max=255)]   = 180
    high: Annotated[int, UI(label="상단 임계 (이보다 밝으면=광원 버림)", min=0, max=255)] = 254

    def Run(self, frame: IMAGE, roi: BBOX | GRAY_IMAGE | None = None, **kwargs) -> dict:
        _m = Band_threshold(frame, low=self.low, high=self.high)
        if roi is not None:
            _m = Mask_within_roi(_m, roi)
            if _m is None:
                return {}
        return {"mask": _m} if _m.any() else {}
