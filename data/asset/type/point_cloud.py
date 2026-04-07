from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from data.asset.type.base import Base_Asset


@dataclass
class PointCloud_Asset(Base_Asset):
    """3D 점군(Point Cloud) 데이터를 보유하는 에셋.

    정점 좌표 배열과 선택적 색상/법선 배열을 담으며,
    faces 없이 점 단위로만 구성된 비정형 데이터를 표현함.
    """
    # (N, 3) 점 좌표 배열
    points: np.ndarray | None = field(default=None, repr=False)
    # (N, 3) RGB 색상 배열 (0~255, uint8) — 선택적
    colors: np.ndarray | None = field(default=None, repr=False)
    # (N, 3) 법선 벡터 배열 — 선택적
    normals: np.ndarray | None = field(default=None, repr=False)

    __exclude_serialize__: ClassVar[set[str]] = {"points", "colors", "normals"}

    @property
    def count(self) -> int:
        """보유한 점의 총 개수를 반환함."""
        if self.points is None:
            return 0
        return len(self.points)
