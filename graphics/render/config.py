from __future__ import annotations
from dataclasses import dataclass, field

import numpy as np

from python_toolbox.project import Base_Config
from data.node import Build_transform


# 고정값 또는 [min, max] 범위
Randomizable = float | list


@dataclass
class Render_Config(Base_Config):
    """렌더 파이프라인 실행 및 배치 캡처 통합 설정.

    passes: 실행할 렌더 패스 이름 목록.
    bg_color: 배경색 (RGB, 0.0~1.0).

    scene_path: 장면 JSON 파일 경로.
    num_samples: 카메라 랜덤화 반복 횟수.
    camera_label: 장면 내 카메라 노드 식별자.

    obj_dir: OBJ 디렉토리 스캔 모드 (빈 문자열이면 비활성).
    target_node_label: OBJ 삽입 대상 노드 라벨.

    tx~rz: 카메라 Extrinsic 델타 범위 (고정값 또는 [min, max]).
    """

    # 렌더 패스
    passes: list = field(default_factory=lambda: ["rgb", "depth", "segmentation", "normal"])
    bg_color: list = field(default_factory=lambda: [0.0, 0.0, 0.0])

    # 장면 및 캡처
    scene_path: str = ""
    num_samples: int = 1
    camera_label: str = "main_camera"

    # OBJ 배치 모드
    obj_dir: str = ""
    target_node_label: str = ""

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
