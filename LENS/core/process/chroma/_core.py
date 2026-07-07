"""채널 거리 계산 유틸리티 (색공간 무관)."""

from __future__ import annotations

import numpy as np


def Cyclic_delta(values: np.ndarray, mu: float | np.ndarray, period: int) -> np.ndarray:
    """순환 채널(예: hue)의 wrap 보정 거리. ``mu`` 는 스칼라/배열 모두 허용(브로드캐스팅)."""
    d = np.abs(values - mu)
    return np.minimum(d, period - d)


def Channel_delta(
    values: np.ndarray, mu: float | np.ndarray, circular: bool, period: int
) -> np.ndarray:
    """채널 한 개의 평균 대비 편차. ``circular`` 이면 wrap 보정, 아니면 단순 차분."""
    if circular:
        return Cyclic_delta(values, mu, period)
    return values - mu
