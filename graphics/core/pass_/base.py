from __future__ import annotations
from abc import ABC, abstractmethod

import numpy as np
from OpenGL.GL import (
    glMatrixMode, glLoadIdentity, glViewport, glLoadMatrixf,
    glPushMatrix, glPopMatrix, glMultMatrixf,
    glClearColor, glClear, glEnable, glDisable, glFlush,
    glReadPixels,
    GL_PROJECTION, GL_MODELVIEW,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_RGB, GL_UNSIGNED_BYTE, GL_DEPTH_COMPONENT, GL_FLOAT,
    GLubyte, GLfloat,
)
from OpenGL.GLU import gluPerspective

from data.node import Base_Node
from data.node.type.mesh import Mesh_Node
from data.node.type.camera import Camera_Node
from graphics.core.draw import Draw_mesh
from graphics.core.resource import GPU_Resource_Manager


class Base_Pass(ABC):
    """렌더 패스 추상 베이스. Template Method 패턴으로 공통 흐름을 고정함.

    서브클래스는 _On_setup / _On_draw / _On_readback 훅만 오버라이드하여
    패스별 차이를 구현함.
    """

    # 서브클래스에서 오버라이드 가능한 기본 설정
    _clear_color: tuple[float, ...] = (0.0, 0.0, 0.0, 1.0)

    def __init__(self):
        self.res_manager = GPU_Resource_Manager()

    @property
    @abstractmethod
    def Name(self) -> str:
        """렌더 패스 고유 식별자."""
        ...

    # ==========================================
    # Template Method (고정 흐름)
    # ==========================================

    def Render(
        self, root_node: Base_Node, camera_node: Camera_Node,
        width: int, height: int
    ) -> np.ndarray:
        """공통 렌더 파이프라인 실행. 서브클래스는 훅을 통해 차이만 주입함.

        Args:
            root_node: 씬 루트 노드.
            camera_node: intrinsic + world_matrix를 보유한 카메라 노드.
            width: 출력 이미지 너비 (px).
            height: 출력 이미지 높이 (px).

        Returns:
            np.ndarray: 픽셀 데이터 (Y축 반전 적용됨).
        """
        # 1. 공통 초기화
        glClearColor(*self._clear_color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)

        # 2. 패스별 GL 상태 설정
        self._On_setup()

        # 3. 카메라 적용
        self._Apply_camera(camera_node, width, height)

        # 4. 패스 드로우
        self._On_draw(root_node)

        glFlush()

        # 5. 패스별 픽셀 읽기
        _raw = self._On_readback(width, height, camera_node=camera_node)

        # 6. 패스별 상태 복구
        self._On_cleanup()

        # 7. 공통 후처리 (OpenGL 좌하단 기준 → 좌상단 기준)
        return np.ascontiguousarray(np.flipud(_raw))

    # ==========================================
    # 오버라이드 훅 (서브클래스에서 필요한 것만 재정의)
    # ==========================================

    def _On_setup(self) -> None:
        """GL 상태 설정 (조명, 디더링 등). 기본: 조기 OFF."""
        glDisable(GL_DEPTH_TEST)

    def _On_draw(self, root_node: Base_Node) -> None:
        """씬 드로우. 기본: Mesh_Node 트리 순회."""
        self._Draw_scene(root_node)

    @abstractmethod
    def _On_readback(self, width: int, height: int, **kwargs) -> np.ndarray:
        """프레임버퍼에서 픽셀 데이터를 읽음. 패스별 포맷이 상이하므로 필수 구현.

        Args:
            width: 출력 너비 (px).
            height: 출력 높이 (px).
            **kwargs: 패스별 추가 인자 (camera_node 등).
        """
        ...

    def _On_cleanup(self) -> None:
        """GL 상태 복구. 기본: 없음."""
        pass

    # ==========================================
    # 공용 헬퍼
    # ==========================================

    def _Apply_camera(
        self, camera_node: Camera_Node, width: int, height: int
    ) -> None:
        """씬 카메라의 intrinsic/extrinsic을 OpenGL 파이프라인에 주입함."""
        if width <= 0 or height <= 0:
            raise ValueError("렌더링 해상도는 양수여야 함.")

        _intrinsic = camera_node.intrinsic
        if _intrinsic is None:
            raise ValueError("intrinsic is None")

        glViewport(0, 0, width, height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(
            _intrinsic.fov, width / height,
            _intrinsic.near_clip, _intrinsic.far_clip
        )

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        _view = np.linalg.inv(camera_node.world_matrix).astype(np.float32)
        glLoadMatrixf(_view.T)

    def _Draw_scene(self, node: Base_Node) -> None:
        """씬 트리를 재귀 순회하며 Mesh_Node의 지오메트리를 렌더링함."""
        if not node.is_renderable:
            return

        glPushMatrix()
        glMultMatrixf(node.local_matrix.T)

        if isinstance(node, Mesh_Node) and node.mesh is not None:
            Draw_mesh(node.mesh, self.res_manager)

        for _child in node.children:
            self._Draw_scene(_child)

        glPopMatrix()

    @staticmethod
    def _Read_rgb(width: int, height: int) -> np.ndarray:
        """프레임버퍼에서 RGB uint8 배열을 읽음."""
        _buf = (GLubyte * (width * height * 3))()
        glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, _buf)
        return np.frombuffer(_buf, dtype=np.uint8).reshape(height, width, 3)

    @staticmethod
    def _Read_depth(width: int, height: int) -> np.ndarray:
        """프레임버퍼에서 Depth float32 배열을 읽음 (NDC 0.0~1.0 원본)."""
        _buf = (GLfloat * (width * height))()
        glReadPixels(0, 0, width, height, GL_DEPTH_COMPONENT, GL_FLOAT, _buf)
        return np.frombuffer(_buf, dtype=np.float32).reshape(height, width)
