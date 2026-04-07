from __future__ import annotations
from dataclasses import dataclass, field, InitVar
from typing import ClassVar

from python_toolbox.project import Base_Config

from data.node.type.base import Base_Node, PrimType
from data.register import NODE_REGISTRY


@dataclass
class Camera_Intrinsic(Base_Config):
    """물리 카메라 모델의 광학 파라미터 정의."""

    width: int = 1920          # 출력 해상도 (px)
    height: int = 1080
    fov: float = 60.0          # 수직 화각 (degrees)
    near_clip: float = 0.1
    far_clip: float = 1000.0


@NODE_REGISTRY.Register_module("Camera")
@dataclass
class Camera_Node(Base_Node):
    """카메라 내부 파라미터(Intrinsic)를 보유하는 카메라 노드임."""

    prim_type: PrimType = "Camera"
    intrinsic: Camera_Intrinsic | None = field(default=None, repr=False)
    intrinsic_meta: InitVar[dict | None] = None

    # intrinsic → intrinsic_meta 키로 직렬화 (역직렬화 시 InitVar로 수신)
    __custom_keys__: ClassVar[dict[str, str]] = {"intrinsic": "intrinsic_meta"}

    def __post_init__(self, intrinsic_meta: dict | None):
        """intrinsic_meta dict → Camera_Intrinsic 객체 복원."""
        _kwarg = intrinsic_meta if intrinsic_meta is not None else {}

        self.intrinsic = Camera_Intrinsic(**_kwarg) 

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
