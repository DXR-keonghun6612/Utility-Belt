from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from python_toolbox.project import Base_Config
from data.node import Build_transform


# 고정값 또는 [min, max] 범위
Randomizable = float | list

# 출력 디렉토리 레이아웃 — per_object: 객체별 서브디렉토리, flat: 단일 디렉토리
Output_Layout = Literal["per_object", "flat"]


@dataclass
class Render_Config(Base_Config):
    """렌더 파이프라인 실행 및 배치 캡처 통합 설정.

    passes: 실행할 렌더 패스 이름 목록.
    bg_color: 배경색 (RGB, 0.0~1.0).

    scene_path: 장면 JSON 파일 경로.
    num_samples: target 객체 1개당 프레임 수 (카메라 델타 반복).
    camera_label: 장면 내 카메라 노드 식별자.
    output_layout: 출력 디렉토리 구조 ("per_object" | "flat").

    tx~rz: 카메라 Extrinsic 델타 범위 (고정값 또는 [min, max]).
    """

    # 렌더 패스
    passes: list = field(default_factory=lambda: ["rgb", "depth", "segmentation", "normal"])
    bg_color: list = field(default_factory=lambda: [0.0, 0.0, 0.0])

    # RGB 패스 — Phong 조명 (RGBA, 0.0~1.0)
    light_diffuse: list = field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    light_ambient: list = field(default_factory=lambda: [0.3, 0.3, 0.3, 1.0])
    light_specular: list = field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    material_specular: list = field(default_factory=lambda: [0.4, 0.4, 0.4, 1.0])
    material_shininess: float = 32.0

    # 장면 및 캡처
    scene_path: str = ""
    num_samples: int = 1
    camera_label: str = "main_camera"
    output_layout: Output_Layout = "per_object"

    # 카메라 Extrinsic 델타 — 이동 (씬 좌표계)
    tx: Randomizable = 0.0
    ty: Randomizable = 0.0
    tz: Randomizable = 0.0

    # 카메라 Extrinsic 델타 — 회전 (degrees, XYZ Euler)
    rx: Randomizable = 0.0
    ry: Randomizable = 0.0
    rz: Randomizable = 0.0


def Sample_delta_matrix(config: Render_Config) -> np.ndarray:
    """Render_Config의 범위에서 델타 변환 행렬을 샘플링함.

    Args:
        config: 카메라 랜덤화 범위가 포함된 설정.

    Returns:
        np.ndarray: 샘플링된 4x4 델타 변환 행렬 (float32).
    """
    return Build_transform(
        tx=_Sample_value(config.tx),
        ty=_Sample_value(config.ty),
        tz=_Sample_value(config.tz),
        rx=_Sample_value(config.rx),
        ry=_Sample_value(config.ry),
        rz=_Sample_value(config.rz),
    )


def _Sample_value(v: Randomizable) -> float:
    """고정값이면 그대로 반환, [min, max]이면 균일 랜덤 샘플링."""
    if isinstance(v, list):
        if len(v) >= 2:
            return float(np.random.uniform(v[0], v[1]))
        return float(v[0])
    return float(v)
