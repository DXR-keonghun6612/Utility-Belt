from __future__ import annotations

import numpy as np
from PySide6.QtGui import QOffscreenSurface, QSurfaceFormat, QOpenGLContext
from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from spatial_toolbox.scene.node import Base_Node, Camera
from simulation.config import Render_Config
from spatial_toolbox.graphics.core.pass_ import Base_Pass


class Render_Pipeline:
    """등록된 패스를 순차 실행하여 한 장면에서 다중 렌더 결과를 생성함.

    OpenGL 컨텍스트 관리 방식:
    - EGL(우선): PySide6 없이 순수 OpenGL 백엔드를 사용하여 FBO 생성 및 렌더링.
    - Qt(폴백): EGL 초기화 실패 시 PySide6 프레임워크 기반 QOffscreenSurface 사용.
    - UI 모드: 호출 측의 기존 컨텍스트 안에서 실행 (makeCurrent 후 호출).
    """

    def __init__(self, config: Render_Config):
        self._config = config

        # config.passes 이름 목록으로 패스 인스턴스 생성 + Configure 주입
        self._passes: list[Base_Pass] = []
        for _name in config.passes:
            _pass = Get_render(_name)
            _pass.Configure(config)
            self._passes.append(_pass)

        # 헤드리스 모드 전용 리소스 (Qt 폴백용)
        self._surface: QOffscreenSurface | None = None
        self._gl_ctx: QOpenGLContext | None = None
        self._fbo: QOpenGLFramebufferObject | None = None
        
        # 상태 변수
        self._use_egl = False

    # ==========================================
    # 패스 파라미터 런타임 갱신
    # ==========================================

    def Get_segmentation_id_map(self) -> list[dict]:
        """segmentation 패스의 color→node 매핑을 JSON 직렬화 가능한 리스트로 반환함.

        반환 포맷: [{"color": [r,g,b], "label": ..., "prim_path": ...}, ...]
        segmentation 패스가 없거나 아직 렌더되지 않았으면 빈 리스트 반환.
        """
        for _pass in self._passes:
            if not hasattr(_pass, "last_id_map"):
                continue
            return [
                {
                    "color": list(_color),
                    "label": _node.label,
                    "prim_path": _node.prim_path,
                }
                for _color, _node in _pass.last_id_map.items()
            ]
        return []

    def Set_light_position(self, position: list[float]) -> None:
        """광원 위치(4성분)를 모든 해당 패스에 런타임 주입함.

        Apply_phong_lighting을 사용하는 패스(RGB 등)에만 영향을 미침. 다른 패스는
        `light_position` 속성을 갖지 않으므로 조용히 스킵됨 (덕 타이핑).

        Args:
            position: [x, y, z, w] 4성분. w=0은 방향광, w=1은 점광원.
        """
        for _pass in self._passes:
            if hasattr(_pass, "light_position"):
                _pass.light_position = list(position)

    # ==========================================
    # 헤드리스 컨텍스트 관리
    # ==========================================

    def Setup_headless_context(self, width: int, height: int, use_egl: bool = True) -> None:
        """오프스크린 OpenGL 컨텍스트 및 FBO를 초기화함.

        Args:
            width: FBO 해상도 너비 (px).
            height: FBO 해상도 높이 (px).
            use_egl: True일 경우 우선적으로 EGL 기반 컨텍스트 생성을 시도함.
        """
        self._use_egl = False
        
        if use_egl:
            try:
                self._Setup_egl_context(width, height)
                self._use_egl = True
                print("[INFO] EGL 컨텍스트 초기화 성공 (순수 OpenGL 모드).")
                return
            except Exception as e:
                print(f"[WARN] EGL 초기화 실패 ({e}). Qt 기반 오프스크린 모드로 폴백함.")
                self._Teardown_egl_context()
        
        self._Setup_qt_context(width, height)

    def _Setup_egl_context(self, width: int, height: int) -> None:
        """PyOpenGL의 EGL 모듈을 활용하여 UI 없는 순수 헤드리스 컨텍스트를 생성함."""
        import ctypes
        from OpenGL.EGL import (
            eglGetDisplay, eglInitialize, eglChooseConfig, eglCreateContext,
            eglCreatePbufferSurface, eglBindAPI, eglMakeCurrent,
            EGL_DEFAULT_DISPLAY, EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
            EGL_BLUE_SIZE, EGL_GREEN_SIZE, EGL_RED_SIZE, EGL_DEPTH_SIZE,
            EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT, EGL_NONE, EGL_WIDTH, EGL_HEIGHT,
            EGL_OPENGL_API, EGL_NO_CONTEXT
        )
        from OpenGL.GL import (
            glGenFramebuffers, glBindFramebuffer, GL_FRAMEBUFFER,
            glGenRenderbuffers, glBindRenderbuffer, GL_RENDERBUFFER,
            glRenderbufferStorage, GL_DEPTH_COMPONENT24, glFramebufferRenderbuffer,
            GL_DEPTH_ATTACHMENT, glCheckFramebufferStatus, GL_FRAMEBUFFER_COMPLETE,
            GL_RGBA8, GL_COLOR_ATTACHMENT0
        )
        
        self._egl_display = eglGetDisplay(EGL_DEFAULT_DISPLAY)
        if not self._egl_display:
            raise RuntimeError("Failed to get EGL display")
            
        if not eglInitialize(self._egl_display, None, None):
            raise RuntimeError("Failed to initialize EGL")

        config_attribs = np.array([
            EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
            EGL_BLUE_SIZE, 8,
            EGL_GREEN_SIZE, 8,
            EGL_RED_SIZE, 8,
            EGL_DEPTH_SIZE, 24,
            EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT,
            EGL_NONE
        ], dtype=np.int32)
        
        configs = (ctypes.c_void_p * 1)()
        num_configs = ctypes.c_int()
        if not eglChooseConfig(self._egl_display, config_attribs, configs, 1, ctypes.byref(num_configs)) or num_configs.value == 0:
            raise RuntimeError("Failed to choose EGL config")
            
        self._egl_config = configs[0]
        
        pbuffer_attribs = np.array([
            EGL_WIDTH, width,
            EGL_HEIGHT, height,
            EGL_NONE
        ], dtype=np.int32)
        
        self._egl_surface = eglCreatePbufferSurface(self._egl_display, self._egl_config, pbuffer_attribs)
        if not self._egl_surface:
            raise RuntimeError("Failed to create EGL pbuffer surface")
            
        eglBindAPI(EGL_OPENGL_API)
        
        self._egl_context = eglCreateContext(self._egl_display, self._egl_config, EGL_NO_CONTEXT, None)
        if not self._egl_context:
            raise RuntimeError("Failed to create EGL context")
            
        if not eglMakeCurrent(self._egl_display, self._egl_surface, self._egl_surface, self._egl_context):
            raise RuntimeError("Failed to make EGL context current")

        self._egl_fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self._egl_fbo)
        
        self._egl_color_rb = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self._egl_color_rb)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, width, height)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, self._egl_color_rb)
        
        self._egl_depth_rb = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self._egl_depth_rb)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width, height)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self._egl_depth_rb)
        
        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("EGL FBO is incomplete")

    def _Setup_qt_context(self, width: int, height: int) -> None:
        """PySide6를 활용한 오프스크린 컨텍스트 생성 (EGL 실패 시 사용)."""
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
        if self._use_egl:
            self._Teardown_egl_context()
        else:
            self._Teardown_qt_context()

    def _Teardown_egl_context(self) -> None:
        try:
            from OpenGL.EGL import eglMakeCurrent, eglDestroyContext, eglDestroySurface, eglTerminate, EGL_NO_CONTEXT, EGL_NO_SURFACE
            from OpenGL.GL import glDeleteFramebuffers, glDeleteRenderbuffers
            
            if hasattr(self, '_egl_fbo') and self._egl_fbo:
                glDeleteFramebuffers(1, [self._egl_fbo])
                self._egl_fbo = None
            if hasattr(self, '_egl_color_rb') and self._egl_color_rb:
                glDeleteRenderbuffers(1, [self._egl_color_rb])
                self._egl_color_rb = None
            if hasattr(self, '_egl_depth_rb') and self._egl_depth_rb:
                glDeleteRenderbuffers(1, [self._egl_depth_rb])
                self._egl_depth_rb = None
                
            if hasattr(self, '_egl_display') and self._egl_display:
                eglMakeCurrent(self._egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)
                if hasattr(self, '_egl_context') and self._egl_context:
                    eglDestroyContext(self._egl_display, self._egl_context)
                    self._egl_context = None
                if hasattr(self, '_egl_surface') and self._egl_surface:
                    eglDestroySurface(self._egl_display, self._egl_surface)
                    self._egl_surface = None
                eglTerminate(self._egl_display)
                self._egl_display = None
        except ImportError:
            pass

    def _Teardown_qt_context(self) -> None:
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
        self, root_node: Base_Node, camera_node: Camera,
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
        if self._use_egl:
            from OpenGL.GL import glBindFramebuffer, GL_FRAMEBUFFER
            if hasattr(self, '_egl_fbo') and self._egl_fbo is not None:
                glBindFramebuffer(GL_FRAMEBUFFER, self._egl_fbo)
        else:
            if self._fbo:
                self._fbo.bind()

        from spatial_toolbox.graphics.openGL.renderer import OpenGL_Renderer
        from spatial_toolbox.scene.node.utils.traversal import walk_nodes

        _renderer = OpenGL_Renderer(width, height)
        _renderer.Configure_lighting(self._config)

        # Build render queue
        _render_queue = list(walk_nodes(root_node, lambda x: hasattr(x, "source_key") and x.source_key is not None))

        _results = _renderer.Render(_render_queue, camera_node, self._passes)

        if self._use_egl:
            from OpenGL.GL import glBindFramebuffer, GL_FRAMEBUFFER
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
        else:
            if self._fbo:
                self._fbo.release()

        return _results
