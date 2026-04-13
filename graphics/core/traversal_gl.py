"""GL 행렬 스택과 결합된 씬 트리 순회 헬퍼.

is_renderable 체크, glPushMatrix/glMultMatrixf/glPopMatrix, 자식 재귀를 단일
구조로 캡슐화함. 호출자는 노드 단위 콜백만 제공함.
"""
from __future__ import annotations

from typing import Callable

from OpenGL.GL import glPushMatrix, glPopMatrix, glMultMatrixf

from data.node import Base_Node


def Walk_gl(
    node: Base_Node, on_node: Callable[[Base_Node], None]
) -> None:
    """현재 노드의 local_matrix를 스택에 푸시한 상태에서 콜백을 실행하고 자식을 재귀 순회함.

    Args:
        node: 순회 시작 노드.
        on_node: glMultMatrixf 적용 후 매 노드마다 1회 실행되는 콜백.
                 노드 타입 분기, 메시 드로우, 기즈모 표시 등 호출자 책임 처리를 수행함.
    """
    if not node.is_renderable:
        return

    glPushMatrix()
    glMultMatrixf(node.local_matrix.T)

    on_node(node)

    for _child in node.children:
        Walk_gl(_child, on_node)

    glPopMatrix()
