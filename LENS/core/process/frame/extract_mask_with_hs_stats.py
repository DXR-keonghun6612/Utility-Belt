"""HS 배경 통계 기반 단일 프레임 객체 마스크 추출 process."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

import cv2
import numpy as np

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process, BBOX
from ..utils.color import Hs_distance, HS_stats
from ..utils.mask import Make_morph_kernel


NAME = "extract_mask_hs"


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _Segment_foreground(
    sub_img: np.ndarray,
    bg_stats: HS_stats,
    k: float,
    k_weak: float | None,
) -> np.ndarray:
    """HS 거리 임계값으로 전경 마스크를 생성한다. hysteresis 옵션 지원."""
    _hsv    = cv2.cvtColor(sub_img, cv2.COLOR_BGR2HSV).astype(np.float32)
    _d      = Hs_distance(_hsv[..., 0], _hsv[..., 1], bg_stats)
    _strong = (_d > k).astype(np.uint8)

    if k_weak is None or k_weak >= k:
        return np.where(_strong > 0, np.uint8(255), np.uint8(0))

    _weak = (_d > k_weak).astype(np.uint8)
    _, _lbl = cv2.connectedComponents(_weak, connectivity=8)
    _keep = np.unique(_lbl[_strong > 0])
    _keep = _keep[_keep != 0]
    if _keep.size == 0:
        return np.zeros_like(_strong)
    return np.isin(_lbl, _keep).astype(np.uint8) * np.uint8(255)


def _Pick_center_object(mask: np.ndarray, min_contour_area: int) -> np.ndarray | None:
    """centroid가 mask 중심에 가장 가까운 단일 객체를 선택한다."""
    _contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not _contours:
        return None
    _contours = [c for c in _contours if cv2.contourArea(c) >= min_contour_area]
    if not _contours:
        return None
    _h, _w = mask.shape
    _cx_img, _cy_img = _w / 2.0, _h / 2.0
    _best_idx, _best_d = 0, float("inf")
    for _i, _c in enumerate(_contours):
        _M = cv2.moments(_c)
        if _M["m00"] == 0:
            continue
        _d = (_M["m10"] / _M["m00"] - _cx_img) ** 2 + (_M["m01"] / _M["m00"] - _cy_img) ** 2
        if _d < _best_d:
            _best_d, _best_idx = _d, _i
    _sel = np.zeros_like(mask)
    cv2.drawContours(_sel, _contours, _best_idx, 255, cv2.FILLED)
    return cv2.bitwise_and(mask, _sel)


# ── Config ────────────────────────────────────────────────────────────────────

@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Extract_mask_hs_config(Base_Config):
    """HS 기반 마스크 추출 파라미터."""

    config_type: str = f"{NAME}_config"
    object_type: str = NAME

    k: float = field(default=1.5, metadata={"ui": {
        "label": "k  (strong 임계)",
        "tip": "배경 HS 거리 > k 인 픽셀을 전경으로 판정",
        "min": 0.1, "max": 5.0, "step": 0.05,
    }})
    k_weak: float | None = field(default=None, metadata={"ui": {
        "label": "k_weak  (hysteresis)",
        "tip": "strong mask에 연결된 weak 픽셀 포함. None이면 hard threshold",
        "min": 0.1, "max": 5.0, "step": 0.05,
    }})
    min_contour_area: int = field(default=200, metadata={"ui": {
        "label": "객체 후보 최소 면적 (px²)",
        "tip": "이 면적 미만 컨투어는 노이즈로 제외",
        "min": 0, "max": 10000,
    }})
    morph_close_size: int = field(default=3, metadata={"ui": {
        "label": "CLOSE 커널 크기 (px)",
        "tip": "작은 구멍 메우기",
        "min": 1, "max": 21,
    }})
    morph_open_size: int = field(default=3, metadata={"ui": {
        "label": "OPEN 커널 크기 (px)",
        "tip": "잔류 노이즈 제거",
        "min": 1, "max": 21,
    }})


# ── Process ───────────────────────────────────────────────────────────────────

@pipeline_registry.Register_module(NAME)
@dataclass
class Extract_mask_hs_process(Base_Process):
    """HS 배경 통계로 단일 프레임에서 전경 객체 마스크를 추출한다."""

    name:             str         = NAME
    k:                float       = 1.2
    k_weak:           float | None = None
    min_contour_area: int         = 200
    morph_close_size: int         = 3
    morph_open_size:  int         = 3

    INPUTS:  ClassVar[tuple[str, ...]] = ("frame", "roi", "bg_stats")
    OUTPUTS: ClassVar[tuple[str, ...]] = ("mask",)

    def Run(
        self,
        frame:    np.ndarray,
        roi:      BBOX,
        bg_stats: HS_stats,
        **kwargs,
    ) -> dict[str, np.ndarray]:
        _y, _x, _h, _w = roi
        _sub = frame[_y:_y + _h, _x:_x + _w]

        _fg = _Segment_foreground(_sub, bg_stats, self.k, self.k_weak)
        _fg = cv2.morphologyEx(_fg, cv2.MORPH_CLOSE, Make_morph_kernel(self.morph_close_size))
        _fg = cv2.morphologyEx(_fg, cv2.MORPH_OPEN,  Make_morph_kernel(self.morph_open_size))

        _mask = _Pick_center_object(_fg, self.min_contour_area)
        if _mask is None:
            return {}
        return {"mask": _mask}
