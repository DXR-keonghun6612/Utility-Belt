from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    glClearColor, glClear, glEnable, glDisable,
    glReadPixels,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST, GL_LIGHTING,
    GL_DEPTH_COMPONENT, GL_FLOAT,
    GLfloat,
)

from data.scene.node import Scene_Node
from graphics.render.pass_.base import Base_Pass, pass_registry


@pass_registry.Register_module("depth")
class Depth_Pass(Base_Pass):
    """선형 미터 단위 뎁스 맵을 생성하는 패스 (float32, shape: H×W).

    배경 픽셀은 0.0으로 마스킹됨.
    """

    @property
    def Name(self) -> str:
        return "depth"

    def Render(
        self, root_node: Scene_Node, camera_node: Scene_Node, width: int, height: int
    ) -> np.ndarray:
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)

        self._Apply_camera(camera_node, width, height)
        self._Draw_scene(root_node)

        # 뎁스 버퍼 읽기 (NDC: 0.0 ~ 1.0)
        _buf = (GLfloat * (width * height))()
        glReadPixels(0, 0, width, height, GL_DEPTH_COMPONENT, GL_FLOAT, _buf)
        _raw = np.frombuffer(_buf, dtype=np.float32).reshape(height, width)

        # NDC → 선형 미터 단위 변환
        _near = camera_node.intrinsic.near_clip
        _far = camera_node.intrinsic.far_clip
        _linear = (2.0 * _near * _far) / (_far + _near - _raw * (_far - _near))

        # 배경(뎁스 1.0) 픽셀 마스킹
        _linear[_raw >= 1.0] = 0.0

        return np.ascontiguousarray(np.flipud(_linear))
