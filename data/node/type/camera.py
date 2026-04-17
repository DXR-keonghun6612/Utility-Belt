from __future__ import annotations
from dataclasses import dataclass, field, InitVar
from typing import ClassVar

import numpy as np

from python_toolbox.project import Base_Config

from data.node.type.base import Base_Node, PrimType
from data.register import NODE_REGISTRY


def Build_gl_projection(
    fx: float, fy: float, cx: float, cy: float,
    width: int, height: int, near: float, far: float
) -> np.ndarray:
    """OpenCV K 파라미터로부터 OpenGL projection 행렬을 산출함.

    OpenGL 관례: 카메라 시선 -Z, NDC y-up. glLoadMatrixf 직접 전달 가능한
    column-major 레이아웃으로 반환함.

    Args:
        fx, fy: 초점 거리 (픽셀 단위).
        cx, cy: 주점 (픽셀 좌표).
        width, height: 이미지 해상도 (px).
        near, far: 렌더 클리핑 평면.

    Returns:
        np.ndarray: 4x4 float32 column-major 투영 행렬.
    """
    _M = np.zeros((4, 4), dtype=np.float32)
    _M[0, 0] = 2.0 * fx / width
    _M[1, 1] = 2.0 * fy / height
    _M[0, 2] = 1.0 - 2.0 * cx / width
    _M[1, 2] = 2.0 * cy / height - 1.0
    _M[2, 2] = -(far + near) / (far - near)
    _M[2, 3] = -2.0 * far * near / (far - near)
    _M[3, 2] = -1.0
    return _M.T


@dataclass
class Camera_Intrinsic(Base_Config):
    """OpenCV/ROS K 모델 기반 카메라 내부 파라미터.

    K = [[fx, 0, cx], [0, fy, cy], [0, 0, 1]] 를 (fx, fy, cx, cy)로 압축 저장함.
    distortion은 OpenCV 규격 8슬롯(k1,k2,p1,p2,k3,k4,k5,k6) 메타로만 보관되며,
    현재 고정 파이프라인은 이를 반영하지 않음 (ROADMAP의 셰이더 적용 과제 참조).
    """

    width: int = 1920
    height: int = 1080
    # Intrinsic K (focal length + principal point, pixel units)
    fx: float = 1000.0
    fy: float = 1000.0
    cx: float = 960.0
    cy: float = 540.0
    # OpenCV 왜곡 계수 8슬롯: k1,k2,p1,p2,k3,k4,k5,k6 — 메타 보관용
    distortion: list = field(
        default_factory=lambda: [0.0] * 8
    )
    near_clip: float = 0.1
    far_clip: float = 1000.0

    @property
    def fov_x(self) -> float:
        """K로부터 산출되는 수평 화각 (degrees)."""
        return float(np.degrees(2.0 * np.arctan((self.width * 0.5) / self.fx)))

    @property
    def fov_y(self) -> float:
        """K로부터 산출되는 수직 화각 (degrees)."""
        return float(np.degrees(2.0 * np.arctan((self.height * 0.5) / self.fy)))

    def Build_gl_projection(self) -> np.ndarray:
        """K와 near/far로부터 OpenGL column-major projection 행렬을 산출함."""
        return Build_gl_projection(
            self.fx, self.fy, self.cx, self.cy,
            self.width, self.height, self.near_clip, self.far_clip
        )


@NODE_REGISTRY.Register_module("Camera")
@dataclass
class Camera_Node(Base_Node):
    """카메라 내부 파라미터(Intrinsic)를 보유하는 카메라 노드임."""

    prim_type: PrimType = "Camera"
    intrinsic: Camera_Intrinsic | None = field(default=None, repr=False)
    intrinsic_meta: InitVar[dict | None] = None

    # intrinsic → intrinsic_meta 키로 직렬화 (역직렬화 시 InitVar로 수신)
    __custom_keys__: ClassVar[dict[str, str]] = {"intrinsic": "intrinsic_meta"}

    def __post_init__(
        self, local_matrix_meta: list | None, intrinsic_meta: dict | None
    ):
        super().__post_init__(local_matrix_meta)
        """intrinsic_meta dict → Camera_Intrinsic 객체 복원."""
        self.intrinsic = Camera_Intrinsic(**(intrinsic_meta or {}))

    def Clone(self, label_name: str | None = None) -> Camera_Node:
        """카메라 고유 파라미터를 포함하여 복제함.

        Args:
            label_name: 복제될 노드의 새로운 식별자.

        Returns:
            Camera_Node: 복제된 카메라 노드.
        """
        _new_node = Camera_Node(
            label=self.label if label_name is None else label_name,
            prim_type=self.prim_type,
            local_matrix=self.local_matrix.copy(),
            source_key=self.source_key,
            visible=self.visible,
            intrinsic=self.intrinsic,
        )

        for _child in self.children:
            _cloned_child = _child.Clone()
            _cloned_child.Set_parent(_new_node)
            _new_node.children.append(_cloned_child)

        return _new_node
