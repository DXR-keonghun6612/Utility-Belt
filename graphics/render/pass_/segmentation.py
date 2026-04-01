from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    glClearColor, glClear, glEnable, glDisable, glFlush,
    glPushMatrix, glPopMatrix, glMultMatrixf,
    glColor3ub, glReadPixels,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST, GL_LIGHTING, GL_DITHER,
    GL_RGB, GL_UNSIGNED_BYTE,
    GLubyte,
)

from data.scene.node import Scene_Node
from graphics.render.pass_.base import Base_Pass, pass_registry


@pass_registry.Register_module("segmentation")
class Segmentation_Pass(Base_Pass):
    """RGB 인코딩된 인스턴스 ID 맵을 생성하는 패스 (uint8, shape: H×W×3).

    Render() 호출 후 last_id_map 속성에서 색상 키 → Scene_Node 매핑을 확인할 수 있음.
    배경은 (0, 0, 0)으로 표현됨.
    """

    def __init__(self):
        # Render() 완료 후 외부에서 참조 가능한 색상-노드 매핑
        self.last_id_map: dict[tuple[int, int, int], Scene_Node] = {}

    @property
    def Name(self) -> str:
        return "segmentation"

    def Render(
        self, root_node: Scene_Node, camera_node: Scene_Node, width: int, height: int
    ) -> np.ndarray:
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        # 안티앨리어싱이 ID 색상값을 훼손하지 않도록 디더링 비활성화
        glDisable(GL_DITHER)

        self._Apply_camera(camera_node, width, height)

        self._id_counter = 1
        self.last_id_map = {}
        self._Draw_id_scene(root_node)

        glFlush()

        _buf = (GLubyte * (width * height * 3))()
        glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, _buf)
        _arr = np.frombuffer(_buf, dtype=np.uint8).reshape(height, width, 3)

        glEnable(GL_DITHER)

        return np.ascontiguousarray(np.flipud(_arr))

    def _Draw_id_scene(self, node: Scene_Node) -> None:
        """고유 RGB 색상으로 인코딩된 ID 메쉬를 재귀 렌더링함."""
        glPushMatrix()
        glMultMatrixf(node.local_matrix.T)

        if node.mesh:
            # 카운터를 24비트 RGB로 인코딩 (최대 16,777,215개 인스턴스)
            _r = self._id_counter & 0xFF
            _g = (self._id_counter >> 8) & 0xFF
            _b = (self._id_counter >> 16) & 0xFF

            self.last_id_map[(_r, _g, _b)] = node
            glColor3ub(_r, _g, _b)
            self._Draw_mesh(node.mesh)
            self._id_counter += 1

        for _child in node.children:
            self._Draw_id_scene(_child)

        glPopMatrix()
