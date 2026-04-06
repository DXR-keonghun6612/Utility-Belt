from __future__ import annotations
from dataclasses import dataclass

from data.scene.node.base import Scene_Node


@dataclass
class Group_Node(Scene_Node):
    """Xform/Stage 계열의 구조적 그룹 노드임. 자식 노드 컨테이너 역할을 수행함."""
    pass
