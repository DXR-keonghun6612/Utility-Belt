from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    glDisable, glEnable,
    glPushMatrix, glPopMatrix, glMultMatrixf,
    glColor3ub,
    GL_LIGHTING, GL_DITHER,
)

from data.scene.node import Scene_Node
from data.scene.node.mesh import Mesh_Node
from graphics.core.draw import Draw_mesh
from graphics.core.pass_.base import Base_Pass
from graphics.core.pass_.registry import Pass_Registry


@Pass_Registry.Register_module("segmentation")
class Segmentation_Pass(Base_Pass):
    """RGB 인코딩된 인스턴스 ID 맵을 생성하는 패스 (uint8, HxWx3).

    Render() 호출 후 last_id_map에서 색상 키 → Scene_Node 매핑을 확인 가능함.
    배경: (0, 0, 0).
    """

    def __init__(self):
        super().__init__()
        self.last_id_map: dict[tuple[int, int, int], Scene_Node] = {}
        self._id_counter: int = 0

    @property
    def Name(self) -> str:
        return "segmentation"

    def _On_setup(self) -> None:
        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)
        self._id_counter = 1
        self.last_id_map = {}

    def _On_draw(self, root_node: Scene_Node) -> None:
        self._Draw_id_scene(root_node)

    def _On_readback(self, width: int, height: int, **kwargs) -> np.ndarray:
        return self._Read_rgb(width, height)

    def _On_cleanup(self) -> None:
        glEnable(GL_DITHER)

    # ==========================================
    # ID 맵 전용 드로우
    # ==========================================

    def _Draw_id_scene(self, node: Scene_Node) -> None:
        """고유 RGB 색상으로 인코딩된 ID 메쉬를 재귀 렌더링함."""
        if not node.is_renderable:
            return

        glPushMatrix()
        glMultMatrixf(node.local_matrix.T)

        if isinstance(node, Mesh_Node) and node.mesh is not None:
            _r = self._id_counter & 0xFF
            _g = (self._id_counter >> 8) & 0xFF
            _b = (self._id_counter >> 16) & 0xFF

            self.last_id_map[(_r, _g, _b)] = node
            glColor3ub(_r, _g, _b)
            Draw_mesh(node.mesh, self.res_manager)
            self._id_counter += 1

        for _child in node.children:
            self._Draw_id_scene(_child)

        glPopMatrix()
