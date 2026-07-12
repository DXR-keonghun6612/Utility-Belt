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

from core.store import Dataset_Meta

# 항목 data 롤 — stem 이름 + 현재 상태 (메뉴에서 state별 구분에 쓴다)
_STEM_ROLE  = Qt.ItemDataRole.UserRole
_STATE_ROLE = Qt.ItemDataRole.UserRole + 1

# 상태별 뱃지 텍스트 + 색 (목록 항목 전경색). 새 상태 추가 시 여기에 한 줄만 더하면 된다 —
# 카운트·메뉴·번호는 meta.CATEGORIES 기준으로 제네릭하게 돈다(미등록 상태는 회색+상태명으로 degrade).
_BADGE: dict[str, tuple[str, QColor]] = {
    "modified": ("작업", QColor(0xE0, 0x7B, 0x00)),   # 주황 — 작업 할거
    "staged":   ("검수", QColor(0x1E, 0x6F, 0xD0)),   # 파랑 — 검수한거
    "skipped":  ("보류", QColor(0x8A, 0x8A, 0x8A)),   # 회색 — 작업 대상 외
}


def _badge(state: str) -> tuple[str, QColor]:
    """상태 → (라벨, 색). 미등록 상태는 상태명 + 회색으로 degrade."""
    return _BADGE.get(state, (state, QColor(0x8A, 0x8A, 0x8A)))


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
        self._editable = True               # 편집 잠금 (잠그면 전이/삭제 메뉴만 막고 선택은 유지)
        self._counts: dict[str, int] = {}   # 상태별 개수 — load 가 meta.CATEGORIES 로 채운다
        self._focus_after: str | None = None  # 전이 후 포커스할 stem (이동 전에 계산해 다음 load 가 소비)
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
        """선택 stem 들에 대한 우클릭 메뉴 — **모든 다른 상태**로 보내기(그 상태가 아닌 것만) + 삭제.

        `Dataset_Meta.CATEGORIES` 를 순회해 현재 상태가 아닌 대상마다 "→ 라벨 로 보내기 (n)" 를 만든다 —
        상태 수가 늘어도(예: skipped) 코드 수정 없이 항목이 생긴다. 보낼 대상 0이면 그 항목은 뺀다.
        """
        if not self._editable:               # 잠금 중(백그라운드 작업)엔 전이/삭제 메뉴 없음
            return
        _items = self._list.selectedItems()
        if not _items:
            return
        _menu = QMenu(self)
        for _state in Dataset_Meta.CATEGORIES:
            _targets = [_it.data(_STEM_ROLE) for _it in _items
                        if _it.data(_STATE_ROLE) != _state]
            if not _targets:
                continue
            _label = _badge(_state)[0]
            _a = QAction(f"→ '{_label}' 로 보내기  ({len(_targets)})", _menu)
            _a.triggered.connect(
                lambda _checked=False, s=_state, t=_targets: self._request_to_state(s, t))
            _menu.addAction(_a)
        if _menu.actions():
            _menu.addSeparator()
        _all = [_it.data(_STEM_ROLE) for _it in _items]
        _del = QAction(f"🗑  삭제  ({len(_all)})", _menu)
        _del.triggered.connect(lambda _checked=False, t=_all: self._request_delete(t))
        _menu.addAction(_del)
        _menu.exec(self._list.viewport().mapToGlobal(pos))

    def _request_to_state(self, state: str, targets: list) -> None:
        """전이 요청을 올리되, **이동 전** 목록 기준으로 전이 후 포커스할 stem 을 미리 잡아둔다.

        포커스는 이동 대상을 따라가지 않고 소스 카테고리에 남는다 — 다음 ``load`` 가 소비한다.
        """
        self._focus_after = self._next_focus(targets)
        self.to_state_requested.emit(state, targets)

    def _request_delete(self, targets: list) -> None:
        """삭제 요청을 올리되, **삭제 전** 목록 기준으로 삭제 후 포커스할 stem 을 미리 잡아둔다.

        전이와 같은 이웃 규칙이되, 소스 카테고리가 통째로 사라지면 (따라갈 목적지가 없으므로)
        다음 카테고리로 옮긴다 — 다음 ``load`` 가 소비한다.
        """
        self._focus_after = self._next_focus(targets, removed=True)
        self.delete_requested.emit(targets)

    def _next_focus(self, moved: list, *, removed: bool = False) -> str | None:
        """전이/삭제 후 포커스할 stem 을 **현재(작업 전) 목록 순서**로 고른다.

        소스 카테고리(가장 위 대상의 상태) 안에서: ① 선택 중 가장 작은 순번의 **한 칸 앞**, 없으면
        ② 가장 큰 순번 **+1**(한 칸 뒤). 둘 다 없으면(그 카테고리가 통째로 비면) ③ 전이는 이동 대상을
        그대로 반환해 이동한 곳으로 따라가고, **삭제는 다음 카테고리**(뒤 우선, 없으면 앞)로 옮긴다.

        Args:
            moved: 이동/삭제할 stem 목록.
            removed: 삭제면 True (③ 처리가 다름 — 목적지가 없으므로).

        Returns:
            포커스할 stem (목록에 없거나 대상이 비면 None → 기본 동작).
        """
        _moved = set(moved)
        _src = None                                    # 소스 카테고리 = 첫(최상위) 대상의 상태
        for _i in range(self._list.count()):
            if self._list.item(_i).data(_STEM_ROLE) in _moved:
                _src = self._list.item(_i).data(_STATE_ROLE)
                break
        if _src is None:
            return None
        _seq = [self._list.item(_i).data(_STEM_ROLE)   # 소스 카테고리 stem 들 (목록 순서 = 순번)
                for _i in range(self._list.count())
                if self._list.item(_i).data(_STATE_ROLE) == _src]
        _sel = [_i for _i, _s in enumerate(_seq) if _s in _moved]
        if not _sel:
            return None
        _lo, _hi = min(_sel), max(_sel)
        if _lo - 1 >= 0:                               # ① 가장 작은 순번 한 칸 앞
            return _seq[_lo - 1]
        if _hi + 1 < len(_seq):                        # ② 가장 큰 순번 +1
            return _seq[_hi + 1]
        if not removed:                                # ③(전이) 소스 카테고리가 비게 됨 → 따라가기
            return moved[0]
        return self._next_category_stem(_src, _moved)  # ③(삭제) 다음 카테고리로

    def _next_category_stem(self, src: str, moved: set) -> str | None:
        """소스 카테고리가 삭제로 통째로 비게 될 때, 남는 항목 중 **소스 뒤(다음 카테고리) 우선**,
        없으면 앞(이전 카테고리)을 고른다 (목록이 통째로 비면 None)."""
        _idx = [_i for _i in range(self._list.count())
                if self._list.item(_i).data(_STATE_ROLE) == src]
        if not _idx:
            return None
        for _i in range(max(_idx) + 1, self._list.count()):      # 뒤(다음 카테고리) 우선
            _s = self._list.item(_i).data(_STEM_ROLE)
            if _s not in moved:
                return _s
        for _i in range(min(_idx) - 1, -1, -1):                  # 없으면 앞(이전 카테고리)
            _s = self._list.item(_i).data(_STEM_ROLE)
            if _s not in moved:
                return _s
        return None

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

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 토글 — 목록은 열어두고(선택·팝아웃 보기 유지) 전이/삭제 메뉴만 막는다."""
        self._editable = editable

    # ── 채우기/증분 갱신 ───────────────────────────────────────────────────────
    def load(self, meta: Dataset_Meta, keep: str = "") -> None:
        """두 버킷의 stem 을 상태 뱃지와 함께 채운다 (``keep`` 선택 유지 시도).

        카테고리 순서(``CATEGORIES``)는 유지하되 **각 카테고리 안은 stem 이름 오름차순**으로 정렬한다
        (전이로 순서가 뒤섞이지 않게). 전이 직후엔 미리 잡아둔 ``_focus_after`` 가 ``keep`` 을 덮어써
        포커스가 이동 대상을 따라가지 않게 한다(일회성).

        Args:
            meta: 표시할 ``Dataset_Meta``.
            keep: 갱신 후 선택을 유지할 stem (없거나 사라졌으면 첫 항목).
        """
        if self._focus_after is not None:              # 전이 후 지정 포커스가 우선 (일회성)
            keep = self._focus_after
            self._focus_after = None
        self._list.blockSignals(True)
        self._list.clear()
        _target: QListWidgetItem | None = None

        for _state in meta.CATEGORIES:                     # 카테고리 순서 유지 + 카테고리 안 오름차순
            for _stem in sorted(meta.Bucket(_state)):
                _it = self._make_item(_stem, _state)
                self._list.addItem(_it)
                if _stem == keep:
                    _target = _it
        self._renumber()
        if _target is None and self._list.count():
            _target = self._list.item(0)
        self._list.setCurrentItem(_target)
        self._list.blockSignals(False)
        self._counts = {_st: len(meta.Bucket(_st)) for _st in meta.CATEGORIES}
        self._refresh_count()
        self.selected.emit(self.current_stem())

    def _refresh_count(self) -> None:
        """상단 개수 라벨 갱신 — 전체 + 상태별(라벨 순, meta.CATEGORIES 기준 제네릭)."""
        _total = sum(self._counts.values())
        _parts = "   ·   ".join(
            f"{_badge(_st)[0]} {self._counts.get(_st, 0)}" for _st in Dataset_Meta.CATEGORIES)
        self._count_label.setText(f"전체 {_total}" + (f"   ·   {_parts}" if _parts else ""))

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
            _label, _color = _badge(_state)
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
        self._counts = {}                    # 비면 _refresh_count 가 CATEGORIES 별 0 으로 표시
        self._refresh_count()
        self.selected.emit("")
