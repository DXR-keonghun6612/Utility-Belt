from __future__ import annotations
from dataclasses import dataclass

from data.node.type.base import Base_Node
from data.register import NODE_REGISTRY


@NODE_REGISTRY.Register_module("Xform")
@dataclass
class Group_Node(Base_Node):
    """Xform/Stage 계열의 구조적 그룹 노드임. 자식 노드 컨테이너 역할을 수행함."""
    pass
