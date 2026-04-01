from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QMenu)
from PySide6.QtCore import Signal, Qt, QPoint
from PySide6.QtGui import QAction, QDropEvent

from data.scene.stage import Stage_Controller
from data.scene.node import Scene_Node


class Scene_Tree_Widget(QTreeWidget):
    """씬의 계층 구조 데이터를 시각화하고 다중 선택 및 Batch 상호작용을 처리하는 트리 컴포넌트."""
    
    # 이제 단일 노드가 아닌 선택된 노드들의 '리스트'를 방출함
    selection_changed = Signal(list)

    def __init__(self, stage: Stage_Controller, parent=None):
        super().__init__(parent)
        self.stage = stage
        self._Setup_ui()
        self.Refresh_ui()

    def _Setup_ui(self):
        self.setHeaderLabel("Hierarchy")
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        # [핵심 1] 다중 선택 모드 활성화 (Ctrl, Shift 클릭 지원)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        self.customContextMenuRequested.connect(self._Show_context_menu)
        
        # [핵심 2] itemClicked 대신 선택 범위 변경 이벤트를 구독
        self.itemSelectionChanged.connect(self._On_selection_changed)

    # ==========================================
    # 헬퍼 및 데이터 추출
    # ==========================================

    def _Get_node(self, item: QTreeWidgetItem | None) -> Scene_Node | None:
        """아이템에서 Scene_Node 데이터를 안전하게 추출함."""
        if not item: 
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def Get_selected_nodes(self) -> list[Scene_Node]:
        """현재 선택된 모든 유효한 노드를 리스트로 반환함."""
        _nodes = []
        for _item in self.selectedItems():
            _node = self._Get_node(_item)
            if _node:
                _nodes.append(_node)
        return _nodes

    def Refresh_ui(self):
        self.clear()
        if self.stage and self.stage.root:
            _root_item = self._Refresh_tree(self.stage.root)
            self.addTopLevelItem(_root_item)
            self.expandAll()

    def _Refresh_tree(self, node: Scene_Node) -> QTreeWidgetItem:
        _item = QTreeWidgetItem([f"[{node.prim_type}] {node.label}"])
        _item.setData(0, Qt.ItemDataRole.UserRole, node)
        
        for _child in node.children:
            _item.addChild(self._Refresh_tree(_child))
        return _item

    # ==========================================
    # 다중 선택 상호작용 (Batch Processing)
    # ==========================================

    def dropEvent(self, event: QDropEvent):
        """다중 드래그 앤 드롭 시 일괄 처리 후 1회 갱신함."""
        _dragged_items = self.selectedItems()
        _target_item = self.itemAt(event.position().toPoint())
        
        # 타겟이 빈 공간이면 루트로 간주, 아니면 타겟 아이템의 노드
        _new_parent = self._Get_node(_target_item) or self.stage.root
        
        if not _dragged_items or not _new_parent:
            event.ignore()
            return

        _is_changed = False

        # 일괄 이동 트랜잭션
        for _item in _dragged_items:
            _node = self._Get_node(_item)
            _old_parent = self._Get_node(_item.parent())

            # 루트 이동 방어 및 자기 자신(또는 자식)으로의 논리적 오류 방어
            if not _old_parent or not _node or _node == _new_parent:
                continue

            # 스테이지 컨트롤러가 허용하는 경우에만 플래그 업데이트
            if self.stage.Move_node(_node, _old_parent, _new_parent):
                _is_changed = True

        if _is_changed:
            self.Refresh_ui()
            event.accept()
        else:
            event.ignore()

    def _Show_context_menu(self, position: QPoint):
        _items = self.selectedItems()
        _count = len(_items)
        _menu = QMenu()

        # ==========================================
        # Case 1: 선택된 항목이 없을 때 (빈 공간 클릭)
        # ==========================================
        if _count == 0:
            _add_act = QAction("Add Group at Root", self)
            _add_act.triggered.connect(
                lambda: self._Request_add(None, self.stage.root))
            _menu.addAction(_add_act)

        # ==========================================
        # Case 2: 단일 항목 선택 시
        # ==========================================
        elif _count == 1 and (_target := self._Get_node(_items[0])):
            _add_child_act = QAction("Add Child Group", self)
            _add_child_act.triggered.connect(
                lambda: self._Request_add(None, _target))
            _menu.addAction(_add_child_act)

            # 최상위 루트 노드는 삭제 불가
            if _target.parent is not None:
                _menu.addSeparator()
                _del_act = QAction("Delete Node", self)
                _del_act.triggered.connect(self._Request_delete)
                _menu.addAction(_del_act)

        # ==========================================
        # Case 3: 다중 항목 선택 시 (2개 이상)
        # ==========================================
        else:
            _parents = {item.parent() for item in _items}

            # 1. 묶어서 그룹화 (Grouping)
            # 조건(루트 미포함 & 공통 부모)을 만족할 때만 메뉴 추가
            if len(_parents) == 1 and None not in _parents:
                _group_act = QAction(f"Group {_count} Nodes Together", self)
                _parent = self._Get_node(list(_parents)[0])
                
                if _parent:
                    _group_act.triggered.connect(
                        lambda: self._Request_group(_items, _parent))
                    _menu.addAction(_group_act)

            # 2. 다중 삭제 (Delete)
            # 메뉴에 이미 앞서 등록된 항목(그룹화)이 있을 때만 구분선 추가
            if not _menu.isEmpty():
                _menu.addSeparator()
                
            # 루트(None)가 선택 영역에 포함되어 있다면 루트를 제외한 개수만 삭제함을 명시
            _deletable_count = _count - 1 if None in _parents else _count
            
            if _deletable_count > 0:
                _del_act = QAction(f"Delete {_deletable_count} Node(s)", self)
                _del_act.triggered.connect(self._Request_delete)
                _menu.addAction(_del_act)

        # 메뉴에 추가된 Action이 하나라도 있을 때만 화면에 띄움 (방어 로직)
        if not _menu.isEmpty():
            _menu.exec(self.mapToGlobal(position))

    # ==========================================
    # 신규 기능: 선택 항목 그룹화 요청
    # ==========================================
    def _Request_group(self, items: list[QTreeWidgetItem], parent: Scene_Node):
        """공통 부모를 가진 여러 노드를 새로운 빈 그룹 아래로 일괄 이동시킴."""
        
        # 1. 새 빈 그룹 노드를 생성하여 공통 부모 아래에 추가
        _new_group = Scene_Node("New_Group", "Xform") # 데이터 구조에 맞게 생성
        self.stage.Add_node(_new_group, parent)

        # 2. 선택된 기존 노드들을 방금 만든 새 그룹 산하로 일괄 이동 (트랜잭션)
        _is_changed = False
        for _item in items:
            _node = self._Get_node(_item)
            if _node:
                # Move_node(이동할 노드, 원래 부모, 새 부모)
                if self.stage.Move_node(_node, parent, _new_group):
                    _is_changed = True

        # 3. 데이터가 변경되었다면 1회만 화면 갱신
        if _is_changed:
            self.Refresh_ui()

    def _Request_add(self, node: Scene_Node | None, parent: Scene_Node):
        self.stage.Add_node(node, parent)
        self.Refresh_ui()

    def _Request_delete(self):
        """선택된 여러 아이템을 안전하게 일괄 삭제함."""
        _nodes_to_delete = []
        
        for _item in self.selectedItems():
            if _item.parent(): # 루트 노드는 파괴 대상에서 제외
                _node = self._Get_node(_item)
                _parent = self._Get_node(_item.parent())
                if _node and _parent:
                    _nodes_to_delete.append((_node, _parent))

        _is_changed = False
        for _n, _p in _nodes_to_delete:
            if self.stage.Pop_node(_n, _p):
                _is_changed = True

        if _is_changed:
            self.Refresh_ui()

    def _On_selection_changed(self):
        """선택 영역이 변경될 때마다 선택된 노드 리스트를 외부로 브로드캐스트함."""
        _nodes = self.Get_selected_nodes()
        self.selection_changed.emit(_nodes)
