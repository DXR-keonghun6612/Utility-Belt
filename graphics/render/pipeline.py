from __future__ import annotations

import numpy as np
from PySide6.QtGui import QOffscreenSurface, QSurfaceFormat, QOpenGLContext
from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from data.scene.node import Scene_Node
from graphics.render.config import Render_Config
from graphics.render.pass_.base import Base_Pass, pass_registry


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
            pass_registry.Get(name)() for name in config.passes
        ]

        # 헤드리스 모드 전용 리소스 (Setup_headless_context() 호출 시 초기화)
        self._surface: QOffscreenSurface | None = None
        self._gl_ctx: QOpenGLContext | None = None
        self._fbo: QOpenGLFramebufferObject | None = None

    # ==========================================
    # 헤드리스 컨텍스트 관리
    # ==========================================

    def Setup_headless_context(self) -> None:
        """오프스크린 OpenGL 컨텍스트 및 FBO를 초기화함.

        QApplication이 생성된 이후에 호출해야 함.
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
        _fbo_fmt.setAttachment(QOpenGLFramebufferObjectFormat.Attachment.Depth)

        self._fbo = QOpenGLFramebufferObject(
            self._config.width, self._config.height, _fbo_fmt
        )

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
        self, root_node: Scene_Node, camera_node: Scene_Node
    ) -> dict[str, np.ndarray]:
        """등록된 패스를 순차 실행하고 패스명 → 픽셀 배열 딕셔너리를 반환함.

        Args:
            root_node: 씬 루트 노드.
            camera_node: 가상 카메라 씬 노드 (intrinsic 필드 필수).

        Returns:
            dict[str, np.ndarray]: 패스명 키, 픽셀 데이터 값.
        """
        _w, _h = self._config.width, self._config.height

        if self._fbo:
            self._fbo.bind()

        _results: dict[str, np.ndarray] = {}
        for _pass in self._passes:
            _results[_pass.Name] = _pass.Render(root_node, camera_node, _w, _h)

        if self._fbo:
            self._fbo.release()

        return _results
