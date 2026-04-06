from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, ClassVar

from data.scene.node.base import Scene_Node


@dataclass
class Mesh_Node(Scene_Node):
    """Trimesh 지오메트리 데이터를 보유하는 메시 노드임."""

    # Trimesh 지오메트리 데이터 (얕은 복사로 인스턴싱 공유)
    mesh: Any | None = field(default=None, repr=False)

    __exclude_serialize__: ClassVar[set[str]] = {"mesh"}

    def Clone(self, label_name: str | None = None) -> Mesh_Node:
        """메시 데이터는 얕은 복사(Instancing)로 메모리를 공유함.

        Args:
            label_name (str | None): 복제될 노드의 새로운 식별자.

        Returns:
            Mesh_Node: 복제된 메시 노드.
        """
        _new_node = Mesh_Node(
            label=self.label if label_name is None else label_name,
            prim_type=self.prim_type,
            local_matrix=self.local_matrix.copy(),
            source_path=self.source_path,
            mesh=self.mesh,
        )

        for _child in self.children:
            _cloned_child = _child.Clone()
            _cloned_child.Set_parent(_new_node)
            _new_node.children.append(_cloned_child)

        return _new_node
