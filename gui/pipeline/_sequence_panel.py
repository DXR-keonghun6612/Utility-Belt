"""process 시퀀스 빌더 — 블록을 자유롭게 추가/삭제/순서변경.

블록 카드를 세로로 쌓아 시퀀스를 표현한다. 출력으로 Session 이 받는
process config meta 리스트를 제공한다.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.pipeline._block import BATCH_KEYS, Block, WRAPPER_KEY


class Sequence_panel(QWidget):
    """process 블록 시퀀스 편집 패널."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._blocks: list[Block] = []
        self._build()

    def _build(self) -> None:
        _root = QVBoxLayout(self)
        _root.setContentsMargins(0, 0, 0, 0)

        _root.addWidget(QLabel("Process 시퀀스"))

        _top = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.addItems(BATCH_KEYS)
        _top.addWidget(self._combo, stretch=1)
        _add = QPushButton("+ 블록 추가")
        _add.clicked.connect(self._on_add)
        _top.addWidget(_add)
        _root.addLayout(_top)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)

        _holder = QWidget()
        _holder.setLayout(self._list_layout)
        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setWidget(_holder)
        _root.addWidget(_scroll, stretch=1)

    def _on_add(self) -> None:
        _key = self._combo.currentText()
        if _key:
            self.add_block(_key)

    def add_block(self, key: str) -> Block:
        _block = Block(key)
        _block.changed.connect(self.changed)
        _block.remove_requested.connect(self._on_remove)
        _block.move_requested.connect(self._on_move)
        self._blocks.append(_block)
        self._relayout()
        self.changed.emit()
        return _block

    def _on_remove(self, block: Block) -> None:
        self._blocks.remove(block)
        block.setParent(None)
        block.deleteLater()
        self._relayout()
        self.changed.emit()

    def _on_move(self, block: Block, direction: int) -> None:
        _i = self._blocks.index(block)
        _j = _i + direction
        if 0 <= _j < len(self._blocks):
            self._blocks[_i], self._blocks[_j] = self._blocks[_j], self._blocks[_i]
            self._relayout()
            self.changed.emit()

    def _relayout(self) -> None:
        while self._list_layout.count():
            _item = self._list_layout.takeAt(0)
            if _item.widget():
                _item.widget().setParent(None)
        for _block in self._blocks:
            self._list_layout.addWidget(_block)
        self._list_layout.addStretch(1)

    def configs(self) -> list[dict]:
        """순서대로의 process config meta 리스트."""
        return [_b.to_config() for _b in self._blocks]
