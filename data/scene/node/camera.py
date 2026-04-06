from __future__ import annotations
from dataclasses import dataclass, field

from python_toolbox.project import Base_Config
from data.scene.node.base import Scene_Node


@dataclass
class Camera_Intrinsic(Base_Config):
    """물리 카메라 모델의 광학 파라미터 정의."""

    width: int = 1920          # 출력 해상도 (px)
    height: int = 1080
    fov: float = 60.0          # 수직 화각 (degrees)
    near_clip: float = 0.1
    far_clip: float = 1000.0
    focal_length: float = 50.0 # mm 단위 (메타데이터 용도)
    sensor_width: float = 36.0 # mm 단위 (메타데이터 용도)
    sensor_height: float = 24.0


@dataclass
class Camera_Node(Scene_Node):
    """카메라 내부 파라미터(Intrinsic)를 보유하는 카메라 노드임."""

    intrinsic: Camera_Intrinsic | None = field(default=None, repr=False)

    def Clone(self, label_name: str | None = None) -> Camera_Node:
        """카메라 고유 파라미터를 포함하여 복제함.

        Args:
            label_name (str | None): 복제될 노드의 새로운 식별자.

        Returns:
            Camera_Node: 복제된 카메라 노드.
        """
        _new_node = Camera_Node(
            label=self.label if label_name is None else label_name,
            prim_type=self.prim_type,
            local_matrix=self.local_matrix.copy(),
            source_path=self.source_path,
            visible=self.visible,
            intrinsic=self.intrinsic,
        )

        for _child in self.children:
            _cloned_child = _child.Clone()
            _cloned_child.Set_parent(_new_node)
            _new_node.children.append(_cloned_child)

        return _new_node
