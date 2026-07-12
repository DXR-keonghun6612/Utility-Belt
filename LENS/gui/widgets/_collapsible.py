"""접히는 섹션 — 헤더 클릭으로 본문을 감춘다 (도메인 비의존, core 의존 0).

``QSplitter`` 안에서도 동작하도록, 접힐 때 max height 를 헤더 높이로 고정한다 — splitter 가 그만큼만
내주고 나머지 공간을 형제 섹션에 넘긴다. 펴지면 해제해 다시 드래그로 크기를 나눌 수 있다.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QToolButton, QVBoxLayout, QWidget

_MAX_H = 16_777_215        # Qt 의 QWIDGETSIZE_MAX (PySide6 빌드에 따라 심볼이 없어 값으로 둔다)


class Collapsible(QWidget):
    """제목 헤더 + 접히는 본문. 접으면 헤더만 남고 형제가 공간을 가져간다.

    Attributes:
        toggled: 펼침/접힘이 바뀜 ``(bool)``.
    """

    toggled = Signal(bool)

    def __init__(self, title: str, content: QWidget, *,
                 expanded: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._content = content

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(0)

        self._header = QToolButton()
        self._header.setText(title)
        self._header.setCheckable(True)
        self._header.setChecked(expanded)
        self._header.setAutoRaise(True)
        self._header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._header.setStyleSheet(
            "QToolButton { text-align: left; padding: 3px 4px; font-weight: bold;"
            " border: none; }")
        self._header.toggled.connect(self._apply)

        _lay.addWidget(self._header)
        _lay.addWidget(content, stretch=1)
        self._apply(expanded)

    def _apply(self, expanded: bool) -> None:
        self._header.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._content.setVisible(expanded)
        self.setMaximumHeight(
            _MAX_H if expanded else self._header.sizeHint().height())
        self.toggled.emit(expanded)

    def set_expanded(self, expanded: bool) -> None:
        """프로그램적으로 펼침/접힘 (헤더 상태를 바꾼다)."""
        self._header.setChecked(expanded)
