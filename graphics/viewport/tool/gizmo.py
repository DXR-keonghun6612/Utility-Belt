import numpy as np
from OpenGL.GL import *
from data.scene.node import Scene_Node
from ..view import Orbit_Camera
from ..transform import Transform_Math

class Gizmo_Controller:
    """선택된 객체의 월드 포즈에 맞춰 3D 조작 핸들(Gizmo)을 그리고 아핀 변환을 제어함."""

    def __init__(self):
        # 1. 상태 관리
        self.active_axis: str | None = None # 현재 드래그 중인 축 (예: 'X', 'RY')
        
        # 2. 기즈모 정의 데이터 (로컬 축)
        self._axis_vectors = {
            'X': np.array([1, 0, 0], dtype=np.float32),
            'Y': np.array([0, 1, 0], dtype=np.float32),
            'Z': np.array([0, 0, 1], dtype=np.float32)
        }
        # 시각적 색상 (X:R, Y:G, Z:B)
        self._axis_colors = {
            'X': (1.0, 0.1, 0.1), 'Y': (0.1, 1.0, 0.1), 'Z': (0.1, 0.1, 1.0),
            'ACTIVE': (1.0, 1.0, 0.1) # 활성화된 축은 노란색
        }
        # 기즈모 픽킹용 고유 컬러 키 (ubyte)
        self._pick_colors = {
            (255, 0, 0): 'X', (0, 255, 0): 'Y', (0, 0, 255): 'Z', # 이동 축
            (128, 0, 0): 'RX', (0, 128, 0): 'RY', (0, 0, 128): 'RZ' # 회전 호
        }

        # 3. 조작 및 시각 파라미터
        self.sensitivity = 0.01 # 변환 민감도
        self.scale_factor = 0.15 # 카메라 거리에 따른 기즈모 크기 비율
        self.arc_radius = 1.2 # 회전 호의 반지름

    # ==========================================
    # 픽킹 및 상태 제어
    # ==========================================

    def Pick_gizmo_axis(self, x: int, y: int, camera: Orbit_Camera, selected_node: Scene_Node | None) -> str | None:
        """기즈모 자체를 픽킹하여 활성화할 조작 축을 결정함.
        
        [주의] OpenGL 컨텍스트가 makeCurrent된 상태에서 호출되어야 함.
        """
        if selected_node is None:
            self.active_axis = None
            return None

        # 상태 백업 및 순수 컬러 렌더링 모드 설정 (라이팅, 안티앨리어싱 끔)
        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT)
        glDisable(GL_LIGHTING); glDisable(GL_BLEND)
        glDisable(GL_LINE_SMOOTH); glDisable(GL_MULTISAMPLE)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        camera.Apply_view()

        # 기즈모 픽킹용 렌더링 (굵은 선으로 적중률 향상)
        glLineWidth(15.0)
        self._Draw_gizmo_core(selected_node, is_picking=True)
        glFlush()

        # 픽셀 읽기
        _pixel = glReadPixels(x, y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)
        glPopAttrib() # 상태 복구

        if isinstance(_pixel, bytes):
            _color_key = tuple(_pixel)
            self.active_axis = self._pick_colors.get(_color_key, None)
            return self.active_axis
            
        self.active_axis = None
        return None

    def Deactivate_axis(self) -> None:
        """마우스 버튼을 뗐을 때 활성화된 축 상태를 초기화함."""
        self.active_axis = None

    # ==========================================
    # 렌더링 오버레이 (Overlay Rendering)
    # ==========================================

    def Render_overlay(self, camera: Orbit_Camera, selected_node: Scene_Node | None):
        """메인 렌더링 위에 기즈모 조작 핸들을 오버레이로 그려 시각적 피드백을 제공함."""
        if selected_node is None: return

        # 뷰포트 상태 저장
        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_LINE_BIT)
        
        # 기즈모는 깊이 테스트를 끄거나 뎁스 레인지를 조절하여 항상 위에 보이게 함
        glDisable(GL_DEPTH_TEST) 
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND) # 선 부드럽게
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        camera.Apply_view() # 카메라 상태는 유지

        glLineWidth(3.0)
        self._Draw_gizmo_core(selected_node, is_picking=False)

        glPopAttrib() # 상태 복구
        glEnable(GL_DEPTH_TEST) # 깊이 테스트 다시 킴

    def _Draw_gizmo_core(self, node: Scene_Node, is_picking: bool):
        """기즈모의 기하학적 형태(선, 호)를 그리는 핵심 루틴."""
        # 1. 월드 포즈 획득 및 OpenGL 행렬 스택 적용
        _world_mat = node.world_matrix
        _slice_xyz = slice(0, 3)
        _world_pos = _world_mat[_slice_xyz, 3]
        
        glPushMatrix()
        
        # 기즈모 원점을 객체의 월드 위치로 이동
        glTranslatef(*_world_pos)
        
        # 2. 다이나믹 스케일링: 카메라 거리에 관계없이 기즈모 크기를 일정하게 유지
        _mv = glGetDoublev(GL_MODELVIEW_MATRIX)
        # 카메라 좌표계 원점(0,0,0)에서 현재 객체(모델뷰 이동량)까지의 거리 계산
        _distance = np.linalg.norm(_mv[3][_slice_xyz])
        _scale = max(_distance * self.scale_factor, 0.01)
        glScalef(_scale, _scale, _scale)
        
        # 3. 객체의 월드 회전 상태를 기즈모 축에 적용 (정규화 필수)
        _world_rot_mat = np.eye(4, dtype=np.float32)
        _world_rot_mat[_slice_xyz, _slice_xyz] = _world_mat[_slice_xyz, _slice_xyz].copy()
        # 스케일 성분 제거 및 직교 정규화 (Gram-Schmidt 부재 시 최소한의 보정)
        for i in range(3):
            _col = _world_rot_mat[_slice_xyz, i]
            _norm = np.linalg.norm(_col)
            if _norm > 1e-6: _world_rot_mat[_slice_xyz, i] /= _norm
            
        glMultMatrixf(_world_rot_mat.T)

        # 4. 축 및 호 그리기 루프
        for _ax in ['X', 'Y', 'Z']:
            # 색상 결정 논리
            _is_active = (self.active_axis == _ax) or (self.active_axis == f'R{_ax}')
            _color = self._axis_colors['ACTIVE'] if _is_active else self._axis_colors[_ax]
            
            # --- 이동 축 (Line) 그리기 ---
            if is_picking:
                # 픽킹 모드일 땐 고유ubyte 색상
                _pk_c = [k for k, v in self._pick_colors.items() if v == _ax][0]
                glColor3ub(*_pk_c)
            else:
                # 시각화 모드일 땐 일반float 색상
                glColor3f(*_color)

            glBegin(GL_LINES)
            glVertex3f(0, 0, 0)
            glVertex3f(*(self._axis_vectors[_ax] * 2.0)) # 축 길이 2배
            glEnd()

            # --- 회전 호 (Arc) 그리기 ---
            _rot_key = f'R{_ax}'
            if is_picking:
                _pk_rc = [k for k, v in self._pick_colors.items() if v == _rot_key][0]
                glColor3ub(*_pk_rc)
            else:
                glColor3f(*_color)
                
            self._Draw_rotation_arc(_ax)

        glPopMatrix()

    def _Draw_rotation_arc(self, axis: str):
        """특정 축을 기준으로 90도 회전 호(Arc)를 그림."""
        glBegin(GL_LINE_STRIP)
        _segments = 32
        _angles = np.linspace(0, np.pi / 2, _segments) # 1사분면 호
        for _a in _angles:
            _cos, _sin = np.cos(_a) * self.arc_radius, np.sin(_a) * self.arc_radius
            if axis == 'X': glVertex3f(0.0, _cos, _sin) # YZ 평면
            elif axis == 'Y': glVertex3f(_sin, 0.0, _cos) # ZX 평면
            elif axis == 'Z': glVertex3f(_cos, _sin, 0.0) # XY 평면
        glEnd()

    # ==========================================
    # 상호작용 및 변환 조립 (Interaction)
    # ==========================================

    def Apply_transform_drag(
        self, node: Scene_Node,
        dx: float, dy: float,
        screen_x: float, screen_y: float
    ):
        """마우스 드래그 이벤트를 받아 수학 모듈을 호출하고 노드의 포즈를 최종 업데이트함.

        Args:
            node: 변환 대상 씬 노드.
            dx: 위젯 좌표계 마우스 X 변위 (px).
            dy: 위젯 좌표계 마우스 Y 변위 (px, 하향 양수).
            screen_x: 현재 마우스 X (OpenGL 스크린 좌표).
            screen_y: 현재 마우스 Y (OpenGL 스크린 좌표, 상향 양수).
        """
        if not node or self.active_axis is None: return

        # OpenGL 상태 머신을 객체의 월드 포즈로 이동 (gluProject 연산 위함)
        glPushMatrix()
        glMultMatrixf(node.world_matrix.T)

        _delta_mat = np.eye(4, dtype=np.float32)

        if self.active_axis in ['X', 'Y', 'Z']:
            _axis_vec = self._axis_vectors[self.active_axis]
            _delta_mat = Transform_Math.Get_translation_delta(
                _axis_vec, dx, dy, self.sensitivity
            )
        elif self.active_axis in ['RX', 'RY', 'RZ']:
            _axis_key = self.active_axis[-1]
            _axis_vec = self._axis_vectors[_axis_key]
            _delta_mat = Transform_Math.Get_rotation_delta(
                self.active_axis, _axis_vec, dx, dy, screen_x, screen_y
            )

        glPopMatrix()

        node.local_matrix = Transform_Math.Apply_delta(
            node.local_matrix, _delta_mat
        )
