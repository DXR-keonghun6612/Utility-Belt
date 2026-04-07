"""씬 그래프의 트리 구조 관리, 직렬화/역직렬화를 담당하는 모듈."""
from __future__ import annotations
from pathlib import Path

import numpy as np

from python_toolbox.file import Utils as File_Utils

from data.node.type import Base_Node, Group_Node
from data.register import NODE_REGISTRY


class Stage_Controller:
    """씬 그래프의 양방향 트리 구조 관리 및 파일 I/O를 제어함."""

    def __init__(self):
        """World Stage 루트 노드 초기화. 부모가 없는 절대 기점임."""
        self.root = Base_Node(label="World_Stage", prim_type="Stage")

    # ==========================================
    # 트리 조작
    # ==========================================

    def Add_node(
        self, node: Base_Node | None = None, parent: Base_Node | None = None
    ) -> None:
        """씬 트리에 노드를 삽입하고 양방향 참조를 동기화함.

        Args:
            node: 추가할 대상 노드. None일 경우 빈 그룹 생성.
            parent: 삽입될 타겟 부모. None일 경우 루트로 지정.
        """
        _target = parent if parent else self.root

        if node is None:
            _new_group = Group_Node(label="new_group", prim_type="Xform")
            _new_group.Set_parent(_target)
            _target.children.append(_new_group)
            return

        if node.prim_type in ["Xform", "Stage"]:
            for _child in node.children:
                _cloned_child = _child.Clone()
                self.Add_node(_cloned_child, _target)
        else:
            _new_node = node.Clone()
            _new_node.Set_parent(_target)
            _target.children.append(_new_node)

    def Move_node(
        self, node: Base_Node, old_parent: Base_Node, new_parent: Base_Node
    ) -> bool:
        """트리 내부에서 노드의 소유권을 이전함.

        Args:
            node: 이동할 대상 노드.
            old_parent: 현재 부모 노드.
            new_parent: 새롭게 편입될 부모 노드.

        Returns:
            bool: 이동 성공 여부.
        """
        _moved_node = self.Pop_node(node, old_parent)

        if _moved_node:
            _moved_node.Set_parent(new_parent)
            new_parent.children.append(_moved_node)
            return True

        return False

    def Pop_node(
        self, node: Base_Node, parent: Base_Node
    ) -> Base_Node | None:
        """부모로부터 노드를 안전하게 분리하고 역참조를 초기화함.

        Args:
            node: 분리할 노드.
            parent: 대상 노드의 현재 부모.

        Returns:
            Base_Node | None: 분리된 노드 객체. 실패 시 None.
        """
        try:
            parent.children.remove(node)
            node.Set_parent(None)
            return node
        except (ValueError, AttributeError):
            return None

    def Clear(self) -> None:
        """씬의 모든 객체를 메모리에서 해제함."""
        for _child in self.root.children:
            _child.Set_parent(None)
        self.root.children.clear()

    # ==========================================
    # 파일 I/O
    # ==========================================

    def Save(self, file_path: Path) -> None:
        """현재 장면 트리를 JSON 파일로 저장함.

        Args:
            file_path: 저장 대상 JSON 파일 경로.
        """
        File_Utils.Write_to(file_path, self.root.Serialize())

    def Load(self, file_path: Path) -> None:
        """JSON 파일에서 장면 트리를 복원하여 현재 씬을 교체함.

        Args:
            file_path: 로드할 JSON 파일 경로.

        Raises:
            ValueError: 파일 읽기 또는 파싱 실패 시.
        """
        _is_ok, _data = File_Utils.Read_from(file_path)
        if not _is_ok or not isinstance(_data, dict):
            raise ValueError(f"장면 파일 읽기 실패: {file_path}")

        _loaded_root = self._Build_node(_data, parent=None)

        self.Clear()
        for _child in list(_loaded_root.children):
            _child.Set_parent(self.root)
            self.root.children.append(_child)

    # ==========================================
    # 내부 구현
    # ==========================================

    def _Build_node(
        self, data: dict, parent: Base_Node | None
    ) -> Base_Node:
        """NODE_REGISTRY 기반으로 prim_type에 맞는 노드를 재귀 복원함."""
        _args = dict(data)
        _prim_type = _args.pop("prim_type", "Xform")
        _children_data = _args.pop("children", [])

        try:
            _node_cls = NODE_REGISTRY.Get(_prim_type)
        except KeyError:
            _node_cls = Base_Node

        _args["prim_type"] = _prim_type
        _args["parent"] = parent

        if "local_matrix" in _args and _args["local_matrix"] is not None:
            _args["local_matrix"] = np.array(
                _args["local_matrix"], dtype=np.float32
            ).reshape(4, 4)

        _node = _node_cls(**_args)

        for _child_data in _children_data:
            _child = self._Build_node(_child_data, parent=_node)
            _node.children.append(_child)

        return _node
