from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    glClearColor, glClear, glEnable, glDisable, glFlush,
    glPushMatrix, glPopMatrix, glMultMatrixf,
    glEnableClientState, glDisableClientState,
    glVertexPointer, glColorPointer, glDrawElements,
    glReadPixels,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST, GL_LIGHTING, GL_DITHER,
    GL_VERTEX_ARRAY, GL_COLOR_ARRAY,
    GL_FLOAT, GL_UNSIGNED_INT, GL_UNSIGNED_BYTE,
    GL_RGB,
    GLubyte,
)

from data.scene.node import Scene_Node
from graphics.render.pass_.base import Base_Pass, pass_registry


@pass_registry.Register_module("normal")
class Normal_Pass(Base_Pass):
    """로컬 공간 법선 벡터를 RGB로 인코딩한 맵을 생성하는 패스 (uint8, shape: H×W×3).

    인코딩 방식: normal_rgb = (normal_xyz + 1.0) * 127.5  (범위 [0, 255])
    배경 픽셀은 (128, 128, 255) — Z+ 방향 기본값으로 채워짐.
    """

    @property
    def Name(self) -> str:
        return "normal"

    def Render(
        self, root_node: Scene_Node, camera_node: Scene_Node, width: int, height: int
    ) -> np.ndarray:
        # 배경: (0,0,1) 법선 방향 → (0.5, 0.5, 1.0) → (128, 128, 255)
        glClearColor(0.5, 0.5, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)

        self._Apply_camera(camera_node, width, height)
        self._Draw_normal_scene(root_node)

        glFlush()

        _buf = (GLubyte * (width * height * 3))()
        glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, _buf)
        _arr = np.frombuffer(_buf, dtype=np.uint8).reshape(height, width, 3)

        glEnable(GL_DITHER)

        return np.ascontiguousarray(np.flipud(_arr))

    def _Draw_normal_scene(self, node: Scene_Node) -> None:
        """법선 벡터를 색상으로 인코딩하여 재귀 렌더링함."""
        glPushMatrix()
        glMultMatrixf(node.local_matrix.T)

        if node.mesh:
            self._Draw_normal_mesh(node.mesh)

        for _child in node.children:
            self._Draw_normal_scene(_child)

        glPopMatrix()

    def _Draw_normal_mesh(self, mesh) -> None:
        """vertex_normals를 glColorPointer로 전달하여 법선 맵을 렌더링함."""
        if not hasattr(mesh, "vertex_normals") or mesh.vertex_normals is None:
            return

        # [-1, 1] → [0, 255] 인코딩 (contiguous 보장)
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
