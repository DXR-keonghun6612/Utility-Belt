from OpenGL.GL import *
from spatial_toolbox.scene.node import Camera_Intrinsic


class Camera_Frustum:
    """Camera 노드의 위치/방향/화각을 와이어프레임으로 시각화하는 뷰포트 노드.

    씬 트리에 속하지 않는 독립 뷰포트 노드로, Camera 노드 순회 시 렌더러가
    노드당 1회 Draw()를 호출함. 호출 전 glMultMatrixf로 노드 변환이 적용되어 있어야 함.
    """

    BODY_SIZE: float = 0.3
    FRUSTUM_DEPTH: float = 1.5
    DEFAULT_W: int = 1920
    DEFAULT_H: int = 1080
    DEFAULT_F: float = 1000.0

    def Draw(self, intrinsic: Camera_Intrinsic | None = None, is_selected: bool = False) -> None:
        """카메라 바디(직육면체) + 프러스텀 + Up 인디케이터를 렌더링함."""
        glDisable(GL_LIGHTING)

        if is_selected:
            glColor3f(1.0, 0.8, 0.2)
            glLineWidth(2.0)
        else:
            glColor3f(0.3, 0.7, 1.0)
            glLineWidth(1.5)

        if intrinsic is not None:
            _W, _H = intrinsic.width, intrinsic.height
            _fx, _fy = intrinsic.fx, intrinsic.fy
        else:
            _W, _H = self.DEFAULT_W, self.DEFAULT_H
            _fx = _fy = self.DEFAULT_F

        _fz = -self.FRUSTUM_DEPTH
        _half_h = self.FRUSTUM_DEPTH * (_H * 0.5) / _fy
        _half_w = self.FRUSTUM_DEPTH * (_W * 0.5) / _fx
        _ftl = (-_half_w,  _half_h, _fz)
        _ftr = ( _half_w,  _half_h, _fz)
        _fbl = (-_half_w, -_half_h, _fz)
        _fbr = ( _half_w, -_half_h, _fz)

        _bs = self.BODY_SIZE * 0.5
        _bd = self.BODY_SIZE * 0.3
        _body = [
            (-_bs,  _bs,  _bd), ( _bs,  _bs,  _bd),
            ( _bs, -_bs,  _bd), (-_bs, -_bs,  _bd),
            (-_bs,  _bs, -_bd), ( _bs,  _bs, -_bd),
            ( _bs, -_bs, -_bd), (-_bs, -_bs, -_bd),
        ]

        glBegin(GL_LINE_LOOP)
        for i in range(4): glVertex3f(*_body[i])
        glEnd()

        glBegin(GL_LINE_LOOP)
        for i in range(4, 8): glVertex3f(*_body[i])
        glEnd()

        glBegin(GL_LINES)
        for i in range(4):
            glVertex3f(*_body[i])
            glVertex3f(*_body[i + 4])
        glEnd()

        glBegin(GL_LINES)
        for _corner in (_ftl, _ftr, _fbl, _fbr):
            glVertex3f(0.0, 0.0, 0.0)
            glVertex3f(*_corner)
        glEnd()

        glBegin(GL_LINE_LOOP)
        glVertex3f(*_ftl); glVertex3f(*_ftr)
        glVertex3f(*_fbr); glVertex3f(*_fbl)
        glEnd()

        # Up 인디케이터 (상단 삼각형)
        _mid_x = (_ftl[0] + _ftr[0]) * 0.5
        glBegin(GL_LINE_LOOP)
        glVertex3f(_ftl[0], _ftl[1], _fz)
        glVertex3f(_mid_x,  _ftl[1] + _half_h * 0.3, _fz)
        glVertex3f(_ftr[0], _ftr[1], _fz)
        glEnd()

        glLineWidth(1.0)
        glEnable(GL_LIGHTING)
