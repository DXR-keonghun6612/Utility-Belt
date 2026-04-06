import numpy as np
from OpenGL.GL import (
    glGetDoublev, glGetIntegerv,
    GL_MODELVIEW_MATRIX, GL_PROJECTION_MATRIX, GL_VIEWPORT
)
from OpenGL.GLU import gluProject

class Transform_Math:
    """
    OpenGL 투영 상태를 활용하여 마우스 2D 델타를 3D 행렬 변화량(Delta Matrix)으로 변환하는 순수 수학 유틸리티.

    [주의] 
    이 모듈의 메서드를 호출하기 전에, OpenGL의 GL_MODELVIEW_MATRIX는 반드시 
    '카메라 뷰 행렬 * 객체의 월드 변환 행렬'이 적용된 상태여야 함.
    """

    @staticmethod
    def _Get_screen_direction(axis_local: np.ndarray) -> np.ndarray:
        """현재 뷰포트 상태에서 3D 로컬 축이 2D 화면에서 향하는 방향 벡터를 산출함."""
        _mv = glGetDoublev(GL_MODELVIEW_MATRIX)
        _proj = glGetDoublev(GL_PROJECTION_MATRIX)
        _vp = glGetIntegerv(GL_VIEWPORT)

        # 로컬 공간의 원점(0,0,0)과 지정된 축의 끝점을 현재 렌더링 파이프라인 기준으로 투영
        _p0 = np.array(gluProject(0.0, 0.0, 0.0, _mv, _proj, _vp)[:2])
        _p1 = np.array(gluProject(*axis_local, _mv, _proj, _vp)[:2])

        _screen_vec = _p1 - _p0
        _norm = np.linalg.norm(_screen_vec)

        # 0 나누기 방지
        return _screen_vec / _norm if _norm > 1e-6 else np.zeros(2, dtype=np.float32)

    @staticmethod
    def Get_translation_delta(
        axis_local: np.ndarray, 
        dx: float, dy: float, 
        sensitivity: float
    ) -> np.ndarray:
        """마우스 이동량을 기반으로 4x4 평행 이동 변화량 행렬을 생성함."""
        _screen_dir = Transform_Math._Get_screen_direction(axis_local)

        # 마우스 델타 벡터 (OpenGL은 화면 Y축이 아래에서 위로 증가하므로 -dy 적용)
        _mouse_vec = np.array([dx, -dy], dtype=np.float32)

        # 내적(Dot Product)을 통해 마우스가 3D 축 방향과 평행하게 움직인 스칼라량 산출
        _move_amount = np.dot(_mouse_vec, _screen_dir) * sensitivity

        # 4x4 단위 행렬의 평행이동 성분에 값 적용
        _delta_mat = np.eye(4, dtype=np.float32)
        _slice_xyz = slice(0, 3)
        _delta_mat[_slice_xyz, 3] = axis_local * _move_amount

        return _delta_mat

    @staticmethod
    def Get_rotation_delta(
        axis_key: str,
        axis_local: np.ndarray,
        dx: float, dy: float,
        screen_x: float, screen_y: float
    ) -> np.ndarray:
        """객체 중심 기준 각도 변위로 4x4 회전 변화량 행렬을 생성함.

        접선 내적 대신 atan2 기반 각도 산출을 사용하여,
        마우스 위치에 관계없이 CAD 스타일의 일관된 회전 방향을 보장함.

        Args:
            axis_key: 회전축 식별자 ('RX', 'RY', 'RZ').
            axis_local: 로컬 공간 회전축 단위 벡터.
            dx: 위젯 좌표계 마우스 X 변위 (px).
            dy: 위젯 좌표계 마우스 Y 변위 (px, 하향 양수).
            screen_x: 현재 마우스 X (OpenGL 스크린 좌표).
            screen_y: 현재 마우스 Y (OpenGL 스크린 좌표, 상향 양수).
        """
        _mv = glGetDoublev(GL_MODELVIEW_MATRIX)
        _proj = glGetDoublev(GL_PROJECTION_MATRIX)
        _vp = glGetIntegerv(GL_VIEWPORT)

        # 객체 원점의 스크린 좌표
        _center = np.array(gluProject(0.0, 0.0, 0.0, _mv, _proj, _vp)[:2])

        # 현재/이전 마우스 위치 (OpenGL Y축 기준 복원)
        _curr = np.array([screen_x, screen_y], dtype=np.float32)
        _prev = np.array([screen_x - dx, screen_y + dy], dtype=np.float32)

        # 중심 → 마우스 벡터 간 각도 산출 (바퀴 회전 원리)
        _v_curr = _curr - _center
        _v_prev = _prev - _center
        _cross = _v_prev[0] * _v_curr[1] - _v_prev[1] * _v_curr[0]
        _angle = np.arctan2(_cross, np.dot(_v_prev, _v_curr))

        # 회전축의 뷰 스페이스 Z 성분으로 방향 보정
        # Z > 0: 축이 카메라를 향함 → 스크린 회전 방향 유지
        # Z < 0: 축이 카메라 반대 → 부호 반전
        _axis_view_z = (_mv[0][2] * axis_local[0] +
                        _mv[1][2] * axis_local[1] +
                        _mv[2][2] * axis_local[2])
        if _axis_view_z < 0:
            _angle = -_angle

        _cos, _sin = np.cos(_angle), np.sin(_angle)
        _delta_mat = np.eye(4, dtype=np.float32)

        _slice_2x2 = slice(1, 3)
        _slice_xz = slice(0, 3, 2)
        _slice_xy = slice(0, 2)

        if 'X' in axis_key:
            _delta_mat[_slice_2x2, _slice_2x2] = [[_cos, -_sin], [_sin, _cos]]
        elif 'Y' in axis_key:
            _delta_mat[0, _slice_xz] = [_cos, _sin]
            _delta_mat[2, _slice_xz] = [-_sin, _cos]
        elif 'Z' in axis_key:
            _delta_mat[_slice_xy, _slice_xy] = [[_cos, -_sin], [_sin, _cos]]

        return _delta_mat

    @staticmethod
    def Apply_delta(local_matrix: np.ndarray, delta_matrix: np.ndarray) -> np.ndarray:
        """
        기존 로컬 행렬에 변화량 행렬을 적용(우측 곱셈)하여 반환함.
        수식: M_new = M_old @ M_delta (객체의 로컬 좌표계 기준 변환)
        """
        return local_matrix @ delta_matrix