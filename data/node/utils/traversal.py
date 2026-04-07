"""노드 트리 순회 유틸리티."""
from __future__ import annotations

from typing import Callable, Iterator

from data.node.type.base import Base_Node


def walk_nodes(
    root: Base_Node,
    predicate: Callable[[Base_Node], bool]
) -> Iterator[Base_Node]:
    """조건을 만족하는 노드를 재귀적으로 순회하여 반환하는 제너레이터.

    Args:
        root: 탐색을 시작할 씬 루트 노드.
        predicate: 노드 필터링용 콜백 함수.

    Yields:
        Base_Node: 필터링 조건을 만족하는 노드.
    """
    if predicate(root):
        yield root
    for _child in root.children:
        yield from walk_nodes(_child, predicate)
