from __future__ import annotations

import numpy as np
from OpenGL.GL import glColor3f

from graphics.core.lighting import (
    Apply_phong_lighting,
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
        self.light_diffuse = list(config.light_diffuse)
        self.light_ambient = list(config.light_ambient)
        self.light_specular = list(config.light_specular)
        self.material_specular = list(config.material_specular)
        self.material_shininess = float(config.material_shininess)

    def _On_setup(self) -> None:
        Apply_phong_lighting(
            light_position=self.light_position,
            light_diffuse=self.light_diffuse,
            light_ambient=self.light_ambient,
            light_specular=self.light_specular,
            material_specular=self.material_specular,
            material_shininess=self.material_shininess,
        )
        glColor3f(0.7, 0.7, 0.7)

    def _On_readback(self, width: int, height: int, **kwargs) -> np.ndarray:
        return self._Read_rgb(width, height)
