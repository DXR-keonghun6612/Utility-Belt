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
        _delta_mat[0:3, 3] = axis_local * _move_amount
        
        return _delta_mat

    @staticmethod
    def Get_rotation_delta(
        axis_key: str,
        axis_local: np.ndarray, 
        dx: float, dy: float, 
        sensitivity: float
    ) -> np.ndarray:
        """마우스 이동량을 기반으로 4x4 회전 변화량 행렬을 생성함."""
        _screen_dir = Transform_Math._Get_screen_direction(axis_local)
        
        # 기즈모 호(Arc)를 드래그할 때는 축 방향이 아니라 축의 접선(Tangent) 방향으로 움직임
        # 방향 벡터를 90도 회전시켜 접선 벡터 산출
        _tangent = np.array([-_screen_dir[1], _screen_dir[0]], dtype=np.float32)
        _mouse_vec = np.array([dx, -dy], dtype=np.float32)
        
        # 축에 따른 회전 부호 보정 (X축 회전 시 시각적 드래그 방향 일치를 위함)
        _sign = -1.0 if 'X' in axis_key else 1.0
        _angle = np.dot(_mouse_vec, _tangent) * sensitivity * _sign
        
        _cos, _sin = np.cos(_angle), np.sin(_angle)
        _delta_mat = np.eye(4, dtype=np.float32)
        
        if 'X' in axis_key:
            _delta_mat[1:3, 1:3] = [[_cos, -_sin], [_sin, _cos]]
        elif 'Y' in axis_key:
            _delta_mat[0, 0], _delta_mat[0, 2] = _cos, _sin
            _delta_mat[2, 0], _delta_mat[2, 2] = -_sin, _cos
        elif 'Z' in axis_key:
            _delta_mat[0:2, 0:2] = [[_cos, -_sin], [_sin, _cos]]
            
        return _delta_mat

    @staticmethod
    def Apply_delta(local_matrix: np.ndarray, delta_matrix: np.ndarray) -> np.ndarray:
        """
        기존 로컬 행렬에 변화량 행렬을 적용(우측 곱셈)하여 반환함.
        수식: M_new = M_old @ M_delta (객체의 로컬 좌표계 기준 변환)
        """
        return local_matrix @ delta_matrix