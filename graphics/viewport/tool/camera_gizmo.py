"""카메라 노드의 위치/방향/화각을 와이어프레임으로 시각화하는 기즈모 모듈."""
import numpy as np
from OpenGL.GL import *

_CAM_BODY_SIZE = 0.3
_CAM_FRUSTUM_DEPTH = 1.5


def Draw_camera_gizmo(
    fov: float = 60.0,
    img_w: int = 1920,
    img_h: int = 1080,
    is_selected: bool = False
) -> None:
    """카메라 프러스텀 및 바디를 와이어프레임으로 렌더링함.

    로컬 좌표계 원점에 그려지므로, 호출 전 glMultMatrixf로 노드 변환이 적용되어 있어야 함.
    카메라는 -Z 방향을 바라보는 OpenGL 관례를 따름.

    Args:
        fov: 수직 화각 (degrees).
        img_w: 이미지 가로 해상도 (px) -- 종횡비 산출용.
        img_h: 이미지 세로 해상도 (px).
        is_selected: 선택 상태 시 하이라이트 색상 적용.
    """
    glDisable(GL_LIGHTING)

    if is_selected:
        glColor3f(1.0, 0.8, 0.2)
        glLineWidth(2.0)
    else:
        glColor3f(0.3, 0.7, 1.0)
        glLineWidth(1.5)

    # 프러스텀 꼭짓점 계산 (-Z 방향)
    _aspect = img_w / img_h if img_h > 0 else 16 / 9
    _half_h = _CAM_FRUSTUM_DEPTH * np.tan(np.radians(fov * 0.5))
    _half_w = _half_h * _aspect

    _fz = -_CAM_FRUSTUM_DEPTH
    _ftl = (-_half_w, _half_h, _fz)
    _ftr = (_half_w, _half_h, _fz)
    _fbl = (-_half_w, -_half_h, _fz)
    _fbr = (_half_w, -_half_h, _fz)

    # 카메라 바디 (작은 직육면체)
    _bs = _CAM_BODY_SIZE * 0.5
    _bd = _CAM_BODY_SIZE * 0.3
    _body = [
        (-_bs, _bs, _bd), (_bs, _bs, _bd),
        (_bs, -_bs, _bd), (-_bs, -_bs, _bd),
        (-_bs, _bs, -_bd), (_bs, _bs, -_bd),
        (_bs, -_bs, -_bd), (-_bs, -_bs, -_bd),
    ]

    # 바디 전면
    glBegin(GL_LINE_LOOP)
    for i in range(4):
        glVertex3f(*_body[i])
    glEnd()

    # 바디 후면
    glBegin(GL_LINE_LOOP)
    for i in range(4, 8):
        glVertex3f(*_body[i])
    glEnd()

    # 바디 연결선
    glBegin(GL_LINES)
    for i in range(4):
        glVertex3f(*_body[i])
        glVertex3f(*_body[i + 4])
    glEnd()

    # 프러스텀 라인 (원점 -> 원거리면 꼭짓점)
    glBegin(GL_LINES)
    for _corner in [_ftl, _ftr, _fbl, _fbr]:
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(*_corner)
    glEnd()

    # 원거리면 사각형
    glBegin(GL_LINE_LOOP)
    glVertex3f(*_ftl)
    glVertex3f(*_ftr)
    glVertex3f(*_fbr)
    glVertex3f(*_fbl)
    glEnd()

    # Up 방향 표시 (프러스텀 상단 삼각형)
    _mid_top_x = (_ftl[0] + _ftr[0]) * 0.5
    _mid_top_y = _ftl[1]
    _tip_y = _mid_top_y + _half_h * 0.3

    glBegin(GL_LINE_LOOP)
    glVertex3f(_ftl[0], _mid_top_y, _fz)
    glVertex3f(_mid_top_x, _tip_y, _fz)
    glVertex3f(_ftr[0], _mid_top_y, _fz)
    glEnd()

    glLineWidth(1.0)
    glEnable(GL_LIGHTING)
