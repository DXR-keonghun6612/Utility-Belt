import numpy as np
from OpenGL.GL import (
    glMatrixMode, glLoadIdentity, glLoadMatrixf,
    GL_PROJECTION, GL_MODELVIEW
)
from OpenGL.GLU import gluLookAt

from spatial_toolbox.scene.node import Build_gl_projection

class Orbit_Camera:
    """극좌표계 기반의 3D 궤도 카메라(Orbit Camera) 제어 및 View/Projection 관리 클래스."""

    def __init__(self):
        # 1. 카메라 시점 상태 (극좌표계)
        self.target = np.array([0.0, 0.0, 0.0], dtype=np.float32) # 바라보는 중심점
        self.distance = 15.0                                      # 중심점으로부터의 거리
        self.pitch = 30.0                                         # 위아래 회전 각도 (고도)
        self.yaw = 45.0                                           # 좌우 회전 각도 (방위각)

        # 2. 렌즈(투영) 설정
        self.fov = 45.0
        # near/far clip — [m] 고정. Update_projection에서 unit_length로 환산됨.
        self.near_clip = 0.1
        self.far_clip = 1000.0

        # 3. 조작 민감도
        self.pan_speed = 0.01
        self.rot_speed = 0.5
        self.zoom_speed = 0.5

    # ==========================================
    # 상호작용 (Interaction) 수학 연산
    # ==========================================

    def Rotate(self, dx: float, dy: float) -> None:
        """마우스 델타를 기반으로 카메라의 궤도를 회전함."""
        self.yaw += dx * self.rot_speed
        self.pitch += dy * self.rot_speed
        
        # 짐벌락(Gimbal Lock) 및 화면 뒤집힘 방지를 위한 Pitch 클램핑
        self.pitch = max(-89.0, min(89.0, self.pitch))

    def Pan(self, dx: float, dy: float) -> None:
        """카메라의 현재 시선 방향에 직교하는 평면(View Plane) 상에서 타겟을 이동함."""
        # 방위각(Yaw)과 고도(Pitch)를 라디안으로 변환
        _yaw_rad = np.radians(self.yaw)
        _pitch_rad = np.radians(self.pitch)

        # 카메라의 로컬 Right 벡터와 Up 벡터 산출
        _right = np.array([
            np.cos(_yaw_rad),
            0.0,
            -np.sin(_yaw_rad)
        ], dtype=np.float32)

        _up = np.array([
            -np.sin(_yaw_rad) * np.sin(_pitch_rad),
            np.cos(_pitch_rad),
            -np.cos(_yaw_rad) * np.sin(_pitch_rad)
        ], dtype=np.float32)

        # 거리에 비례하여 패닝 속도 보정 (멀리 있을수록 더 많이 이동해야 자연스러움)
        _distance_factor = self.distance * self.pan_speed
        
        # OpenGL은 Y축이 마우스 이동과 반대이므로 dy 부호 반전
        self.target -= _right * (dx * _distance_factor)
        self.target += _up * (dy * _distance_factor)

    def Zoom(self, delta: float) -> None:
        """마우스 휠 델타를 기반으로 타겟과의 거리를 조절함."""
        self.distance -= delta * self.zoom_speed
        # 거리가 0 이하로 내려가 화면이 뒤집히는 현상 방지
        self.distance = max(0.1, self.distance)

    # ==========================================
    # OpenGL 파이프라인 상태 주입
    # ==========================================

    def Update_projection(self, width: int, height: int, unit_length: float = 1.0) -> None:
        """창 크기 변경 시 호출되어 Projection 행렬을 갱신함.

        Orbit_Camera는 K 모델이 아닌 fov 중심으로 조작되므로, fov_y로부터
        fx/fy를 역산하여 씬 카메라와 동일한 빌더 경로를 공유함.

        Args:
            unit_length: stage 1단위당 m. near/far(m) → stage 단위 환산에 사용됨.
        """
        if height == 0: height = 1  # 0으로 나누기 방지

        # fov(수직) → fy 역산. 정사각 픽셀 가정으로 fx = fy.
        _fy = (height * 0.5) / np.tan(np.radians(self.fov * 0.5))
        _fx = _fy
        _cx = width * 0.5
        _cy = height * 0.5

        _proj = Build_gl_projection(
            _fx, _fy, _cx, _cy, width, height,
            self.near_clip / unit_length, self.far_clip / unit_length
        )

        glMatrixMode(GL_PROJECTION)
        glLoadMatrixf(_proj)

    def Apply_view(self) -> None:
        """매 프레임 호출되어 ModelView 행렬에 카메라 위치를 세팅함."""
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # 극좌표계를 직교 좌표계(Cartesian)의 눈 위치(Eye Position)로 변환
        _yaw_rad = np.radians(self.yaw)
        _pitch_rad = np.radians(self.pitch)

        _eye_x = self.target[0] + self.distance * np.cos(_pitch_rad) * np.sin(_yaw_rad)
        _eye_y = self.target[1] + self.distance * np.sin(_pitch_rad)
        _eye_z = self.target[2] + self.distance * np.cos(_pitch_rad) * np.cos(_yaw_rad)

        gluLookAt(
            _eye_x, _eye_y, _eye_z,             # 카메라 위치
            self.target[0], self.target[1], self.target[2], # 바라보는 중심점
            0.0, 1.0, 0.0                       # Up 벡터 (월드 Y축)
        )