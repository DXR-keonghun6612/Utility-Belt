from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    glClearColor, glClear, glEnable, glDisable, glColor3f,
    glLightfv, glReadPixels,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST, GL_LIGHTING, GL_LIGHT0, GL_COLOR_MATERIAL,
    GL_POSITION, GL_DIFFUSE, GL_AMBIENT,
    GL_RGB, GL_UNSIGNED_BYTE,
    GLubyte,
)

from data.scene.node import Scene_Node
from graphics.render.pass_.base import Base_Pass, pass_registry


@pass_registry.Register_module("rgb")
class RGB_Pass(Base_Pass):
    """Phong 조명 기반 RGB 컬러 이미지를 생성하는 패스."""

    @property
    def Name(self) -> str:
        return "rgb"

    def Render(
        self, root_node: Scene_Node, camera_node: Scene_Node, width: int, height: int
    ) -> np.ndarray:
        _bg = getattr(self, "_bg_color", (0.0, 0.0, 0.0))
        glClearColor(*_bg, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)

        # 단순 검증용 조명 (위에서 내리꽂는 방향성 광원)
        glLightfv(GL_LIGHT0, GL_POSITION, [0.0, 1.0, 0.0, 0.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])

        self._Apply_camera(camera_node, width, height)

        glColor3f(0.7, 0.7, 0.7)
        self._Draw_scene(root_node)

        _buf = (GLubyte * (width * height * 3))()
        glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, _buf)
        _arr = np.frombuffer(_buf, dtype=np.uint8).reshape(height, width, 3)

        # OpenGL은 좌하단 기준이므로 Y축 반전
        return np.ascontiguousarray(np.flipud(_arr))
