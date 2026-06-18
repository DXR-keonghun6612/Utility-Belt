"""결과 썸네일 그리드 — class별 결과를 보고 다중 선택한다."""

from __future__ import annotations

from pathlib import Path

import cv2

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from gui.widgets import _bgr_to_pixmap


_THUMB = 128


class Grid(QListWidget):
    """썸네일 아이콘 그리드 (다중 선택)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(_THUMB, _THUMB))
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setSpacing(6)
        self.setUniformItemSizes(True)
        self._cache: dict[str, QIcon] = {}

    def populate(self, entries: list[dict]) -> None:
        self.clear()
        for _e in entries:
            _item = QListWidgetItem(self._icon(_e["path"]), Path(_e["rel"]).stem)
            _item.setData(Qt.ItemDataRole.UserRole, _e["rel"])
            _item.setToolTip(f'{_e["rel"]}\nclass: {_e["cls"]}')
            self.addItem(_item)

    def _icon(self, path: Path) -> QIcon:
        _key = str(path)
        if _key in self._cache:
            return self._cache[_key]
        _img = cv2.imread(_key, cv2.IMREAD_COLOR)
        _icon = QIcon(_bgr_to_pixmap(_img)) if _img is not None else QIcon()
        self._cache[_key] = _icon
        return _icon

    def selected_rels(self) -> set[str]:
        return {_it.data(Qt.ItemDataRole.UserRole) for _it in self.selectedItems()}
