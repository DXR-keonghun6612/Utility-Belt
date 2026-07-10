"""class 재배정 대상 선택 다이얼로그 — 검색 필터 + 목록 (id_map class 가 수백 개일 때).

정본 params 의 id_map class 후보를 필터로 좁혀 하나 고른다. 편집형 콤보로는 수백 개를 훑기 어려워
별도 창으로 뺐다 — 다중선택 재배정에서 "선택한 sample 들 → 이 class 로" 의 대상을 정한다.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import Pop_dialog


class Class_picker(Pop_dialog):
    """class 후보 목록 + 검색 필터. ``exec()`` 후 ``selected()`` 로 고른 class (취소·미선택이면 None)."""

    def __init__(self, classes, parent=None) -> None:
        super().__init__("class 재배정 — 대상 선택", size=(360, 500), parent=parent)
        self._chosen: str | None = None
        self._all = sorted(set(classes))
        self._build()
        self._populate("")

    def _build(self) -> None:
        _w = QWidget()
        _l = QVBoxLayout(_w)
        _l.setContentsMargins(0, 0, 0, 0)
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("class 검색…")
        self._filter.textChanged.connect(self._populate)
        _l.addWidget(self._filter)
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _it: self._accept())
        _l.addWidget(self._list, stretch=1)
        self._set_body(_w)
        self._bottom_bar(buttons=QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                         on_accept=self._accept, on_reject=self.reject)

    def _populate(self, text: str) -> None:
        _t = text.strip().lower()
        self._list.clear()
        for _c in self._all:
            if _t in _c.lower():
                self._list.addItem(_c)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _accept(self) -> None:
        _it = self._list.currentItem()
        self._chosen = _it.text() if _it is not None else None
        self.accept()

    def selected(self) -> str | None:
        return self._chosen
