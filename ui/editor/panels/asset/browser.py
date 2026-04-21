from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QFileDialog, QAbstractItemView, QComboBox
)
from PySide6.QtCore import Qt, Signal, Slot

from spatial_toolbox.scene.asset.cache import ASSET_CACHE
from spatial_toolbox.scene.file import Load_and_register
from ui.editor.panels.asset.duplicate_dialog import Duplicate_Dialog
from ui.core.base_panel import Base_Panel


# Unit 프리셋: (표기, 1단위당 미터 수)
_UNIT_PRESETS: list[tuple[str, float]] = [
    ("km", 1000.0),
    ("m", 1.0),
    ("cm", 0.01),
    ("mm", 0.001),
]
_UNIT_DEFAULT_INDEX = 1  # "m"


class Asset_Browser_Panel(Base_Panel):
    """에셋 라이브러리 목록을 시각화하고 씬으로의 인스턴스화 요청을 담당하는 패널임."""

    asset_removed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def _connect_signals(self) -> None:
        self.bus.scene_loaded.connect(self.Clear_assets)

    def _setup_ui(self):
        _btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Import Asset")
        self.btn_remove = QPushButton("Remove")
        self.btn_duplicates = QPushButton("Find Duplicates")
        _btn_layout.addWidget(self.btn_load)
        _btn_layout.addWidget(self.btn_remove)
        _btn_layout.addWidget(self.btn_duplicates)

        self.main_layout.addLayout(_btn_layout)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Name", "Path", "Unit"])
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setUniformRowHeights(True)

        # 열 폭을 내용 기준으로 산정 + 마지막 열 stretch 해제 → 좌우 스크롤 활성화
        _header = self.tree.header()
        _header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        _header.setStretchLastSection(False)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tree.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.main_layout.addWidget(self.tree)

        self.btn_load.clicked.connect(self._on_load_clicked)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        self.btn_duplicates.clicked.connect(self._on_find_duplicates_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

    @Slot()
    def _on_load_clicked(self):
        _files, _ = QFileDialog.getOpenFileNames(
            self, "Import 3D Asset", "", "OBJ (*.obj)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if not _files:
            return

        for _f in _files:
            if ASSET_CACHE.Get(_f) is not None:
                continue
            Load_and_register(_f)

        self._Rebuild_tree()

    @Slot(QTreeWidgetItem, int)
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """리프 항목 더블클릭 시 도메인 계층으로 인스턴스화 이벤트를 방출함."""
        _key = item.data(0, Qt.ItemDataRole.UserRole)
        if not _key:
            return
        self.bus.asset_instantiate_requested.emit(_key)

    @Slot()
    def _on_remove_clicked(self):
        _items = self.tree.selectedItems()
        if not _items:
            return

        _key = _items[0].data(0, Qt.ItemDataRole.UserRole)
        if not _key:
            return

        if ASSET_CACHE.Remove(_key):
            self.asset_removed.emit(_key)
            self._Rebuild_tree()

    @Slot()
    def Clear_assets(self) -> None:
        ASSET_CACHE.Clear()
        self.tree.clear()

    @Slot()
    def _on_find_duplicates_clicked(self) -> None:
        Duplicate_Dialog(parent=self).exec()

    def _Rebuild_tree(self) -> None:
        """ASSET_CACHE의 타입 버킷을 순회하여 트리를 재구성함."""
        self.tree.clear()

        for _type_cls, _bucket in ASSET_CACHE.cache.items():
            _type_item = QTreeWidgetItem([_type_cls.__name__, "", ""])
            # 그룹 노드는 선택 불가 (리프만 Remove / Instantiate 대상)
            _type_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(_type_item)

            for _key_tuple, _asset in _bucket.items():
                _path, _fragment = _key_tuple
                _name = Path(_path).stem
                _display = _name if _fragment is None else f"{_name}#{_fragment}"
                _key_str = _path if _fragment is None else f"{_path}#{_fragment}"

                _child = QTreeWidgetItem([_display, _path, ""])
                _child.setData(0, Qt.ItemDataRole.UserRole, _key_str)
                _type_item.addChild(_child)

                _combo = self._Build_unit_combo(_asset.unit_length, _key_str)
                self.tree.setItemWidget(_child, 2, _combo)

            _type_item.setExpanded(True)

    def _Build_unit_combo(self, current_unit: float, key: str) -> QComboBox:
        """단위 프리셋 콤보박스를 생성하고 현재 값에 맞는 항목을 선택함."""
        _combo = QComboBox()
        for _label, _value in _UNIT_PRESETS:
            _combo.addItem(_label, _value)

        # 현재 unit_length에 정확히 매칭되는 프리셋 선택, 부재 시 m 기본
        _idx = next(
            (i for i, (_, v) in enumerate(_UNIT_PRESETS) if v == current_unit),
            _UNIT_DEFAULT_INDEX,
        )
        _combo.setCurrentIndex(_idx)

        # 초기 인덱스 설정 이후 시그널 연결 → 빌드 중 불필요한 방출 방지
        _combo.currentIndexChanged.connect(
            lambda _idx: self._On_unit_changed(key, _combo.currentData())
        )
        return _combo

    def _On_unit_changed(self, key: str, value: float) -> None:
        """콤보박스 선택에 따라 ASSET_CACHE 내 에셋의 unit_length 값을 치환함."""
        _asset = ASSET_CACHE.Get(key, is_hold=True)
        if _asset is None:
            return
        _asset.unit_length = float(value)
