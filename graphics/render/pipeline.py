from __future__ import annotations

import numpy as np
from PySide6.QtGui import QOffscreenSurface, QSurfaceFormat, QOpenGLContext
from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from data.scene.node import Scene_Node
from data.scene.node.camera import Camera_Node
from graphics.render.config import Render_Config
from graphics.core.pass_.base import Base_Pass
from graphics.core.pass_.build import Get_render


class Render_Pipeline:
    """등록된 패스를 순차 실행하여 한 장면에서 다중 렌더 결과를 생성함.

    OpenGL 컨텍스트 관리 방식:
    - UI 모드: 호출 측의 기존 컨텍스트 안에서 실행 (makeCurrent 후 호출).
    - 헤드리스 모드: Setup_headless_context() 호출로 독립 오프스크린 컨텍스트 생성.
    """

    def __init__(self, config: Render_Config):
        self._config = config

        # config.passes 이름 목록으로 패스 인스턴스 생성
        self._passes: list[Base_Pass] = [
            Get_render(name) for name in config.passes
        ]

        # 헤드리스 모드 전용 리소스
        self._surface: QOffscreenSurface | None = None
        self._gl_ctx: QOpenGLContext | None = None
        self._fbo: QOpenGLFramebufferObject | None = None

    # ==========================================
    # 헤드리스 컨텍스트 관리
    # ==========================================

    def Setup_headless_context(self, width: int, height: int) -> None:
        """오프스크린 OpenGL 컨텍스트 및 FBO를 초기화함.

        Args:
            width: FBO 해상도 너비 (px).
            height: FBO 해상도 높이 (px).
        """
        _fmt = QSurfaceFormat()
        _fmt.setDepthBufferSize(24)
        _fmt.setVersion(2, 1)

        self._surface = QOffscreenSurface()
        self._surface.setFormat(_fmt)
        self._surface.create()

        self._gl_ctx = QOpenGLContext()
        self._gl_ctx.setFormat(_fmt)
        self._gl_ctx.create()
        self._gl_ctx.makeCurrent(self._surface)

        _fbo_fmt = QOpenGLFramebufferObjectFormat()
        _fbo_fmt.setAttachment(
            QOpenGLFramebufferObject.Attachment.Depth
        )

        self._fbo = QOpenGLFramebufferObject(width, height, _fbo_fmt)

    def Teardown_headless_context(self) -> None:
        """오프스크린 컨텍스트 리소스를 해제함."""
        if self._fbo:
            self._fbo.release()
        if self._gl_ctx and self._surface:
            self._gl_ctx.doneCurrent()
        self._fbo = None
        self._gl_ctx = None
        self._surface = None

    # ==========================================
    # 실행
    # ==========================================

    def Execute(
        self, root_node: Scene_Node, camera_node: Camera_Node,
        width: int, height: int
    ) -> dict[str, np.ndarray]:
        """등록된 패스를 순차 실행하고 패스명 → 픽셀 배열 딕셔너리를 반환함.

        Args:
            root_node: 씬 루트 노드.
            camera_node: intrinsic 필드를 보유한 카메라 노드.
            width: 출력 해상도 너비 (px).
            height: 출력 해상도 높이 (px).

        Returns:
            dict[str, np.ndarray]: 패스명 키, 픽셀 데이터 값.
        """
        if self._fbo:
            self._fbo.bind()

        _results: dict[str, np.ndarray] = {}
        for _pass in self._passes:
            _results[_pass.Name] = _pass.Render(root_node, camera_node, width, height)

        if self._fbo:
            self._fbo.release()

        return _results
