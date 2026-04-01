from __future__ import annotations
from abc import ABC, abstractmethod

import numpy as np
from OpenGL.GL import (
    glMatrixMode, glLoadIdentity, glLoadMatrixf,
    GL_PROJECTION, GL_MODELVIEW,
)
from OpenGL.GLU import gluPerspective

from data.scene.node import Scene_Node
from graphics.core.draw import Draw_mesh, Walk_scene
from python_toolbox.project import Registry


class Base_Pass(ABC):
    """렌더 패스 추상 베이스.

    구현체는 Render()를 통해 현재 활성화된 OpenGL 컨텍스트(FBO)에
    드로우 콜을 수행하고 픽셀 배열을 반환해야 함.
    """

    @property
    @abstractmethod
    def Name(self) -> str:
        """렌더 패스 고유 식별자."""
        ...

    @abstractmethod
    def Render(
        self, root_node: Scene_Node, camera_node: Scene_Node, width: int, height: int
    ) -> np.ndarray:
        """OpenGL 드로우 콜 실행 후 픽셀 배열을 반환함.

        Args:
            root_node: 씬 루트 노드.
            camera_node: prim_type="Camera"인 씬 노드 (intrinsic + world_matrix 보유).
            width: 출력 이미지 너비 (px).
            height: 출력 이미지 높이 (px).

        Returns:
            np.ndarray: 픽셀 데이터. dtype은 패스별로 상이함 (uint8 or float32).
        """
        ...

    # ==========================================
    # 공용 헬퍼 (서브클래스에서 재사용)
    # ==========================================

    def _Apply_camera(
        self, camera_node: Scene_Node, width: int, height: int
    ) -> None:
        """씬 카메라의 intrinsic/extrinsic을 OpenGL 파이프라인에 주입함."""
        _intrinsic = camera_node.intrinsic
        _aspect = width / max(height, 1)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(_intrinsic.fov, _aspect, _intrinsic.near_clip, _intrinsic.far_clip)

        # 카메라 world_matrix의 역행렬 = View 행렬
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        _view = np.linalg.inv(camera_node.world_matrix).astype(np.float32)
        glLoadMatrixf(_view.T)

    def _Draw_mesh(self, mesh) -> None:
        """공통 드로우 코어에 위임함."""
        Draw_mesh(mesh)

    def _Draw_scene(self, node: Scene_Node) -> None:
        """공통 씬 순회에 위임함."""
        Walk_scene(node)


# 렌더 패스 등록 레지스트리 (Base_Pass 서브클래스 전용)
pass_registry: Registry = Registry("RenderPassRegistry", Base_Pass)
