"""mask/area — (h, w) Cartesian 영역 속성. centroid 가 여기 기준점.

다른 모듈(예: ``mask.align``, ``mask.shape``)이 원점으로 쓰는 무게중심을 여기서 단일 정의한다.
area·bbox 등 크기/채움 계열 특징도 이 모듈로 모은다 (확장 예정).
"""

from __future__ import annotations

import numpy as np


def centroid(mask: np.ndarray) -> tuple[float, float]:
    """이진 mask 의 면적 무게중심 ``(cx, cy)`` (h,w 픽셀 좌표, x=열·y=행)."""
    _ys, _xs = np.nonzero(mask > 0)
    if _ys.size == 0:
        raise ValueError("빈 mask")
    return float(_xs.mean()), float(_ys.mean())


def area(mask: np.ndarray) -> int:
    """전경 픽셀 수 (raw, px²; 물리단위는 pixel_size² 를 곱해 환산)."""
    return int(np.count_nonzero(mask > 0))
