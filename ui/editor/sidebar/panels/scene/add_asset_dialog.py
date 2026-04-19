from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QAbstractItemView, QPushButton,
)
from PySide6.QtCore import Qt

from spatial_toolbox.scene import ASSET_CACHE


class Add_Asset_Dialog(QDialog):
    """캐시된 에셋 중 하나 이상을 다중 선택하여 반환하는 다이얼로그임."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Asset")
        self.resize(460, 360)

        _layout = QVBoxLayout(self)
        _layout.addWidget(QLabel("Select asset(s) to add:"))

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        _layout.addWidget(self.list_widget)

        self._Populate()

        _btn_layout = QHBoxLayout()
        _btn_layout.addStretch()
        self.btn_ok = QPushButton("Add")
        self.btn_ok.setFixedWidth(80)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedWidth(80)
        self.btn_cancel.clicked.connect(self.reject)
        _btn_layout.addWidget(self.btn_ok)
        _btn_layout.addWidget(self.btn_cancel)
        _layout.addLayout(_btn_layout)

        self.btn_ok.setEnabled(False)
        self.list_widget.itemSelectionChanged.connect(
            lambda: self.btn_ok.setEnabled(
                len(self.list_widget.selectedItems()) > 0
            )
        )

    def _Populate(self) -> None:
        """ASSET_CACHE의 등록 경로를 리스트에 채움."""
        for _path in ASSET_CACHE.Get_paths():
            _item = QListWidgetItem(f"{_path.name}    [{_path}]")
            _item.setData(Qt.ItemDataRole.UserRole, _path)
            self.list_widget.addItem(_item)

    def Get_selected_paths(self) -> list[Path]:
        """확인된 선택 경로 목록을 반환함."""
        return [
            _item.data(Qt.ItemDataRole.UserRole)
            for _item in self.list_widget.selectedItems()
        ]
