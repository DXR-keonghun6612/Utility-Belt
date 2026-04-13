"""인스턴스 ID를 RGB로 인코딩한 메시 드로우 + 컬러키 → 노드 매핑 드라이버.

viewport 픽킹과 Segmentation_Pass가 동일 인코딩/매핑 로직을 공유함.
"""
from __future__ import annotations

from OpenGL.GL import glColor3ub

from data.node import Base_Node
from data.node.type.mesh import Mesh_Node
from graphics.core.draw import Draw_mesh
from graphics.core.resource import GPU_Resource_Manager
from graphics.core.traversal_gl import Walk_gl


def Encode_id(idx: int) -> tuple[int, int, int]:
    """24비트 정수 인덱스를 RGB 색상 키로 인코딩함."""
    return (idx & 0xFF, (idx >> 8) & 0xFF, (idx >> 16) & 0xFF)


class Id_Pass_Driver:
    """ID 패스 1회 실행 단위. Reset → Draw 후 id_map에서 컬러키→노드를 조회함."""

    def __init__(self, res_manager: GPU_Resource_Manager):
        self.res_manager = res_manager
        self.id_map: dict[tuple[int, int, int], Base_Node] = {}
        self._counter: int = 1

    def Reset(self) -> None:
        """카운터와 매핑을 초기화함."""
        self.id_map = {}
        self._counter = 1

    def Draw(self, root: Base_Node) -> None:
        """씬 트리를 ID 인코딩 모드로 렌더링하면서 매핑을 누적함."""
        Walk_gl(root, self._On_node)

    def _On_node(self, node: Base_Node) -> None:
        if not (isinstance(node, Mesh_Node) and node.mesh is not None):
            return

        _color = Encode_id(self._counter)
        self.id_map[_color] = node
        glColor3ub(*_color)
        Draw_mesh(node.mesh, self.res_manager)
        self._counter += 1
