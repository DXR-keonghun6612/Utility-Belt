"""단일 프레임 H·S 픽셀 추출 process."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

import cv2
import numpy as np

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process, GRAY_IMAGE, BBOX
from ..utils.color import Hs_distance


NAME = "extract_hs"

# ── Config ────────────────────────────────────────────────────────────────────

@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Extract_hs_config(Base_Config):
    """H·S 픽셀 추출 파라미터.

    Attributes:
        threshold: inlier 판정 HS 거리 임계값.
        min_pixels: 유효 inlier 픽셀 최솟값. 미달 시 None 반환.
    """

    config_type: str = f"{NAME}_config"
    object_type: str = NAME

    threshold: float = field(default=2.0, metadata={"ui": {
        "label": "HS 거리 임계값",
        "tip": "초기 mean으로부터 이 거리 이내 픽셀만 inlier로 선택",
        "min": 0.5, "max": 5.0, "step": 0.1,
    }})
    min_pixels: int = field(default=100, metadata={"ui": {
        "label": "최소 픽셀 수",
        "tip": "inlier 픽셀이 이 수 미만이면 None 반환",
        "min": 10, "max": 1000,
    }})


# ── Process ───────────────────────────────────────────────────────────────────

@pipeline_registry.Register_module(NAME)
@dataclass
class Extract_hs_process(Base_Process):
    """단일 프레임에서 ROI 내 배경 H·S 픽셀을 추출한다.

    roi가 np.ndarray면 mask > 0 영역, tuple이면 (y, x, h, w) bbox 영역에서 추출.
    초기 mean/std 기준 HS 거리로 outlier를 제거해 배경 픽셀만 반환한다.

    Attributes:
        threshold: inlier 판정 HS 거리 임계값.
        min_pixels: 유효 inlier 픽셀 최솟값.
    """

    name:       str   = NAME
    threshold:  float = 2.0
    min_pixels: int   = 100

    INPUTS:  ClassVar[tuple[str, ...]] = ("frame", "roi")
    OUTPUTS: ClassVar[tuple[str, ...]] = ("h", "s")

    def Run(
        self, frame: np.ndarray, roi: GRAY_IMAGE | BBOX | None = None,
        **kwargs,
    ) -> dict[str, np.ndarray]:
        """ROI에서 배경 H·S 픽셀을 추출한다.

        roi 미제공 시 kwargs["mask"] → kwargs["bg_roi"] 순으로 fallback한다.

        Args:
            frame: BGR 이미지.
            roi:   binary mask (H, W) 또는 bbox (y, x, h, w). None 허용.

        Returns:
            {"h": inlier H픽셀, "s": inlier S픽셀}. 유효 픽셀 부족 시 None.
        """
        _roi = roi if roi is not None else kwargs.get("mask") or kwargs.get("bg_roi")
        if _roi is None:
            return {}
        _hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        _h, _s = self._Extract(_hsv, _roi)

        if _h.size < self.min_pixels:
            return {}

        return self._Filter_inliers(_h, _s)


    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _Extract(
        hsv: np.ndarray, roi: GRAY_IMAGE | BBOX
    ) -> tuple[np.ndarray, np.ndarray]:
        if isinstance(roi, np.ndarray):
            _mask = roi > 0
            return hsv[..., 0][_mask], hsv[..., 1][_mask]
        _y, _x, _h, _w = roi
        _region = hsv[_y:_y + _h, _x:_x + _w]
        return _region[..., 0].ravel(), _region[..., 1].ravel()

    def _Filter_inliers(
        self, h: np.ndarray, s: np.ndarray
    ) -> dict[str, np.ndarray]:
        _mask = Hs_distance(h, s) < self.threshold
        _h_in, _s_in = h[_mask], s[_mask]

        if _h_in.size < self.min_pixels:
            return {}
        return {"h": _h_in, "s": _s_in}
