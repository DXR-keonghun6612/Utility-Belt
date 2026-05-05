import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import gluProject
from spatial_toolbox.scene.node import Base_Node
from ..orbit_cam import Orbit_Camera


class _Transform_Math:
    """마우스 2D 델타를 3D 행렬 변화량으로 변환하는 내부 수학 유틸리티."""

    @staticmethod
    def _Get_screen_direction(axis_local: np.ndarray) -> np.ndarray:
        _mv = glGetDoublev(GL_MODELVIEW_MATRIX)
        _proj = glGetDoublev(GL_PROJECTION_MATRIX)
        _vp = glGetIntegerv(GL_VIEWPORT)
        _p0 = np.array(gluProject(0.0, 0.0, 0.0, _mv, _proj, _vp)[:2])
        _p1 = np.array(gluProject(*axis_local, _mv, _proj, _vp)[:2])
        _screen_vec = _p1 - _p0
        _norm = np.linalg.norm(_screen_vec)
        return _screen_vec / _norm if _norm > 1e-6 else np.zeros(2, dtype=np.float32)

    @staticmethod
    def Get_translation_delta(
        axis_local: np.ndarray, dx: float, dy: float, sensitivity: float
    ) -> np.ndarray:
        _screen_dir = _Transform_Math._Get_screen_direction(axis_local)
        _move_amount = np.dot(np.array([dx, -dy], dtype=np.float32), _screen_dir) * sensitivity
        _delta_mat = np.eye(4, dtype=np.float32)
        _delta_mat[:3, 3] = axis_local * _move_amount
        return _delta_mat

    @staticmethod
    def Get_rotation_delta(
        axis_key: str, axis_local: np.ndarray,
        dx: float, dy: float, screen_x: float, screen_y: float
    ) -> np.ndarray:
        _mv = glGetDoublev(GL_MODELVIEW_MATRIX)
        _proj = glGetDoublev(GL_PROJECTION_MATRIX)
        _vp = glGetIntegerv(GL_VIEWPORT)
        _center = np.array(gluProject(0.0, 0.0, 0.0, _mv, _proj, _vp)[:2])
        _curr = np.array([screen_x, screen_y], dtype=np.float32)
        _prev = np.array([screen_x - dx, screen_y + dy], dtype=np.float32)
        _v_curr = _curr - _center
        _v_prev = _prev - _center
        _cross = _v_prev[0] * _v_curr[1] - _v_prev[1] * _v_curr[0]
        _angle = np.arctan2(_cross, np.dot(_v_prev, _v_curr))
        _axis_view_z = (_mv[0][2] * axis_local[0] +
                        _mv[1][2] * axis_local[1] +
                        _mv[2][2] * axis_local[2])
        if _axis_view_z < 0:
            _angle = -_angle
        _cos, _sin = np.cos(_angle), np.sin(_angle)
        _delta_mat = np.eye(4, dtype=np.float32)
        if 'X' in axis_key:
            _delta_mat[1:3, 1:3] = [[_cos, -_sin], [_sin, _cos]]
        elif 'Y' in axis_key:
            _delta_mat[0, 0::2] = [_cos, _sin]
            _delta_mat[2, 0::2] = [-_sin, _cos]
        elif 'Z' in axis_key:
            _delta_mat[:2, :2] = [[_cos, -_sin], [_sin, _cos]]
        return _delta_mat

    @staticmethod
    def Apply_delta(local_rigid: np.ndarray, delta_matrix: np.ndarray) -> np.ndarray:
        return local_rigid @ delta_matrix


