"""Flow 카드 목록 — 추가/삭제/순서 변경."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.meta_page.run._flow_card import Flow_card
from gui.widgets import drop, reorder


class Flow_sequence(QWidget):
    """``Flow_card`` 목록을 추가/삭제/순서 변경하는 편집 패널.

    Attributes:
        changed: 카드 추가/삭제/이동/내부 편집이 일어날 때 emit하는 시그널.
    """

    changed = Signal()

    def __init__(self, parent=None) -> None:
        """패널을 구성한다.

        Args:
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._cards: list[Flow_card] = []
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)

        self._top = QHBoxLayout()
        _add = QPushButton("+ Flow 추가")
        _add.clicked.connect(self._on_add)
        self._top.addWidget(_add)
        self._top.addStretch()
        _lay.addLayout(self._top)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        _holder = QWidget()
        _holder.setLayout(self._list_layout)
        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setWidget(_holder)
        _lay.addWidget(_scroll, stretch=1)

    def _on_add(self) -> None:
        _card = Flow_card()
        _card.changed.connect(self.changed)
        _card.remove_requested.connect(self._on_remove)
        _card.move_requested.connect(self._on_move)
        self._cards.append(_card)
        self._relayout()
        self.changed.emit()

    def _on_remove(self, card: Flow_card) -> None:
        self._cards.remove(card)
        drop(card)
        self._relayout()
        self.changed.emit()

    def _on_move(self, card: Flow_card, direction: int) -> None:
        _i = self._cards.index(card)
        _j = _i + direction
        if 0 <= _j < len(self._cards):
            self._cards[_i], self._cards[_j] = self._cards[_j], self._cards[_i]
            self._relayout()
            self.changed.emit()

    def _relayout(self) -> None:
        reorder(self._list_layout, self._cards, stretch=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_top_widgets(self, *widgets: QWidget) -> None:
        """상단 줄(+ Flow 추가 버튼 행)의 오른쪽 끝에 위젯을 추가한다.

        추가 버튼과 신축 스페이서 뒤에 붙으므로, 넘긴 위젯들은 우측 끝으로 몰린다.

        Args:
            *widgets: 상단 줄 우측에 배치할 위젯들 (예: 실행/중단 버튼).
        """
        for _w in widgets:
            self._top.addWidget(_w)

    def to_config(self) -> list[dict]:
        """모든 카드를 flow config dict 리스트로 직렬화한다.

        Returns:
            카드 순서대로의 flow config dict 목록.
        """
        return [_c.to_config() for _c in self._cards]

    def load(self, configs: list) -> None:
        """flow config 리스트로 카드들을 복원한다.

        Args:
            configs: flow config dict 목록.
        """
        for _c in list(self._cards):
            self._cards.remove(_c)
            drop(_c)
        for _d in (configs or []):
            if not isinstance(_d, dict):
                continue
            _card = Flow_card()
            _card.changed.connect(self.changed)
            _card.remove_requested.connect(self._on_remove)
            _card.move_requested.connect(self._on_move)
            self._cards.append(_card)
            _card.load(_d)
        self._relayout()
