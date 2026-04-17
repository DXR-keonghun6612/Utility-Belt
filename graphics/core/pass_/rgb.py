from __future__ import annotations

import numpy as np
from OpenGL.GL import glColor3f

from graphics.core.lighting import (
    Apply_phong_lighting,
    Set_light_position,
    DEFAULT_LIGHT_DIFFUSE,
    DEFAULT_LIGHT_AMBIENT,
    DEFAULT_LIGHT_SPECULAR,
    DEFAULT_MATERIAL_SPECULAR,
    DEFAULT_MATERIAL_SHININESS,
)
from graphics.core.pass_.base import Base_Pass
from graphics.core.pass_.registry import Pass_Registry


@Pass_Registry.Register_module("rgb")
class RGB_Pass(Base_Pass):
    """Phong 조명(diffuse + ambient + specular) 기반 RGB 컬러 이미지 생성."""

    _clear_color = (0.0, 0.0, 0.0, 1.0)

    # 조명 파라미터 (Configure로 주입됨, 미주입 시 기본값 사용)
    light_position: list[float] = [-1.0, -1.0, -1.0, 0.0]
    light_diffuse: list[float] = list(DEFAULT_LIGHT_DIFFUSE)
    light_ambient: list[float] = list(DEFAULT_LIGHT_AMBIENT)
    light_specular: list[float] = list(DEFAULT_LIGHT_SPECULAR)
    material_specular: list[float] = list(DEFAULT_MATERIAL_SPECULAR)
    material_shininess: float = DEFAULT_MATERIAL_SHININESS

    @property
    def Name(self) -> str:
        return "rgb"

    def Configure(self, config) -> None:
        """Render_Config에서 조명/머티리얼 파라미터를 흡수함."""
        self.light_position = list(config.light_position)
        self.light_diffuse = list(config.light_diffuse)
        self.light_ambient = list(config.light_ambient)
        self.light_specular = list(config.light_specular)
        self.material_specular = list(config.material_specular)
        self.material_shininess = float(config.material_shininess)

    def _On_setup(self) -> None:
        # 조명/머티리얼 상태 설정. light_position은 여기서 지정해도 아직 view
        # 행렬이 로드되기 전이라 월드 고정 의미가 없음 — _On_post_camera에서
        # view 로드 후 다시 주입함.
        Apply_phong_lighting(
            light_position=self.light_position,
            light_diffuse=self.light_diffuse,
            light_ambient=self.light_ambient,
            light_specular=self.light_specular,
            material_specular=self.material_specular,
            material_shininess=self.material_shininess,
        )
        glColor3f(0.7, 0.7, 0.7)

    def _On_post_camera(self) -> None:
        # view 행렬이 MODELVIEW에 로드된 직후 호출되어 light_position이
        # 월드 좌표계 기준으로 고정됨 (방향광 w=0이면 월드 방향벡터로 고정).
        Set_light_position(self.light_position)

    def _On_readback(self, width: int, height: int, **kwargs) -> np.ndarray:
        return self._Read_rgb(width, height)
