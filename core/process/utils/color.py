"""H·S 거리 계산 유틸리티."""

from __future__ import annotations
from dataclasses import dataclass

import numpy as np


@dataclass
class HS_stats:
    """배경 H·S 통계 컨테이너."""

    mean_h: float
    mean_s: float
    std_h:  float
    std_s:  float


def Hue_delta(h: np.ndarray, mu: float) -> np.ndarray:
    """OpenCV hue(0~179) 순환 거리."""
    d = np.abs(h - mu)
    return np.minimum(d, 180.0 - d)


def Hs_distance(
    h: np.ndarray, s: np.ndarray, base_line: HS_stats | None = None
) -> np.ndarray:
    """H·S 정규화 거리. d = √((ΔH/σH)² + (ΔS/σS)²)

    h, s는 pixel array (N,) 또는 spatial array (H, W) 모두 허용.
    """
    if base_line is None:
        _h_mean, _s_mean= h.mean(), s.mean()
        _h_std, _s_std = s.std(), s.std()

    else:
        _h_mean, _s_mean= base_line.mean_h, base_line.mean_s
        _h_std, _s_std = base_line.std_h, base_line.std_s

    _dh = Hue_delta(h, _h_mean)
    _ds = s - _s_mean
    return np.sqrt(
        (_dh / max(_h_std, 1e-6)) ** 2 + (_ds / max(_s_std, 1e-6)) ** 2)