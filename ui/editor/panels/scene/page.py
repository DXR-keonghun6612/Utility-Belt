from pathlib import Path
from PySide6.QtWidgets import (
    QVBoxLayout, QSplitter, QHBoxLayout, QLineEdit,
    QPushButton, QFileDialog
)
from PySide6.QtCore import Qt, Slot

from spatial_toolbox.scene import Controller as Stage_Controller
from spatial_toolbox.scene.node import Camera as Camera_Node
from ui.core.base_panel import Base_Panel

from .scene_tree import Scene_Tree_Widget
from .property import Property_Panel

class Outliner_Panel(Base_Panel):
    """검색창, 트리 뷰, I/O 툴바를 결합한 관리 패널. Base_Panel 표준화됨."""

    def __init__(self, stage: Stage_Controller, parent=None):
        self.stage = stage
        super().__init__(parent)

    def _setup_ui(self):
        # Base_Panel의 main_layout을 직접 사용
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search nodes...")
        self.search_bar.textChanged.connect(self._On_search_text_changed)
        self.main_layout.addWidget(self.search_bar)

        self.tree_widget = Scene_Tree_Widget(self.stage)
        self.main_layout.addWidget(self.tree_widget)

        _tb_layout = QHBoxLayout()
        self.btn_add_group = QPushButton("New Group")
        self.btn_add_camera = QPushButton("New Camera")
        self.btn_delete = QPushButton("Delete")
        
        self.btn_add_group.clicked.connect(self._On_add_group_clicked)
        self.btn_add_camera.clicked.connect(self._On_add_camera_clicked)
        self.btn_delete.clicked.connect(self.tree_widget._Request_delete)

        _tb_layout.addWidget(self.btn_add_group)
        _tb_layout.addWidget(self.btn_add_camera)
        _tb_layout.addWidget(self.btn_delete)
        self.main_layout.addLayout(_tb_layout)

        _io_layout = QHBoxLayout()
        self.btn_save_scene = QPushButton("Save Scene")
        self.btn_load_scene = QPushButton("Load Scene")
        
        self.btn_save_scene.clicked.connect(self._On_save_scene_clicked)
        self.btn_load_scene.clicked.connect(self._On_load_scene_clicked)
        
        _io_layout.addWidget(self.btn_save_scene)
        _io_layout.addWidget(self.btn_load_scene)
        self.main_layout.addLayout(_io_layout)

    def _connect_signals(self):
        # [수정] 외부 트리거에 의한 트리 갱신을 위해 EVENT_BUS 수신
        self.bus.scene_mutated.connect(self.tree_widget.Refresh_ui)
        self.bus.scene_loaded.connect(self.tree_widget.Refresh_ui)

    def _On_search_text_changed(self, text: str):
        _items = self.tree_widget.findItems("", Qt.MatchFlag.MatchRecursive | Qt.MatchFlag.MatchContains)
        for _item in _items:
            _item.setHidden(text.lower() not in _item.text(0).lower())

    def _On_add_group_clicked(self):
        _selected = self.tree_widget.Get_selected_nodes()
        _parent = _selected[0] if _selected else self.stage.root
        self.tree_widget._Request_add(None, _parent)

    def _On_add_camera_clicked(self):
        _selected = self.tree_widget.Get_selected_nodes()
        _parent = _selected[0] if _selected else self.stage.root
        _cam = Camera_Node(label="new_camera", prim_type="Camera")
        _cam.Set_parent(_parent)
        _parent.children.append(_cam)
        self.bus.scene_mutated.emit() # 트리 및 뷰어 일괄 갱신 지시

    def _On_save_scene_clicked(self):
        _path, _ = QFileDialog.getSaveFileName(
            self, "Save Scene", "", "Scene Files (*.json)", options=QFileDialog.Option.DontUseNativeDialog)
        if _path: self.stage.Save(Path(_path))

    def _On_load_scene_clicked(self):
        _path, _ = QFileDialog.getOpenFileName(
            self, "Load Scene", "", "Scene Files (*.json)", options=QFileDialog.Option.DontUseNativeDialog)
        if _path:
            self.stage.Load(Path(_path))
            self.bus.scene_loaded.emit()

class Scene_Explorer_Page(Base_Panel):
    """Outliner와 Inspector를 결합하는 씬 탐색기 래퍼. Base_Panel 표준화됨."""

    def __init__(self, stage: Stage_Controller, parent=None):
        self.stage = stage
        super().__init__(parent)

    def _setup_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.outliner = Outliner_Panel(self.stage)
        self.inspector = Property_Panel()

        self.splitter.addWidget(self.outliner)
        self.splitter.addWidget(self.inspector)
        self.splitter.setSizes([400, 600])

        self.main_layout.addWidget(self.splitter)

    def _connect_signals(self):
        self.bus.selection_changed.connect(self._On_selection_changed)
        self.bus.scene_loaded.connect(lambda: self.inspector.Update_info(None))

    @Slot(list)
    def _On_selection_changed(self, nodes: list):
        self.inspector.Update_info(nodes[0] if len(nodes) == 1 else None)