from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QMenu,
    QStyledItemDelegate, QLineEdit
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction, QDropEvent, QIcon, QPixmap, QPainter, QFont

from spatial_toolbox.scene import Controller as Stage_Controller
from spatial_toolbox.scene.node import Base_Node, Group
from spatial_toolbox.scene.file import Load_and_register

from ui.core.event_bus import EVENT_BUS # [수정] 누락된 이벤트 버스 임포트
from .add_asset_dialog import Add_Asset_Dialog

_COL_NAME = 0
_COL_VIS = 1
_ICON_SIZE = 16

def _Make_eye_icon(visible: bool) -> QIcon:
    _pix = QPixmap(_ICON_SIZE, _ICON_SIZE)
    _pix.fill(Qt.GlobalColor.transparent)
    _p = QPainter(_pix)
    _p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _p.setFont(QFont("Segoe UI Symbol", 10))
    if visible:
        _p.setPen(Qt.GlobalColor.white)
        _p.drawText(_pix.rect(), Qt.AlignmentFlag.AlignCenter, "\U0001F441")
    else:
        _p.setPen(Qt.GlobalColor.darkGray)
        _p.drawText(_pix.rect(), Qt.AlignmentFlag.AlignCenter, "—")
    _p.end()
    return QIcon(_pix)

class _Name_Delegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        if index.column() != _COL_NAME: return None
        return QLineEdit(parent)

    def setEditorData(self, editor, index):
        _node = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(_node, Base_Node): editor.setText(_node.label)

    def setModelData(self, editor, model, index):
        _text = editor.text().strip()
        if not _text: return
        _node = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(_node, Base_Node):
            _node.label = _text
            model.setData(index, f"[{_node.prim_type}] {_text}", Qt.ItemDataRole.DisplayRole)
            EVENT_BUS.property_changed.emit() # [수정] 라벨 변경 시 UI 갱신 전파

