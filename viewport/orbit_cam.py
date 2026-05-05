import numpy as np
from OpenGL.GL import glMatrixMode, glLoadIdentity, GL_PROJECTION, GL_MODELVIEW
from OpenGL.GLU import gluLookAt, gluPerspective


class Orbit_Camera:
    """극좌표계 기반의 3D 궤도 카메라 제어 및 View/Projection 관리 클래스."""

    def __init__(self):
        self.target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.distance = 15.0
        self.pitch = 30.0
        self.yaw = 45.0

        self.fov = 45.0
        self.near_clip = 0.1   # [m]
        self.far_clip = 1000.0 # [m]

        self.pan_speed = 0.01
        self.rot_speed = 0.5
        self.zoom_speed = 0.5

    # ==========================================
    # 상호작용
    # ==========================================

    def Rotate(self, dx: float, dy: float) -> None:
        # yaw: 우측 드래그 → 씬이 오른쪽으로 회전 → 카메라가 왼쪽으로 이동 → yaw 감소
        # pitch: Qt Y는 아래가 양수이므로 dy 부호 반전하여 위 드래그 = pitch 증가
        self.yaw -= dx * self.rot_speed
        self.pitch = max(-89.0, min(89.0, self.pitch - dy * self.rot_speed))

    def Pan(self, dx: float, dy: float) -> None:
        _yaw_rad = np.radians(self.yaw)
        _pitch_rad = np.radians(self.pitch)

        _right = np.array([np.cos(_yaw_rad), 0.0, -np.sin(_yaw_rad)], dtype=np.float32)
        _up = np.array([
            -np.sin(_yaw_rad) * np.sin(_pitch_rad),
            np.cos(_pitch_rad),
            -np.cos(_yaw_rad) * np.sin(_pitch_rad),
        ], dtype=np.float32)

        _f = self.distance * self.pan_speed
        self.target -= _right * (dx * _f)
        self.target += _up * (dy * _f)

    def Zoom_to_cursor(self, delta: float, ndc_x: float, ndc_y: float, aspect: float) -> None:
        """커서 방향으로 이동하며 줌 (AutoCAD 스타일).

        ndc_x, ndc_y: 커서의 정규화 좌표 ([-1, 1], 우상단이 양수).
        """
        _zoom_amount = delta * self.zoom_speed
        _new_dist = max(0.1, self.distance - _zoom_amount)
        _actual = self.distance - _new_dist

        if abs(_actual) > 1e-6:
            _half_h = self.distance * np.tan(np.radians(self.fov * 0.5))
            _half_w = _half_h * aspect

            _yaw_rad = np.radians(self.yaw)
            _pitch_rad = np.radians(self.pitch)
            _right = np.array([np.cos(_yaw_rad), 0.0, -np.sin(_yaw_rad)], dtype=np.float32)
            _up = np.array([
                -np.sin(_yaw_rad) * np.sin(_pitch_rad),
                np.cos(_pitch_rad),
                -np.cos(_yaw_rad) * np.sin(_pitch_rad),
            ], dtype=np.float32)

            _cursor_world = _right * (ndc_x * _half_w) + _up * (ndc_y * _half_h)
            self.target += _cursor_world * (_actual / self.distance)

        self.distance = _new_dist

    # ==========================================
    # OpenGL 파이프라인 상태 주입
    # ==========================================

    def Update_projection(self, width: int, height: int, unit_length: float = 1.0) -> None:
        """창 크기 변경 시 Projection 행렬을 갱신함.

        near/far는 [m] 단위로 보관되며 unit_length로 나눠 씬 단위로 환산됨.
        """
        if height == 0:
            height = 1
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(
            self.fov,
            width / height,
            self.near_clip / unit_length,
            self.far_clip / unit_length,
        )

    def Apply_view(self) -> None:
        """매 프레임 ModelView 행렬에 카메라 위치를 세팅함."""
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        _yaw_rad = np.radians(self.yaw)
        _pitch_rad = np.radians(self.pitch)

        _eye_x = self.target[0] + self.distance * np.cos(_pitch_rad) * np.sin(_yaw_rad)
        _eye_y = self.target[1] + self.distance * np.sin(_pitch_rad)
        _eye_z = self.target[2] + self.distance * np.cos(_pitch_rad) * np.cos(_yaw_rad)

        gluLookAt(
            _eye_x, _eye_y, _eye_z,
            self.target[0], self.target[1], self.target[2],
            0.0, 1.0, 0.0,
        )
