from __future__ import annotations

import numpy as np
from OpenGL.GL import glDisable, GL_LIGHTING

from data.node.type.camera import Camera_Node
from graphics.core.pass_.base import Base_Pass
from graphics.core.pass_.registry import Pass_Registry


@Pass_Registry.Register_module("depth")
class Depth_Pass(Base_Pass):
    """선형 미터 단위 뎁스 맵을 생성하는 패스 (float32, shape: HxW).

    배경 픽셀은 0.0으로 마스킹됨.
    """

    @property
    def Name(self) -> str:
        return "depth"

    def _On_setup(self) -> None:
        glDisable(GL_LIGHTING)

    def _On_readback(self, width: int, height: int, **kwargs) -> np.ndarray:
        _raw = self._Read_depth(width, height)

        # NDC → 선형 미터 단위 변환
        _cam: Camera_Node = kwargs["camera_node"]
        _near = _cam.intrinsic.near_clip
        _far = _cam.intrinsic.far_clip
        _linear = (2.0 * _near * _far) / (_far + _near - _raw * (_far - _near))

        # 배경(뎁스 1.0) 마스킹
        _linear[_raw >= 1.0] = 0.0
        return _linear
