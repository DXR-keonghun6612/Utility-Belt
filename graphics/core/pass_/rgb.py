from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    glEnable, glColor3f, glLightfv,
    GL_LIGHTING, GL_LIGHT0, GL_COLOR_MATERIAL,
    GL_POSITION, GL_DIFFUSE, GL_AMBIENT,
)

from graphics.core.pass_.base import Base_Pass
from graphics.core.pass_.registry import Pass_Registry


@Pass_Registry.Register_module("rgb")
class RGB_Pass(Base_Pass):
    """Phong 조명 기반 RGB 컬러 이미지를 생성하는 패스."""

    _clear_color = (0.0, 0.0, 0.0, 1.0)

    # 조명 파라미터 (외부 주입 가능)
    light_position: list[float] = [-1.0, -1.0, -1.0, 0.0]
    light_diffuse: list[float] = [1.0, 1.0, 1.0, 1.0]
    light_ambient: list[float] = [0.3, 0.3, 0.3, 1.0]

    @property
    def Name(self) -> str:
        return "rgb"

    def _On_setup(self) -> None:
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)

        glLightfv(GL_LIGHT0, GL_POSITION, self.light_position)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, self.light_diffuse)
        glLightfv(GL_LIGHT0, GL_AMBIENT, self.light_ambient)

        glColor3f(0.7, 0.7, 0.7)

    def _On_readback(self, width: int, height: int, **kwargs) -> np.ndarray:
        return self._Read_rgb(width, height)
