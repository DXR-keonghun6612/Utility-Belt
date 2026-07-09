"""params 트리 패널 — key별 value를 재귀적으로 펼쳐 보여준다."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QVBoxLayout,
)

from gui.meta_page._adapter import value_node
from gui.widgets import make_tree


class Params_panel(QGroupBox):
    """``params`` (``dict[str, Any]``) 을 트리로 보여준다."""

    def __init__(self, parent=None) -> None:
        super().__init__("params", parent)
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(4, 4, 4, 4)
        self._tree = make_tree(
            headers=["key", "value"],
            resize=[QHeaderView.ResizeToContents, QHeaderView.Stretch],
            alternating=True)
        _lay.addWidget(self._tree)

    def load(self, params: dict[str, Any]) -> None:
        """``params`` 내용으로 트리를 채운다."""
        self._tree.clear()
        for _k, _v in params.items():
            self._tree.addTopLevelItem(value_node(_k, _v))
        self.setTitle(f"params  ({len(params)} entries)")

    def clear(self) -> None:
        """패널을 비운다."""
        self._tree.clear()
        self.setTitle("params")
