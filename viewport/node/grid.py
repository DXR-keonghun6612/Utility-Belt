from dataclasses import dataclass
from OpenGL.GL import *
from python_toolbox import Data_Schema


@dataclass
class Viewer_Config(Data_Schema):
    grid_spacing: float = 1.0
    grid_range: int = 10
    grid_line_width: float = 1.0


class Ground_Grid:
    """Y=0 기준 평면 그리드를 렌더링하는 뷰포트 노드.

    씬 트리에 속하지 않는 독립 뷰포트 노드로, Viewer_Config를 직접 소유하며
    렌더러가 매 프레임 Draw()를 호출함.
    """

    def __init__(self) -> None:
        self.config = Viewer_Config()

    def Draw(self) -> None:
        _s = self.config.grid_spacing
        _r = self.config.grid_range
        _edge = _s * _r

        glDisable(GL_LIGHTING)
        glColor3f(0.3, 0.3, 0.3)
        glLineWidth(self.config.grid_line_width)

        glBegin(GL_LINES)
        for i in range(-_r, _r + 1):
            _p = i * _s
            glVertex3f(_p,    0.0, -_edge)
            glVertex3f(_p,    0.0,  _edge)
            glVertex3f(-_edge, 0.0, _p)
            glVertex3f( _edge, 0.0, _p)
        glEnd()

        glEnable(GL_LIGHTING)
