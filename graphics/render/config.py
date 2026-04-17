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
class Randomize_Range(Base_Config):
    """6-DoF 변환 델타 범위. 카메라/객체 양쪽에 동일 구조로 재사용됨.

    각 필드는 고정값(float) 또는 [min, max] 리스트 형태로 지정함.
    """
    tx: Randomizable = 0.0
    ty: Randomizable = 0.0
    tz: Randomizable = 0.0
    rx: Randomizable = 0.0
    ry: Randomizable = 0.0
    rz: Randomizable = 0.0


@dataclass
class Render_Config(Base_Config):
    """렌더 파이프라인 실행 및 배치 캡처 통합 설정.

    passes: 실행할 렌더 패스 이름 목록.
    bg_color: 배경색 (RGB, 0.0~1.0).

    scene_path: 장면 JSON 파일 경로.
    num_samples: target 객체 1개당 프레임 수 (샘플 루프 반복 횟수).
    camera_label: 장면 내 카메라 노드 식별자.
    output_layout: 출력 디렉토리 구조 ("per_object" | "flat").

    cam: 카메라 extrinsic 델타 범위 (샘플마다 카메라 포즈에 적용).
    obj: 객체 local 델타 범위 (샘플마다 현재 visible 대상 노드에 적용).
    seed: RNG 시드. None이면 비결정적, 정수이면 np.random.seed에 주입.
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

    # 광원 기준 위치(방향) — 4성분. w=0 방향광(xyz는 방향 벡터), w=1 점광원(xyz는 월드 좌표).
    # 현재 파이프라인은 방향광 기준(w=0)으로 xyz 델타를 적용함.
    light_position: list = field(default_factory=lambda: [0.0, 1.0, 0.0, 0.0])

    # 장면 및 캡처
    scene_path: str = ""
    num_samples: int = 1
    camera_label: str = "main_camera"
    output_layout: Output_Layout = "per_object"

    # 샘플 랜덤화 — 카메라 / 객체 / 광원 독립 범위
    # light 는 tx/ty/tz 만 사용되며 회전 성분(rx/ry/rz)은 무시됨.
    cam: Randomize_Range = field(default_factory=Randomize_Range)
    obj: Randomize_Range = field(default_factory=Randomize_Range)
    light: Randomize_Range = field(default_factory=Randomize_Range)

    # RNG 시드 (재현성). None이면 전역 상태 유지.
    seed: int | None = None

    def __post_init__(self) -> None:
        """JSON 역직렬화 시 nested dict → Randomize_Range 복원."""
        if isinstance(self.cam, dict):
            self.cam = Randomize_Range(**self.cam)
        if isinstance(self.obj, dict):
            self.obj = Randomize_Range(**self.obj)
        if isinstance(self.light, dict):
            self.light = Randomize_Range(**self.light)


def Sample_delta_matrix(r: Randomize_Range) -> np.ndarray:
    """Randomize_Range의 6-DoF 범위로부터 델타 변환 행렬을 샘플링함.

    Args:
        r: 샘플링 대상 범위 (Render_Config.cam 또는 Render_Config.obj).

    Returns:
        np.ndarray: 샘플링된 4x4 델타 변환 행렬 (float32).
    """
    return Build_transform(
        tx=_Sample_value(r.tx),
        ty=_Sample_value(r.ty),
        tz=_Sample_value(r.tz),
        rx=_Sample_value(r.rx),
        ry=_Sample_value(r.ry),
        rz=_Sample_value(r.rz),
    )


def Sample_translation(r: Randomize_Range) -> tuple[float, float, float]:
    """Randomize_Range의 tx/ty/tz 만 샘플링하여 3-벡터를 반환함 (회전은 무시).

    광원 위치 델타처럼 회전 의미가 없는 용도에 사용.
    """
    return _Sample_value(r.tx), _Sample_value(r.ty), _Sample_value(r.tz)


def _Sample_value(v: Randomizable) -> float:
    """고정값이면 그대로 반환, [min, max]이면 균일 랜덤 샘플링."""
    if isinstance(v, list):
        if len(v) >= 2:
            return float(np.random.uniform(v[0], v[1]))
        return float(v[0])
    return float(v)
