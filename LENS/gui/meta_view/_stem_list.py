"""staging stem 목록 — 상태별 id + 뱃지 + 다중선택 우클릭 메뉴 (요청만 emit, 표시·증분 갱신만).

id 는 modified/staged 를 따로 세는 목록 내 순번(각 0부터)이라, 전이/삭제로 구성이 바뀌면
``_renumber`` 로 다시 매긴다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from core.data.meta import Dataset_Meta

# 항목 data 롤 — stem 이름 + 현재 상태 (메뉴에서 state별 구분에 쓴다)
_STEM_ROLE  = Qt.ItemDataRole.UserRole
_STATE_ROLE = Qt.ItemDataRole.UserRole + 1

# 상태별 뱃지 텍스트 + 색 (목록 항목 전경색)
_BADGE: dict[str, tuple[str, QColor]] = {
    "modified": ("변경됨", QColor(0xE0, 0x7B, 0x00)),   # 주황
    "staged":   ("staged", QColor(0x1E, 0x6F, 0xD0)),   # 파랑
}


class Stem_list(QWidget):
    """stem 목록(상태 뱃지) — 다중선택 + 우클릭 전이/삭제, 더블클릭 팝아웃.

    Attributes:
        selected: 현재(포커스) stem 이 바뀌어 본문 편집기에 띄울 때 emit (없으면 "").
        to_state_requested: 선택 stem 들을 그 상태로 보내달라는 요청 ``(state, [stem…])``.
        delete_requested: 선택 stem 들을 삭제해달라는 요청 ``[stem…]``.
        popout_requested: stem 더블클릭 — 별도 창 요청.
    """

    selected           = Signal(str)
    to_state_requested = Signal(str, list)
    delete_requested   = Signal(list)
    popout_requested   = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._counts: dict[str, int] = {"modified": 0, "staged": 0}
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(2)
        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #666;")
        _lay.addWidget(self._count_label)
        self._list = QListWidget()
        self._list.setMinimumWidth(120)         # 폭은 splitter 가 조절 (좌우 연동, maxWidth 제거)
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_menu)
        self._list.currentItemChanged.connect(self._on_current_changed)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        _lay.addWidget(self._list)
        self._refresh_count()

    # ── 신호 ──────────────────────────────────────────────────────────────────
    def _on_current_changed(self, *_args) -> None:
        self.selected.emit(self.current_stem())

    def _on_double_click(self, item: QListWidgetItem) -> None:
        _stem = item.data(_STEM_ROLE)
        if _stem:
            self.popout_requested.emit(_stem)

    def _on_menu(self, pos) -> None:
        """선택 stem 들에 대한 우클릭 메뉴 — 보낼 곳별로 **이미 그 상태가 아닌 것만** 센다.

        예) 선택 5개 중 3개가 modified 면 'staged 로 보내기 (3)', 2개가 staged 면 'modified 로
        보내기 (2)'. 보낼 대상이 0이면 그 항목은 뺀다. 삭제는 선택 전체.
        """
        _items = self._list.selectedItems()
        if not _items:
            return
        _to_staged = [_it.data(_STEM_ROLE) for _it in _items if _it.data(_STATE_ROLE) != "staged"]
        _to_mod    = [_it.data(_STEM_ROLE) for _it in _items if _it.data(_STATE_ROLE) != "modified"]
        _all       = [_it.data(_STEM_ROLE) for _it in _items]

        _menu = QMenu(self)
        if _to_staged:
            _a = QAction(f"→ staged 로 보내기  ({len(_to_staged)})", _menu)
            _a.triggered.connect(lambda: self.to_state_requested.emit("staged", _to_staged))
            _menu.addAction(_a)
        if _to_mod:
            _a = QAction(f"→ modified 로 보내기  ({len(_to_mod)})", _menu)
            _a.triggered.connect(lambda: self.to_state_requested.emit("modified", _to_mod))
            _menu.addAction(_a)
        if _menu.actions():
            _menu.addSeparator()
        _del = QAction(f"🗑  삭제  ({len(_all)})", _menu)
        _del.triggered.connect(lambda: self.delete_requested.emit(_all))
        _menu.addAction(_del)
        _menu.exec(self._list.viewport().mapToGlobal(pos))

    # ── 조회 ──────────────────────────────────────────────────────────────────
    def current_stem(self) -> str:
        """현재(포커스) stem (없으면 "")."""
        _it = self._list.currentItem()
        return _it.data(_STEM_ROLE) if _it is not None else ""

    def focus_list(self) -> None:
        """목록(QListWidget)에 키보드 포커스를 준다 (저장 후 화살표로 stem 이동하려면)."""
        self._list.setFocus()

    def list_has_focus(self) -> bool:
        """목록(QListWidget)이 현재 키보드 포커스를 쥐고 있으면 True (Tab 토글 판정용)."""
        return self._list.hasFocus()

    # ── 채우기/증분 갱신 ───────────────────────────────────────────────────────
    def load(self, meta: Dataset_Meta, keep: str = "") -> None:
        """두 버킷의 stem 을 상태 뱃지와 함께 채운다 (``keep`` 선택 유지 시도).

        Args:
            meta: 표시할 ``Dataset_Meta``.
            keep: 갱신 후 선택을 유지할 stem (없거나 사라졌으면 첫 항목).
        """
        self._list.blockSignals(True)
        self._list.clear()
        _target: QListWidgetItem | None = None
        for _state, _stem, _frame in meta.Iter_all():
            _it = self._make_item(_stem, _state)
            self._list.addItem(_it)
            if _stem == keep:
                _target = _it
        self._renumber()
        if _target is None and self._list.count():
            _target = self._list.item(0)
        self._list.setCurrentItem(_target)
        self._list.blockSignals(False)
        self._counts = {_st: len(meta.Bucket(_st)) for _st in meta.STATES}
        self._refresh_count()
        self.selected.emit(self.current_stem())

    def _refresh_count(self) -> None:
        """상단 개수 라벨 갱신 — 전체 / 변경됨(modified) / staged."""
        _m, _s = self._counts.get("modified", 0), self._counts.get("staged", 0)
        self._count_label.setText(f"전체 {_m + _s}   ·   변경됨 {_m}   ·   staged {_s}")

    @staticmethod
    def _make_item(stem: str, state: str) -> QListWidgetItem:
        """빈 항목에 stem/state 롤만 심는다 (표시 텍스트·색은 ``_renumber`` 가 매긴다)."""
        _it = QListWidgetItem()
        _it.setData(_STEM_ROLE, stem)
        _it.setData(_STATE_ROLE, state)
        return _it

    def _renumber(self) -> None:
        """모든 항목의 표시 텍스트를 상태별 id(각 상태 0부터) + 뱃지로 다시 매긴다.

        id 는 modified/staged 를 따로 세는 목록 내 순번이라, 전이/삭제로 구성이 바뀌면 다시
        부른다 (항목 자체는 유지 — 텍스트/색만 갱신). 표시 텍스트 포맷의 단일 소스.
        """
        _seq: dict[str, int] = {}
        for _i in range(self._list.count()):
            _it = self._list.item(_i)
            _stem = _it.data(_STEM_ROLE)
            _state = _it.data(_STATE_ROLE)
            _id = _seq.get(_state, 0)
            _seq[_state] = _id + 1
            _label, _color = _BADGE.get(_state, (_state, QColor(0, 0, 0)))
            _it.setText(f"#{_id}  {_stem}   [{_label}]")
            _it.setForeground(_color)

    def update_state(self, stem: str, state: str) -> None:
        """한 stem 항목의 상태 + 개수를 갱신하고 id/뱃지를 다시 매긴다 (전이 후 — 전체 재구성 없이)."""
        for _i in range(self._list.count()):
            _it = self._list.item(_i)
            if _it.data(_STEM_ROLE) == stem:
                _old = _it.data(_STATE_ROLE)
                _it.setData(_STATE_ROLE, state)
                if _old != state:
                    self._counts[_old] = self._counts.get(_old, 0) - 1
                    self._counts[state] = self._counts.get(state, 0) + 1
                    self._refresh_count()
                self._renumber()             # 전이로 두 상태의 순번이 밀린다
                return

    def remove(self, stem: str) -> None:
        """한 stem 항목을 목록·개수에서 제거하고 id 를 다시 매긴다 (삭제 후 — 전체 재구성 없이)."""
        for _i in range(self._list.count()):
            _it = self._list.item(_i)
            if _it.data(_STEM_ROLE) == stem:
                _st = _it.data(_STATE_ROLE)
                self._counts[_st] = self._counts.get(_st, 0) - 1
                self._list.takeItem(_i)
                self._refresh_count()
                self._renumber()             # 뒤 항목들의 순번이 당겨진다
                return

    def clear(self) -> None:
        """목록·개수를 비운다."""
        self._list.blockSignals(True)
        self._list.clear()
        self._list.blockSignals(False)
        self._counts = {"modified": 0, "staged": 0}
        self._refresh_count()
        self.selected.emit("")
