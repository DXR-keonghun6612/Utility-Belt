from __future__ import annotations
from dataclasses import dataclass

from python_toolbox.project import Base_Config


@dataclass
class Camera_Intrinsic(Base_Config):
    """물리 카메라 모델의 광학 파라미터 정의."""

    fov: float = 60.0          # 수직 화각 (degrees)
    near_clip: float = 0.1
    far_clip: float = 1000.0
    focal_length: float = 50.0 # mm 단위 (메타데이터 용도)
    sensor_width: float = 36.0 # mm 단위 (메타데이터 용도)
    sensor_height: float = 24.0
