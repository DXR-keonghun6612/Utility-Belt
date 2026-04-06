from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    glDisable, glEnable,
    glPushMatrix, glPopMatrix, glMultMatrixf,
    glEnableClientState, glDisableClientState,
    glVertexPointer, glColorPointer, glDrawElements,
    GL_LIGHTING, GL_DITHER,
    GL_VERTEX_ARRAY, GL_COLOR_ARRAY,
    GL_FLOAT, GL_UNSIGNED_INT, GL_UNSIGNED_BYTE, GL_TRIANGLES,
)

from data.scene.node import Scene_Node
from data.scene.node.mesh import Mesh_Node
from graphics.core.pass_.base import Base_Pass
from graphics.core.pass_.registry import Pass_Registry


@Pass_Registry.Register_module("normal")
class Normal_Pass(Base_Pass):
    """로컬 공간 법선 벡터를 RGB로 인코딩한 맵을 생성하는 패스 (uint8, HxWx3).

    인코딩: normal_rgb = (normal_xyz + 1.0) * 127.5
    배경: (128, 128, 255) — Z+ 방향 기본값.
    """

    _clear_color = (0.5, 0.5, 1.0, 1.0)

    @property
    def Name(self) -> str:
        return "normal"

    def _On_setup(self) -> None:
        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)

    def _On_draw(self, root_node: Scene_Node) -> None:
        self._Draw_normal_scene(root_node)

    def _On_readback(self, width: int, height: int, **kwargs) -> np.ndarray:
        return self._Read_rgb(width, height)

    def _On_cleanup(self) -> None:
        glEnable(GL_DITHER)

    # ==========================================
    # 법선 맵 전용 드로우
    # ==========================================

    def _Draw_normal_scene(self, node: Scene_Node) -> None:
        """법선 벡터를 색상으로 인코딩하여 재귀 렌더링함."""
        if not node.is_renderable:
            return

        glPushMatrix()
        glMultMatrixf(node.local_matrix.T)

        if isinstance(node, Mesh_Node) and node.mesh is not None:
            self._Draw_normal_mesh(node.mesh)

        for _child in node.children:
            self._Draw_normal_scene(_child)

        glPopMatrix()

    def _Draw_normal_mesh(self, mesh) -> None:
        """vertex_normals를 glColorPointer로 전달하거나 VBO를 사용하여 법선 맵을 렌더링함."""
        if not hasattr(mesh, "vertex_normals") or mesh.vertex_normals is None:
            return

        _vbos = self.res_manager.Sync_mesh(mesh)

        if _vbos is not None and 'normal_colors' in _vbos:
            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)

            _vbos['vertices'].bind()
            glVertexPointer(3, GL_FLOAT, 0, _vbos['vertices'])

            _vbos['normal_colors'].bind()
            glColorPointer(3, GL_UNSIGNED_BYTE, 0, _vbos['normal_colors'])

            _vbos['faces'].bind()
            glDrawElements(GL_TRIANGLES, _vbos['face_count'], GL_UNSIGNED_INT, None)
            _vbos['faces'].unbind()

            glDisableClientState(GL_COLOR_ARRAY)
            _vbos['normal_colors'].unbind()
            glDisableClientState(GL_VERTEX_ARRAY)
            _vbos['vertices'].unbind()
            return

        # 폴백 (저속)
        _colors = np.ascontiguousarray(
            ((mesh.vertex_normals + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
        )

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, mesh.vertices)
        glColorPointer(3, GL_UNSIGNED_BYTE, 0, _colors)
        glDrawElements(GL_TRIANGLES, len(mesh.faces) * 3, GL_UNSIGNED_INT, mesh.faces)
        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)