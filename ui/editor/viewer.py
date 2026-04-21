from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QMouseEvent, QWheelEvent

from spatial_toolbox.scene import Controller as Stage_Controller
from viewport.view import Orbit_Camera
from viewport.renderer import Scene_Renderer
from viewport.tool.selection import Selection_Controller
from viewport.tool.gizmo import Gizmo_Controller

from ui.core.event_bus import EVENT_BUS

class Viewer_Panel(QOpenGLWidget):
    """Qt 프레임워크와 독립된 3D 뷰포트 코어 엔진을 연결하는 메인 UI 패널."""

    def __init__(self, stage: Stage_Controller, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 1. 도메인 의존성 주입 및 초기화
        self.stage = stage
        self.camera = Orbit_Camera()
        self.renderer = Scene_Renderer()
        self.selection = Selection_Controller()
        self.gizmo = Gizmo_Controller()

        # 2. UI 상태 변수
        self._last_mouse_pos = None

        # 3. 렌더링 루프 (약 60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

        # 4. 이벤트 버스 구독
        EVENT_BUS.property_changed.connect(self._On_property_changed)
        EVENT_BUS.scene_mutated.connect(self.update)
        EVENT_BUS.scene_loaded.connect(self._On_scene_loaded)
        EVENT_BUS.camera_changed.connect(self._On_camera_changed)
        EVENT_BUS.selection_changed.connect(self._On_selection_changed)

    def _On_scene_loaded(self):
        self.selection.selected_node = None
        self._Refresh_projection()
        self.update()

    def _On_camera_changed(self):
        # fov/near/far 변경 등 렌즈 파라미터 갱신을 커버
        self._Refresh_projection()
        self.update()

    def _On_property_changed(self):
        # stage.unit_length 편집 반영을 위해 투영 재빌드
        self._Refresh_projection()
        self.update()

    def _On_selection_changed(self, nodes: list):
        self.selection.selected_node = nodes[0] if len(nodes) == 1 else None
        self.update()

    def _Refresh_projection(self) -> None:
        """현재 stage.unit_length 기준으로 Orbit_Camera 투영 행렬 재계산."""
        self.makeCurrent()
        self.camera.Update_projection(
            self.width(), self.height(), self.stage.unit_length
        )

    # ==========================================
    # Qt OpenGL 파이프라인 오버라이딩
    # ==========================================

    def initializeGL(self):
        """OpenGL 컨텍스트가 생성된 직후 1회 호출됨."""
        self.renderer.Initialize()

    def resizeGL(self, w: int, h: int):
        """위젯의 크기가 변경될 때 호출됨."""
        self.camera.Update_projection(w, h, self.stage.unit_length)

    def paintGL(self):
        """매 프레임 화면을 그림 (Timer에 의해 트리거됨)."""
        _root = self.stage.root
        _selected = self.selection.selected_node

        # 1. 씬의 3D 객체 렌더링
        self.renderer.Render_frame(_root, self.camera, _selected)
        
        # 2. 선택된 객체가 있다면 그 위에 기즈모 오버레이 렌더링
        if _selected:
            self.gizmo.Render_overlay(self.camera, _selected)

    # ==========================================
    # 입력 이벤트 라우팅
    # ==========================================

    def mousePressEvent(self, event: QMouseEvent):
        """클릭 시 픽킹(선택 및 기즈모 활성화) 처리."""
        self._last_mouse_pos = event.position().toPoint()
        _x = self._last_mouse_pos.x()
        _y = self.height() - self._last_mouse_pos.y() # OpenGL Y축 역전
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.makeCurrent() # OpenGL 컨텍스트 활성화
            
            # 1. 먼저 기즈모의 축(핸들)을 클릭했는지 판별
            _axis = self.gizmo.Pick_gizmo_axis(
                _x, _y, self.camera, self.selection.selected_node)
            
            # 2. 기즈모를 클릭하지 않았다면 씬 내부의 일반 객체 픽킹 시도
            if not _axis:
                _node = self.selection.Pick(
                    _x, _y, self.stage.root, self.camera, self.renderer)
                # 속성창 등 다른 UI 갱신을 위해 시그널 발송
                EVENT_BUS.selection_changed.emit([_node] if _node else [])

    def mouseMoveEvent(self, event: QMouseEvent):
        """드래그 시 기즈모 변환 또는 카메라 조작 처리."""
        _current_pos = event.position().toPoint()
        
        if self._last_mouse_pos:
            _dx = _current_pos.x() - self._last_mouse_pos.x()
            _dy = _current_pos.y() - self._last_mouse_pos.y()

            if event.buttons() & Qt.MouseButton.LeftButton:
                if self.gizmo.active_axis and self.selection.selected_node:
                    self.makeCurrent()
                    _sx = float(_current_pos.x())
                    _sy = float(self.height() - _current_pos.y())
                    self.gizmo.Apply_transform_drag(
                        self.selection.selected_node,
                        float(_dx), float(_dy), _sx, _sy
                    )
                else:
                    # 기즈모 비활성 상태라면 카메라 궤도 회전
                    self.camera.Rotate(float(_dx), float(_dy))
                    EVENT_BUS.camera_moved.emit()

            elif event.buttons() & Qt.MouseButton.MiddleButton:
                # 휠 클릭 드래그는 카메라 패닝
                self.camera.Pan(float(_dx), float(_dy))
                EVENT_BUS.camera_moved.emit()

        self._last_mouse_pos = _current_pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """드래그 종료 시 기즈모 활성 상태 해제."""
        self.gizmo.Deactivate_axis()

    def wheelEvent(self, event: QWheelEvent):
        """마우스 휠 스크롤 시 카메라 줌 처리."""
        _delta = event.angleDelta().y() / 120.0 # 일반적인 마우스 휠 1틱
        self.camera.Zoom(_delta)
        EVENT_BUS.camera_moved.emit()
