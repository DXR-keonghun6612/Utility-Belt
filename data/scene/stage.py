from pathlib import Path
from data.scene.node import Scene_Node, Group_Node


from data.scene.scene_file import save_scene, load_scene

class Stage_Controller:
    """씬 그래프의 양방향 트리 구조를 관리하고 상태 무결성을 제어함."""

    def __init__(self):
        """World Stage 루트 노드 초기화. 부모가 없는 절대 기점임."""
        self.root = Scene_Node(label="World_Stage", prim_type="Stage")

    def Add_node(
        self, node: Scene_Node | None = None, parent: Scene_Node | None = None
    ) -> None:
        """씬 트리에 노드를 삽입하고 양방향 참조를 동기화함.
        
        Args:
            node (Scene_Node | None): 추가할 대상 노드. None일 경우 빈 그룹 생성.
            parent (Scene_Node | None): 삽입될 타겟 부모. None일 경우 루트로 지정.
        """
        _target = parent if parent else self.root

        # 1. 빈 그룹 생성 분기
        if node is None:
            _new_group = Group_Node(label="new_group", prim_type="Xform")
            _new_group.Set_parent(_target)
            _target.children.append(_new_group)
            return

        # 2. 컨테이너 노드 언패킹 분기
        if node.prim_type in ["Xform", "Stage"]:
            # 언패킹 시 원본 자식들을 복제하여 참조 독립성 확보
            for _child in node.children:
                _cloned_child = _child.Clone()
                self.Add_node(_cloned_child, _target)
        # 3. 단일 프림 삽입 분기
        else:
            _new_node = node.Clone()
            _new_node.Set_parent(_target)
            _target.children.append(_new_node)

    def Move_node(
        self, node: Scene_Node, old_parent: Scene_Node, new_parent: Scene_Node
    ) -> bool:
        """트리 내부에서 노드의 소유권을 이전함 (Internal Re-parenting).
        
        Args:
            node (Scene_Node): 이동할 대상 노드.
            old_parent (Scene_Node): 현재 부모 노드.
            new_parent (Scene_Node): 새롭게 편입될 부모 노드.
            
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
        self, node: Scene_Node, parent: Scene_Node
    ) -> Scene_Node | None:
        """부모로부터 노드를 안전하게 분리하고 역참조를 초기화함.
        
        Args:
            node (Scene_Node): 분리할 노드.
            parent (Scene_Node): 대상 노드의 현재 부모.
            
        Returns:
            Scene_Node | None: 분리된 노드 객체. 실패 시 None.
        """
        try:
            parent.children.remove(node)
            # 순환 참조 단절
            node.Set_parent(None)
            return node
        except (ValueError, AttributeError):
            return None

    def Save(self, file_path: Path) -> None:
        """현재 장면 트리를 JSON 파일로 저장함.

        Args:
            file_path: 저장 대상 JSON 파일 경로.
        """
        save_scene(self.root, file_path)

    def Load(self, file_path: Path) -> None:
        """JSON 파일에서 장면 트리를 복원하여 현재 씬을 교체함.

        Args:
            file_path: 로드할 JSON 파일 경로.
        """
        _loaded_root = load_scene(file_path)

        self.clear_scene()
        for _child in list(_loaded_root.children):
            _child.Set_parent(self.root)
            self.root.children.append(_child)

    def clear_scene(self) -> None:
        """씬의 모든 객체를 메모리에서 해제함."""
        # GC 최적화를 위한 자식 노드들의 부모 참조 선제적 해제
        for _child in self.root.children:
            _child.Set_parent(None)
            
        self.root.children.clear()