class Scene_Tree_Widget(QTreeWidget):
    """씬의 계층 구조 시각화 및 Batch 상호작용 트리 컴포넌트."""
    def __init__(self, stage: Stage_Controller, parent=None):
        super().__init__(parent)
        self.stage = stage
        self._Setup_ui()

    def _Setup_ui(self):
        self.setColumnCount(2)
        self.setHeaderLabels(["Hierarchy", ""])
        self.header().setStretchLastSection(False)
        self.header().resizeSection(_COL_VIS, 28)
        self.header().setSectionResizeMode(_COL_NAME, self.header().ResizeMode.Stretch)
        self.header().setSectionResizeMode(_COL_VIS, self.header().ResizeMode.Fixed)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.customContextMenuRequested.connect(self._Show_context_menu)
        self.itemSelectionChanged.connect(self._On_selection_changed)
        self.itemClicked.connect(self._On_item_clicked)

        self.setItemDelegateForColumn(_COL_NAME, _Name_Delegate(self))
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)

    def _Get_node(self, item: QTreeWidgetItem | None) -> Base_Node | None:
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def Get_selected_nodes(self) -> list[Base_Node]:
        return [_node for _item in self.selectedItems() if (_node := self._Get_node(_item))]

    def Refresh_ui(self):
        self.clear()
        if self.stage and self.stage.root:
            self.addTopLevelItem(self._Refresh_tree(self.stage.root))
            self.expandAll()

    def _Refresh_tree(self, node: Base_Node) -> QTreeWidgetItem:
        _item = QTreeWidgetItem([f"[{node.prim_type}] {node.label}"])
        _item.setData(_COL_NAME, Qt.ItemDataRole.UserRole, node)
        _item.setFlags(_item.flags() | Qt.ItemFlag.ItemIsEditable)
        _item.setIcon(_COL_VIS, _Make_eye_icon(node.visible))
        for _child in node.children:
            _item.addChild(self._Refresh_tree(_child))
        return _item

    def _On_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if column != _COL_VIS: return
        if _node := self._Get_node(item):
            _node.visible = not _node.visible
            item.setIcon(_COL_VIS, _Make_eye_icon(_node.visible))
            EVENT_BUS.property_changed.emit() # [수정] 가시성 변경 시 뷰포트 갱신

    def dropEvent(self, event: QDropEvent):
        _dragged = self.selectedItems()
        _new_parent = self._Get_node(self.itemAt(event.position().toPoint())) or self.stage.root
        
        if not _dragged or not _new_parent:
            event.ignore(); return

        _is_changed = False
        for _item in _dragged:
            _node = self._Get_node(_item)
            _old_parent = self._Get_node(_item.parent())
            if not _old_parent or not _node or _node == _new_parent: continue
            if self.stage.Move_node(_node, _old_parent, _new_parent):
                _is_changed = True

        if _is_changed:
            self.Refresh_ui()
            EVENT_BUS.scene_mutated.emit() # [수정] 계층 변경 알림
            event.accept()
        else:
            event.ignore()

    def _Show_context_menu(self, position: QPoint):
        _items = self.selectedItems()
        _count = len(_items)
        _menu = QMenu()

        if _count == 0:
            _act = QAction("Add Group at Root", self)
            _act.triggered.connect(lambda: self._Request_add(None, self.stage.root))
            _menu.addAction(_act)
        elif _count == 1 and (_target := self._Get_node(_items[0])):
            _act = QAction("Add Child Group", self)
            _act.triggered.connect(lambda: self._Request_add(None, _target))
            _menu.addAction(_act)
            if _target.prim_type in ("Stage", "Xform"):
                _act2 = QAction("Add Asset...", self)
                _act2.triggered.connect(lambda: self._Request_add_asset(_target))
                _menu.addAction(_act2)
            if _target.parent is not None:
                _menu.addSeparator()
                _act3 = QAction("Delete Node", self)
                _act3.triggered.connect(self._Request_delete)
                _menu.addAction(_act3)
        else:
            _parents = {item.parent() for item in _items}
            if len(_parents) == 1 and None not in _parents:
                if _parent := self._Get_node(list(_parents)[0]):
                    _act = QAction(f"Group {_count} Nodes Together", self)
                    _act.triggered.connect(lambda: self._Request_group(_items, _parent))
                    _menu.addAction(_act)
            if not _menu.isEmpty(): _menu.addSeparator()
            _deletable = _count - 1 if None in _parents else _count
            if _deletable > 0:
                _act = QAction(f"Delete {_deletable} Node(s)", self)
                _act.triggered.connect(self._Request_delete)
                _menu.addAction(_act)

        if not _menu.isEmpty():
            _menu.exec(self.mapToGlobal(position))

    def _Request_group(self, items: list[QTreeWidgetItem], parent: Base_Node):
        _new_group = Group(label="New_Group", prim_type="Xform")
        _new_group.Set_parent(parent)
        parent.children.append(_new_group)
        _is_changed = False
        for _item in items:
            if _node := self._Get_node(_item):
                if self.stage.Move_node(_node, parent, _new_group): _is_changed = True
        if _is_changed:
            self.Refresh_ui()
            EVENT_BUS.scene_mutated.emit()

    def _Request_add(self, node: Base_Node | None, parent: Base_Node):
        self.stage.Add_node(node, parent)
        self.Refresh_ui()
        EVENT_BUS.scene_mutated.emit()

    def _Request_add_asset(self, parent: Base_Node) -> None:
        _dialog = Add_Asset_Dialog(parent=self)
        if _dialog.exec() != Add_Asset_Dialog.DialogCode.Accepted: return
        _paths = _dialog.Get_selected_paths()
        if not _paths: return
        _is_changed = False
        for _path in _paths:
            if not (_keys := Load_and_register(str(_path))): continue
            for _key in _keys:
                _node = self.stage.Build_node_from_cache(_key)
                self.stage.Add_node(_node, parent)
            _is_changed = True
        if _is_changed:
            self.Refresh_ui()
            EVENT_BUS.scene_mutated.emit()

    def _Request_delete(self):
        _to_delete = []
        for _item in self.selectedItems():
            if _item.parent():
                if (_node := self._Get_node(_item)) and (_parent := self._Get_node(_item.parent())):
                    _to_delete.append((_node, _parent))
        _is_changed = False
        for _n, _p in _to_delete:
            if self.stage.Pop_node(_n, _p): _is_changed = True
        if _is_changed:
            self.Refresh_ui()
            EVENT_BUS.scene_mutated.emit()

    def _On_selection_changed(self):
        EVENT_BUS.selection_changed.emit(self.Get_selected_nodes())