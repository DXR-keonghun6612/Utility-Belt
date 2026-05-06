from PySide6.QtCore import Qt, QTimer
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QCloseEvent, QMouseEvent, QWheelEvent

from spatial_toolbox.scene import Controller as Stage_Controller
from viewport.orbit_cam import Orbit_Camera
from viewport.renderer import Scene_Renderer
from viewport.utils.selection import Selection_Controller
from viewport.node.gizmo import Transform_Gizmo

from ui.event_bus import EVENT_BUS


class Viewer_Panel(QOpenGLWidget):
    """Qt 프레임워크와 독립된 3D 뷰포트 코어 엔진을 연결하는 메인 UI 패널."""

    def __init__(self, stage: Stage_Controller, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.stage = stage
        self.camera = Orbit_Camera()
        self.renderer = Scene_Renderer()
        self.selection = Selection_Controller()
        self.gizmo = Transform_Gizmo()
        self._is_cleaned_up = False

        self._last_mouse_pos = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

        EVENT_BUS.property_changed.connect(self._On_property_changed)
        EVENT_BUS.scene_mutated.connect(self.update)
        EVENT_BUS.scene_loaded.connect(self._On_scene_loaded)
        EVENT_BUS.camera_changed.connect(self._On_camera_changed)
        EVENT_BUS.selection_changed.connect(self._On_selection_changed)
        EVENT_BUS.viewer_config_changed.connect(self.update)

    def _On_scene_loaded(self):
        self.selection.selected_node = None
        self._Refresh_projection()
        self.update()

    def _On_camera_changed(self):
        self._Refresh_projection()
        self.update()

    def _On_property_changed(self):
        self._Refresh_projection()
        self.update()

    def _On_selection_changed(self, nodes: list):
        self.selection.selected_node = nodes[0] if len(nodes) == 1 else None
        self.update()

    def _Refresh_projection(self) -> None:
        self.makeCurrent()
        self.camera.Update_projection(self.width(), self.height(), self.stage.unit_length)
        self.doneCurrent()

    def _Cleanup_gl_resources(self) -> None:
        """Stops repaint activity and frees cached GL resources once."""
        if self._is_cleaned_up:
            return
        self._is_cleaned_up = True

        self.timer.stop()
        if self.context() is None:
            return

        self.makeCurrent()
        try:
            self.renderer.Clear_resources()
        finally:
            self.doneCurrent()

    # ==========================================
    # Qt OpenGL 파이프라인 오버라이딩
    # ==========================================

    def initializeGL(self):
        self.renderer.Initialize()

    def resizeGL(self, w: int, h: int):
        self.camera.Update_projection(w, h, self.stage.unit_length)

    def paintGL(self):
        _root = self.stage.root
        _selected = self.selection.selected_node
        self.renderer.Render_frame(_root, self.camera, _selected)
        if _selected:
            self.gizmo.Draw(self.camera, _selected)

    # ==========================================
    # 입력 이벤트 라우팅
    # ==========================================

    def mousePressEvent(self, event: QMouseEvent):
        self._last_mouse_pos = event.position().toPoint()
        _x = self._last_mouse_pos.x()
        _y = self.height() - self._last_mouse_pos.y()

        if event.button() == Qt.MouseButton.LeftButton:
            self.makeCurrent()
            _axis = self.gizmo.Pick_axis(_x, _y, self.camera, self.selection.selected_node)
            if not _axis:
                _node = self.selection.Pick(_x, _y, self.stage.root, self.camera, self.renderer)
                EVENT_BUS.selection_changed.emit([_node] if _node else [])

    def mouseMoveEvent(self, event: QMouseEvent):
        _current_pos = event.position().toPoint()

        if self._last_mouse_pos:
            _dx = float(_current_pos.x() - self._last_mouse_pos.x())
            _dy = float(_current_pos.y() - self._last_mouse_pos.y())

            if event.buttons() & Qt.MouseButton.LeftButton:
                if self.gizmo.active_axis and self.selection.selected_node:
                    self.makeCurrent()
                    self.gizmo.Apply_drag(
                        self.selection.selected_node, _dx, _dy,
                        float(_current_pos.x()),
                        float(self.height() - _current_pos.y()),
                    )

            elif event.buttons() & Qt.MouseButton.MiddleButton:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.camera.Pan(_dx, _dy)
                else:
                    self.camera.Rotate(_dx, _dy)
                EVENT_BUS.camera_moved.emit()

        self._last_mouse_pos = _current_pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.gizmo.Deactivate()

    def wheelEvent(self, event: QWheelEvent):
        _delta = event.angleDelta().y() / 120.0
        _pos = event.position()
        _ndc_x = (2.0 * _pos.x() / self.width()) - 1.0
        _ndc_y = 1.0 - (2.0 * _pos.y() / self.height())
        self.camera.Zoom_to_cursor(_delta, _ndc_x, _ndc_y, self.width() / max(self.height(), 1))
        EVENT_BUS.camera_moved.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._Cleanup_gl_resources()
        super().closeEvent(event)
