from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Signal, Slot

from spatial_toolbox.scene.asset.cache import ASSET_CACHE, Parse_key
from spatial_toolbox.scene.file import Load_and_register
from ui.editor.panels.asset.duplicate_dialog import Duplicate_Dialog
from ui.core.base_panel import Base_Panel

class Asset_Browser_Panel(Base_Panel):
    """에셋 라이브러리 목록을 시각화하고 씬으로의 인스턴스화 요청을 담당하는 패널임."""

    asset_removed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def _connect_signals(self) -> None:
        self.bus.scene_loaded.connect(self.Clear_assets)

    def _setup_ui(self):
        # [수정] QVBoxLayout(self) 중복 선언 제거, 부모 main_layout 재사용
        _btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Import Asset")
        self.btn_remove = QPushButton("Remove")
        self.btn_duplicates = QPushButton("Find Duplicates")
        _btn_layout.addWidget(self.btn_load)
        _btn_layout.addWidget(self.btn_remove)
        _btn_layout.addWidget(self.btn_duplicates)
        
        self.main_layout.addLayout(_btn_layout)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Path"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.main_layout.addWidget(self.table)

        self.btn_load.clicked.connect(self._on_load_clicked)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        self.btn_duplicates.clicked.connect(self._on_find_duplicates_clicked)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

    @Slot()
    def _on_load_clicked(self):
        _files, _ = QFileDialog.getOpenFileNames(
            self, "Import 3D Asset", "", "OBJ (*.obj)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        for _f in _files:
            if ASSET_CACHE.Get(_f) is not None:
                continue

            _asset_keys = Load_and_register(_f)
            if _asset_keys:
                for _key in _asset_keys:
                    _path_key, _fragment_key = Parse_key(_key)
                    _path_key = Path(_path_key).stem

                    if _fragment_key is None:
                        self._update_table(_path_key, _f)
                    else:
                        self._update_table(
                            f"{_path_key}#{_fragment_key}", _f)

    @Slot(QTableWidgetItem)
    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """목록 더블클릭 시 도메인 계층으로 인스턴스화 이벤트를 방출함."""
        _row = item.row()
        _path_item = self.table.item(_row, 1)
        if not _path_item:
            return

        _path_key = _path_item.text()
        
        # [수정] 환각 함수(load_as_node) 제거 및 이벤트 버스로 키 전달
        self.bus.asset_instantiate_requested.emit(_path_key)

    @Slot()
    def _on_remove_clicked(self):
        _selected = self.table.selectedItems()
        if not _selected: return

        _row = _selected[0].row()
        _path_item = self.table.item(_row, 1)
        if not _path_item: return

        _path_key = _path_item.text()

        if ASSET_CACHE.Remove(_path_key):
            self.table.removeRow(_row)
            self.asset_removed.emit(_path_key)

    @Slot()
    def Clear_assets(self) -> None:
        ASSET_CACHE.Clear()
        self.table.setRowCount(0)

    @Slot()
    def _on_find_duplicates_clicked(self) -> None:
        Duplicate_Dialog(parent=self).exec()

    def _update_table(self, name: str, path: str):
        _row = self.table.rowCount()
        self.table.insertRow(_row)
        self.table.setItem(_row, 0, QTableWidgetItem(name))
        self.table.setItem(_row, 1, QTableWidgetItem(path))