class Transform_Gizmo:
    """선택된 씬 노드 위에 오버레이되는 3축 이동/회전 핸들 뷰포트 노드.

    씬 트리에 속하지 않는 독립 뷰포트 노드로, 자체적으로 픽킹 패스와
    오버레이 렌더링을 수행하고 마우스 드래그를 노드 변환에 반영함.
    """

    def __init__(self):
        self.active_axis: str | None = None

        self._axis_vectors = {
            'X': np.array([1, 0, 0], dtype=np.float32),
            'Y': np.array([0, 1, 0], dtype=np.float32),
            'Z': np.array([0, 0, 1], dtype=np.float32)
        }
        self._axis_colors = {
            'X': (1.0, 0.1, 0.1), 'Y': (0.1, 1.0, 0.1), 'Z': (0.1, 0.1, 1.0),
            'ACTIVE': (1.0, 1.0, 0.1)
        }
        self._pick_colors = {
            (255, 0, 0): 'X',   (0, 255, 0): 'Y',   (0, 0, 255): 'Z',
            (128, 0, 0): 'RX',  (0, 128, 0): 'RY',  (0, 0, 128): 'RZ'
        }

        self.sensitivity = 0.01
        self.scale_factor = 0.15
        self.arc_radius = 1.2

    # ==========================================
    # 픽킹 및 상태 제어
    # ==========================================

    def Pick_axis(self, x: int, y: int, camera: Orbit_Camera, node: Base_Node | None) -> str | None:
        """기즈모 핸들을 픽킹하여 활성 축을 결정함. makeCurrent 상태에서 호출해야 함."""
        if node is None:
            self.active_axis = None
            return None

        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT)
        glDisable(GL_LIGHTING); glDisable(GL_BLEND)
        glDisable(GL_LINE_SMOOTH); glDisable(GL_MULTISAMPLE)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        camera.Apply_view()

        glLineWidth(15.0)
        self._Draw_core(node, is_picking=True)
        glFlush()

        _pixel = glReadPixels(x, y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)
        glPopAttrib()

        if isinstance(_pixel, bytes):
            self.active_axis = self._pick_colors.get(tuple(_pixel), None)
            return self.active_axis

        self.active_axis = None
        return None

    def Deactivate(self) -> None:
        self.active_axis = None

    # ==========================================
    # 렌더링
    # ==========================================

    def Draw(self, camera: Orbit_Camera, node: Base_Node | None) -> None:
        """선택 노드 위에 기즈모 핸들을 오버레이로 렌더링함."""
        if node is None:
            return

        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_LINE_BIT)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        camera.Apply_view()
        glLineWidth(3.0)
        self._Draw_core(node, is_picking=False)

        glPopAttrib()
        glEnable(GL_DEPTH_TEST)

    def _Draw_core(self, node: Base_Node, is_picking: bool) -> None:
        _world_mat = node.world_matrix
        _world_pos = _world_mat[:3, 3]

        glPushMatrix()
        glTranslatef(*_world_pos)

        _mv = glGetDoublev(GL_MODELVIEW_MATRIX)
        _scale = max(np.linalg.norm(_mv[3][:3]) * self.scale_factor, 0.01)
        glScalef(_scale, _scale, _scale)

        _rot = np.eye(4, dtype=np.float32)
        _rot[:3, :3] = _world_mat[:3, :3].copy()
        for i in range(3):
            _col = _rot[:3, i]
            _n = np.linalg.norm(_col)
            if _n > 1e-6:
                _rot[:3, i] /= _n
        glMultMatrixf(_rot.T)

        for _ax in ['X', 'Y', 'Z']:
            _active = (self.active_axis == _ax) or (self.active_axis == f'R{_ax}')
            _color = self._axis_colors['ACTIVE'] if _active else self._axis_colors[_ax]

            if is_picking:
                glColor3ub(*[k for k, v in self._pick_colors.items() if v == _ax][0])
            else:
                glColor3f(*_color)

            glBegin(GL_LINES)
            glVertex3f(0, 0, 0)
            glVertex3f(*(self._axis_vectors[_ax] * 2.0))
            glEnd()

            if is_picking:
                glColor3ub(*[k for k, v in self._pick_colors.items() if v == f'R{_ax}'][0])
            else:
                glColor3f(*_color)

            self._Draw_arc(_ax)

        glPopMatrix()

    def _Draw_arc(self, axis: str) -> None:
        glBegin(GL_LINE_STRIP)
        for _a in np.linspace(0, np.pi / 2, 32):
            _c, _s = np.cos(_a) * self.arc_radius, np.sin(_a) * self.arc_radius
            if axis == 'X':   glVertex3f(0.0, _c, _s)
            elif axis == 'Y': glVertex3f(_s, 0.0, _c)
            elif axis == 'Z': glVertex3f(_c, _s, 0.0)
        glEnd()

    # ==========================================
    # 변환 적용
    # ==========================================

    def Apply_drag(
        self, node: Base_Node,
        dx: float, dy: float,
        screen_x: float, screen_y: float
    ) -> None:
        """마우스 드래그를 씬 노드의 로컬 변환에 반영함."""
        if not node or self.active_axis is None:
            return

        glPushMatrix()
        glMultMatrixf(node.world_matrix.T)

        _delta = np.eye(4, dtype=np.float32)

        if self.active_axis in ('X', 'Y', 'Z'):
            _delta = _Transform_Math.Get_translation_delta(
                self._axis_vectors[self.active_axis], dx, dy, self.sensitivity
            )
        elif self.active_axis in ('RX', 'RY', 'RZ'):
            _delta = _Transform_Math.Get_rotation_delta(
                self.active_axis, self._axis_vectors[self.active_axis[-1]],
                dx, dy, screen_x, screen_y
            )

        glPopMatrix()
        node.local_rigid = _Transform_Math.Apply_delta(node.local_rigid, _delta)
