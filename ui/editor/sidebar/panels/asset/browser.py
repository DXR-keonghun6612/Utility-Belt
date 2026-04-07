from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Signal, Slot, Qt
from data.asset import Asset_Cache
from data.asset.type.mesh import Mesh_Asset
from data.node import Base_Node
from data.io.loader import load_as_asset, load_as_node
from ui.editor.sidebar.panels.asset.duplicate_dialog import Duplicate_Dialog

class Asset_Browser_Panel(QWidget):
    """에셋 라이브러리 목록을 시각화하고 씬으로의 인스턴스화 요청을 담당하는 패널임."""

    # 에셋이 씬에 배치되어야 할 때 방출하는 시그널
    instantiate_requested = Signal(object)
    asset_removed = Signal(str)

    def __init__(self, asset_cache: Asset_Cache, parent=None):
        super().__init__(parent)
        self.res_manager = asset_cache
        self._init_ui()

    def _init_ui(self):
        _layout = QVBoxLayout(self)
        _layout.setContentsMargins(5, 5, 5, 5)

        # 1. 제어 버튼 영역
        _btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Import Asset")
        self.btn_remove = QPushButton("Remove")
        self.btn_duplicates = QPushButton("Find Duplicates")
        _btn_layout.addWidget(self.btn_load)
        _btn_layout.addWidget(self.btn_remove)
        _btn_layout.addWidget(self.btn_duplicates)
        _layout.addLayout(_btn_layout)

        # 2. 에셋 목록 테이블 영역
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Path"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # 읽기 전용 및 행 단위 선택 설정
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        _layout.addWidget(self.table)

        # 3. 이벤트 와이어링
        self.btn_load.clicked.connect(self._on_load_clicked)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        self.btn_duplicates.clicked.connect(self._on_find_duplicates_clicked)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

    @Slot()
    def _on_load_clicked(self):
        """파일을 선택하여 에셋 캐시에 등록하고 목록에 표시함."""
        _files, _ = QFileDialog.getOpenFileNames(
            self, "Import 3D Asset", "", "OBJ (*.obj)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        for _f in _files:
            # 캐시에 이미 있으면 스킵
            if self.res_manager.Get(_f) is not None:
                continue

            _assets = load_as_asset(_f)
            if _assets:
                self.res_manager.Register(_f, _assets)
                # 첫 번째 에셋의 label을 대표명으로 사용
                self._update_table(_assets[0].label, _f)

    @Slot(QTableWidgetItem)
    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """목록의 에셋을 더블 클릭 시, Scene_Node로 변환하여 씬 배치를 요청함."""
        _row = item.row()
        _path_item = self.table.item(_row, 1)
        if not _path_item:
            return

        _path_key = _path_item.text()
        # io를 통해 Scene_Node 트리로 변환하여 씬에 전달
        _node = load_as_node(_path_key)
        if _node:
            self.instantiate_requested.emit(_node)

    @Slot()
    def _on_remove_clicked(self):
        """선택된 에셋을 라이브러리에서 제거함."""
        _selected = self.table.selectedItems()
        if not _selected: return

        _row = _selected[0].row()
        _path_item = self.table.item(_row, 1)
        if not _path_item: return

        _path_key = _path_item.text()

        if self.res_manager.Remove(_path_key):
            self.table.removeRow(_row)
            self.asset_removed.emit(_path_key)

    @Slot()
    def Clear_assets(self) -> None:
        """씬이 초기화될 때 모든 에셋 데이터를 캐시에서 해제하고 UI를 비움."""
        self.res_manager.Clear()
        self.table.setRowCount(0)

    @Slot()
    def _on_find_duplicates_clicked(self) -> None:
        """중복 에셋 검출 다이얼로그를 표시함."""
        Duplicate_Dialog(self.res_manager, parent=self).exec()

    def _update_table(self, name: str, path: str):
        """성공적으로 로드된 정보를 UI에 반영함."""
        _row = self.table.rowCount()
        self.table.insertRow(_row)
        self.table.setItem(_row, 0, QTableWidgetItem(name))
        self.table.setItem(_row, 1, QTableWidgetItem(path))
