from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    glDisable, glEnable,
    GL_LIGHTING, GL_DITHER,
)

from data.node import Base_Node
from graphics.core.id_pass import Id_Pass_Driver
from graphics.core.pass_.base import Base_Pass
from graphics.core.pass_.registry import Pass_Registry


@Pass_Registry.Register_module("segmentation")
class Segmentation_Pass(Base_Pass):
    """RGB 인코딩된 인스턴스 ID 맵을 생성하는 패스 (uint8, HxWx3).

    Render() 호출 후 last_id_map에서 색상 키 → Scene_Node 매핑을 확인 가능함.
    배경: (0, 0, 0).
    """

    def __init__(self):
        super().__init__()
        self._driver = Id_Pass_Driver(self.res_manager)

    @property
    def Name(self) -> str:
        return "segmentation"

    @property
    def last_id_map(self) -> dict[tuple[int, int, int], Base_Node]:
        """드라이버 내부 매핑을 외부에 노출."""
        return self._driver.id_map

    def _On_setup(self) -> None:
        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)
        self._driver.Reset()

    def _On_draw(self, root_node: Base_Node) -> None:
        self._driver.Draw(root_node)

    def _On_readback(self, width: int, height: int, **kwargs) -> np.ndarray:
        return self._Read_rgb(width, height)

    def _On_cleanup(self) -> None:
        glEnable(GL_DITHER)
