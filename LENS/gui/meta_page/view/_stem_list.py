"""staging stem 목록 — 상태별 뱃지 + **체크박스로 모은 대상** 우클릭 전이/삭제 (요청만 emit, 표시만).

**가상화(QListView + 모델)** — 6.5만 개 stem 에서 항목마다 위젯을 만들면 채우기·전이 후 재구축이
UI 를 수 초 얼린다. 위젯 대신 모델 행으로 들면 보이는 것만 렌더해 목록 크기와 무관하게 상수 시간이다.
그래서 여기는 데이터(``(stem, state)`` 행 + 상태별 순번)만 들고, 렌더는 뷰가 필요할 때 ``data`` 로 묻는다.

순번(``#id``)은 각 상태를 따로 세는 목록 내 자리라, 전이/삭제로 구성이 바뀌면 모델 리셋 때 다시 매긴다.

**검색은 표시만 거른다.** 모델이 전체(``_all``)와 보이는 행(``_rows``)을 나눠 들고, 검색어는 후자만
다시 세운다 — 체크(작업 대상)도 순번도 전체 기준이라 그대로 남는다. 그래서 걸러 놓고 체크한 뒤 검색어를
지워도 모아 둔 것이 유지되고, 같은 stem 이 검색 전후로 같은 번호로 보인다. 필터는 전량 1회 훑기(O(n))이고
타이핑은 디바운스한다.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from core.store import Dataset_Meta

# data 롤 — stem 이름 + 현재 상태 (메뉴·포커스 계산에서 state별 구분에 쓴다)
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


class _Stem_model(QAbstractListModel):
    """``(stem, state)`` 행 목록 — 표시 텍스트·색·순번을 요청받아 돌려준다 (위젯 없이).

    행 자체는 가볍고(문자열 둘), 라벨·색은 ``data`` 에서 그때그때 짓는다. 순번(``_ids``)만 리셋 때
    한 번 계산해 나른다 — ``data`` 마다 세면 O(n²)가 되므로.
    """

    def __init__(self) -> None:
        super().__init__()
        # **전체**와 **보이는 것**을 나눠 든다 — 검색은 표시를 거를 뿐 목록 자체를 바꾸지 않는다.
        # 순번(#id)은 전체 기준으로 한 번 매겨 필터를 타고 그대로 간다: 검색할 때마다 번호가 바뀌면
        # 같은 stem 이 다른 번호로 보여 못 쫓는다.
        self._all: list[tuple[str, str, int]] = []  # (stem, state, #id) — 전체 (카테고리 순 · 이름순)
        self._filter = ""                           # 소문자 부분일치 (빈 문자열 = 전부)
        self._rows: list[tuple[str, str]] = []      # (stem, state) — **보이는** 행
        self._ids: list[int] = []                   # 행별 상태내 순번 (#id) — _rows 와 정렬
        self._counts: dict[str, int] = {}           # 상태별 개수 (전체 기준 — 검색과 무관)
        self._index_of: dict[str, int] = {}         # stem → **보이는** row (선택 복원·포커스 O(1))
        self._checked: set[str] = set()             # 체크된 stem — **선택·검색과 무관하게 지속**(작업 대상)

    # ── Qt 모델 계약 ───────────────────────────────────────────────────────────
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def flags(self, index: QModelIndex):
        """체크박스가 그려지도록 ``ItemIsUserCheckable`` 을 단다. 실제 토글은 위젯이 행 클릭으로 하고
        (``setData`` 는 기본 False 라 Qt 의 체크박스-직접토글은 무효), 그래서 체크박스든 텍스트든 한 번만 뒤집힌다."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        _stem, _state = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"#{self._ids[index.row()]}  {_stem}   [{_badge(_state)[0]}]"
        if role == Qt.ItemDataRole.ForegroundRole:
            return _badge(_state)[1]
        if role == Qt.ItemDataRole.CheckStateRole:
            return (Qt.CheckState.Checked if _stem in self._checked
                    else Qt.CheckState.Unchecked)
        if role == _STEM_ROLE:
            return _stem
        if role == _STATE_ROLE:
            return _state
        return None

    # ── 채우기 ────────────────────────────────────────────────────────────────
    def set_rows(self, meta: Dataset_Meta) -> None:
        """두 버킷의 stem 을 카테고리 순서(``CATEGORIES``) + 카테고리 안 이름 오름차순으로 채운다.

        전이로 순서가 뒤섞이지 않게 이름순으로 세우고, 상태별 순번(``#id``)도 여기서 매긴다.
        """
        self._all = []
        _seq: dict[str, int] = {}
        for _state in meta.CATEGORIES:
            for _stem in sorted(meta.Bucket(_state)):
                _id = _seq.get(_state, 0)
                _seq[_state] = _id + 1
                self._all.append((_stem, _state, _id))
        self._counts = {_st: len(meta.Bucket(_st)) for _st in meta.CATEGORIES}
        # 체크는 **전체** 기준으로 거른다 — 검색으로 안 보이는 것까지 버리면 모아 둔 대상이 날아간다.
        self._checked &= {_s for _s, _, _ in self._all}
        self._apply_filter()

    def set_filter(self, text: str) -> None:
        """검색어 설정 — 부분일치(대소문자 무시)로 **표시만** 거른다 (체크·순번은 그대로)."""
        _f = (text or "").strip().lower()
        if _f == self._filter:
            return
        self._filter = _f
        self._apply_filter()

    def _apply_filter(self) -> None:
        """전체에서 보이는 행을 다시 세운다 — 전량 1회 훑기(O(n)), 항목별 증분 없음."""
        self.beginResetModel()
        if self._filter:
            _keep = [(_s, _st, _i) for _s, _st, _i in self._all if self._filter in _s.lower()]
        else:
            _keep = self._all
        self._rows = [(_s, _st) for _s, _st, _ in _keep]
        self._ids = [_i for _, _, _i in _keep]
        self._index_of = {_stem: _i for _i, (_stem, _st) in enumerate(self._rows)}
        self.endResetModel()

    def visible_count(self) -> int:
        """지금 보이는 행 수 (검색 결과 수)."""
        return len(self._rows)

    def total_count(self) -> int:
        """검색과 무관한 전체 stem 수."""
        return len(self._all)

    def clear(self) -> None:
        self.beginResetModel()
        self._all = []
        self._rows, self._ids, self._counts, self._index_of = [], [], {}, {}
        self._checked = set()
        self.endResetModel()

    # ── 체크 (선택과 무관하게 지속) ─────────────────────────────────────────────
    def toggle_check(self, row: int) -> None:
        """그 행의 체크를 뒤집는다 — 위젯이 **행 클릭**으로 부른다(체크박스든 텍스트든)."""
        if not 0 <= row < len(self._rows):
            return
        _stem = self._rows[row][0]
        self._checked.discard(_stem) if _stem in self._checked else self._checked.add(_stem)
        _idx = self.index(row, 0)
        self.dataChanged.emit(_idx, _idx, [Qt.ItemDataRole.CheckStateRole])

    def update_checked(self, add, remove) -> None:
        """체크 집합을 델타로 갱신 — shift/ctrl **선택**이 부른다(선택된 건 추가, 해제된 건 제거).

        선택을 체크에 미러링하되 델타만 건드린다 — shift/ctrl 밖(Enter·다른 카테고리)에서 모아 둔 체크는
        선택에 없어도 유지된다. 바뀐 행만 dataChanged 로 알려 6.5만 행에서도 상수 비용이다.
        """
        _add = {_s for _s in add if _s in self._index_of} - self._checked
        _rem = {_s for _s in remove if _s in self._checked}
        if not _add and not _rem:
            return
        self._checked |= _add
        self._checked -= _rem
        _rows = [self._index_of[_s] for _s in (_add | _rem)]
        self.dataChanged.emit(self.index(min(_rows), 0), self.index(max(_rows), 0),
                              [Qt.ItemDataRole.CheckStateRole])

    def checked(self) -> set[str]:
        return set(self._checked)

    def clear_checked(self) -> None:
        """모든 체크를 푼다 (전이/삭제로 소비된 뒤)."""
        if not self._checked:
            return
        self._checked = set()
        if self._rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, 0),
                                  [Qt.ItemDataRole.CheckStateRole])

    # ── 조회 ──────────────────────────────────────────────────────────────────
    def rows(self) -> list[tuple[str, str]]:
        return self._rows

    def counts(self) -> dict[str, int]:
        return self._counts

    def row_of(self, stem: str) -> int | None:
        return self._index_of.get(stem)


class _Stem_view(QListView):
    """Enter 로 현재 항목의 체크를 토글하는 QListView — Enter 는 여기서 삼켜 위(폼 기본 동작)로 안 샌다.

    이 뷰는 Enter 토글만 안다. shift/ctrl 다중 선택을 체크에 미러링하는 건 부모(:class:`Stem_list`)가
    ``selectionChanged`` 로 한다.
    """

    enter_pressed = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.enter_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class Stem_list(QWidget):
    """stem 목록(상태 뱃지) — **체크박스로 작업 대상 표시** + 우클릭 전이/삭제, 더블클릭 팝아웃.

    **작업 대상은 선택이 아니라 체크다.** 체크는 선택과 무관하게 지속돼, 여러 카테고리에 섞인 것을 훑으며
    모아 뒀다가 우클릭 한 번으로 다 옮긴다. 체크하는 길은 둘:

    - **단일 클릭·화살표는 탐색만** (그 stem 을 편집기에 띄우기), 체크는 안 건드린다. 항목을 선택하고
      **Enter** 를 누르면 그 항목 체크가 토글된다(다시 Enter 로 풀린다).
    - **shift/ctrl 다중 선택**은 그 선택을 체크에 미러링한다 — 선택된 건 체크, (shift/ctrl 로) 선택 해제된
      건 언체크. 한 번에 여러 개를 빠르게 모을 때. Enter 로 따로 모은 체크는 선택에 없어도 유지된다.

    Attributes:
        selected: 현재(포커스) stem 이 바뀌어 본문 편집기에 띄울 때 emit (없으면 "").
        to_state_requested: **체크된** stem 들을 그 상태로 보내달라는 요청 ``(state, [stem…])``.
        delete_requested: **체크된** stem 들을 삭제해달라는 요청 ``[stem…]``.
        popout_requested: stem 더블클릭 — 별도 창 요청.
    """

    selected           = Signal(str)
    to_state_requested = Signal(str, list)
    delete_requested   = Signal(list)
    popout_requested   = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._editable = True               # 편집 잠금 (잠그면 전이/삭제 메뉴만 막고 선택은 유지)
        self._focus_after: str | None = None  # 전이 후 포커스할 stem (이동 전에 계산해 다음 load 가 소비)
        self._loading = False               # load/clear 중 — 프로그램 선택이 selected 를 흘리지 않게
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(2)
        # 검색 — 6.5만 행이라 타이핑마다 훑으면 입력이 끊긴다. **디바운스** 후 1회만 거른다.
        self._search = QLineEdit()
        self._search.setPlaceholderText("stem 검색 (부분일치)")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _t: self._search_timer.start())
        _lay.addWidget(self._search)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._apply_search)

        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #666;")
        _lay.addWidget(self._count_label)

        self._model = _Stem_model()
        self._view = _Stem_view()
        self._view.setModel(self._model)
        self._view.setMinimumWidth(120)         # 폭은 splitter 가 조절 (좌우 연동)
        self._view.setUniformItemSizes(True)    # 모든 행 같은 높이 — 6.5만 행에서 측정 비용 제거
        self._view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)  # 단일=탐색 / shift·ctrl=다중→체크
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_menu)
        self._view.enter_pressed.connect(self._on_toggle_current)  # 선택 항목에서 Enter → 체크 토글
        self._view.doubleClicked.connect(self._on_double_click)
        self._view.selectionModel().currentChanged.connect(self._on_current_changed)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)  # shift·ctrl → 체크 미러
        _lay.addWidget(self._view)
        self._refresh_count()

    # ── 신호 ──────────────────────────────────────────────────────────────────
    def _on_current_changed(self, *_args) -> None:
        if self._loading:                    # 프로그램 선택(load 중)은 흘리지 않는다 — load 가 한 번만 emit
            return
        self.selected.emit(self.current_stem())

    def _on_selection_changed(self, selected, deselected) -> None:
        """**shift/ctrl 로 선택할 때만** 선택을 체크에 미러링한다 — 선택된 건 체크, 해제된 건 언체크.

        수정자 없는 단일 클릭은 탐색만(기존 동선 — 체크 안 건드림). shift/ctrl 이 눌린 동안은 다중 선택이
        곧 작업 대상 표시라, 현재 선택 전체를 체크에 더하고 방금 선택 해제된 것만 체크에서 뺀다(앵커까지
        포함되게 델타가 아니라 전체 선택을 더한다). Enter 로 모아 둔 체크는 선택에 없어도 유지된다.
        """
        if self._loading:                                # 프로그램 선택(load 중)은 미러링 안 함
            return
        _mods = QApplication.keyboardModifiers()
        if not (_mods & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier)):
            return
        _sel = [self._model.data(_i, _STEM_ROLE)
                for _i in self._view.selectionModel().selectedIndexes()]
        _des = [self._model.data(_i, _STEM_ROLE) for _i in deselected.indexes()]
        self._model.update_checked([_s for _s in _sel if _s], [_s for _s in _des if _s])
        self._refresh_count()

    def _on_toggle_current(self) -> None:
        """선택(현재) 항목에서 **Enter** 를 누르면 체크를 뒤집는다 (다시 Enter 로 풀린다).

        마우스·화살표 선택은 탐색만 하고 체크를 안 건드린다 — 자유롭게 훑다가 **Enter 로만** 작업 대상을
        표시한다. 체크는 선택과 무관하게 지속된다.
        """
        _idx = self._view.currentIndex()
        if _idx.isValid():
            self._model.toggle_check(_idx.row())
            self._refresh_count()

    def _on_double_click(self, index) -> None:
        _stem = self._model.data(index, _STEM_ROLE)
        if _stem:
            self.popout_requested.emit(_stem)

    def _on_menu(self, pos) -> None:
        """**체크된** stem 들에 대한 우클릭 메뉴 — **모든 다른 상태**로 보내기(그 상태가 아닌 것만) + 삭제.

        `Dataset_Meta.CATEGORIES` 를 순회해 현재 상태가 아닌 대상마다 "→ 라벨 로 보내기 (n)" 를 만든다 —
        상태 수가 늘어도(예: skipped) 코드 수정 없이 항목이 생긴다. 보낼 대상 0이면 그 항목은 뺀다.
        대상은 **체크된 것들**(선택과 무관·지속). 체크가 하나도 없으면 우클릭한 그 행 하나를 대상으로 한다.
        """
        if not self._editable:               # 잠금 중(백그라운드 작업)엔 전이/삭제 메뉴 없음
            return
        _sel = self._menu_targets(pos)
        if not _sel:
            return
        _menu = QMenu(self)
        for _state in Dataset_Meta.CATEGORIES:
            _targets = [_stem for _stem, _st in _sel if _st != _state]
            if not _targets:
                continue
            _label = _badge(_state)[0]
            _a = QAction(f"→ '{_label}' 로 보내기  ({len(_targets)})", _menu)
            _a.triggered.connect(
                lambda _checked=False, s=_state, t=_targets: self._request_to_state(s, t))
            _menu.addAction(_a)
        if _menu.actions():
            _menu.addSeparator()
        _all = [_stem for _stem, _st in _sel]
        _del = QAction(f"🗑  삭제  ({len(_all)})", _menu)
        _del.triggered.connect(lambda _checked=False, t=_all: self._request_delete(t))
        _menu.addAction(_del)
        _menu.exec(self._view.viewport().mapToGlobal(pos))

    def _menu_targets(self, pos) -> list[tuple[str, str]]:
        """메뉴가 상태별로 가를 ``(stem, state)`` 목록 — **체크된 것들**(선택과 무관).

        체크가 하나도 없으면 우클릭한 그 행 하나로 떨어진다 — 한 개만 빠르게 옮기려고 굳이 체크했다
        풀 필요가 없게(옛 단일 우클릭 동선 보존).
        """
        _checked = self._model.checked()
        if _checked:
            return [(_stem, _st) for _stem, _st in self._model.rows() if _stem in _checked]
        _idx = self._view.indexAt(pos)                # 체크 없음 → 우클릭한 행 하나
        if _idx.isValid():
            return [(self._model.data(_idx, _STEM_ROLE), self._model.data(_idx, _STATE_ROLE))]
        return []

    def _request_to_state(self, state: str, targets: list) -> None:
        """전이 요청을 올리되, **이동 전** 목록 기준으로 전이 후 포커스할 stem 을 미리 잡아둔다.

        포커스는 이동 대상을 따라가지 않고 소스 카테고리에 남는다 — 다음 ``load`` 가 소비한다.
        체크는 이 요청으로 **소비**되므로 곧바로 푼다(작업이 끝나면 마크가 남아 다음 이동에 딸려가지 않게).
        """
        self._focus_after = self._next_focus(targets)
        self.to_state_requested.emit(state, targets)
        self._model.clear_checked()
        self._refresh_count()

    def _request_delete(self, targets: list) -> None:
        """삭제 요청을 올리되, **삭제 전** 목록 기준으로 삭제 후 포커스할 stem 을 미리 잡아둔다.

        전이와 같은 이웃 규칙이되, 소스 카테고리가 통째로 사라지면 (따라갈 목적지가 없으므로)
        다음 카테고리로 옮긴다 — 다음 ``load`` 가 소비한다. 체크는 이 요청으로 소비되므로 곧바로 푼다.
        """
        self._focus_after = self._next_focus(targets, removed=True)
        self.delete_requested.emit(targets)
        self._model.clear_checked()
        self._refresh_count()

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
        _rows = self._model.rows()
        _src = next((_st for _stem, _st in _rows if _stem in _moved), None)  # 소스 = 첫 대상의 상태
        if _src is None:
            return None
        _seq = [_stem for _stem, _st in _rows if _st == _src]   # 소스 카테고리 stem 들 (목록 순서 = 순번)
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
        _rows = self._model.rows()
        _idx = [_i for _i, (_stem, _st) in enumerate(_rows) if _st == src]
        if not _idx:
            return None
        for _i in range(max(_idx) + 1, len(_rows)):              # 뒤(다음 카테고리) 우선
            if _rows[_i][0] not in moved:
                return _rows[_i][0]
        for _i in range(min(_idx) - 1, -1, -1):                  # 없으면 앞(이전 카테고리)
            if _rows[_i][0] not in moved:
                return _rows[_i][0]
        return None

    # ── 조회 ──────────────────────────────────────────────────────────────────
    def current_stem(self) -> str:
        """현재(포커스) stem (없으면 "")."""
        _idx = self._view.currentIndex()
        return (self._model.data(_idx, _STEM_ROLE) or "") if _idx.isValid() else ""

    def focus_list(self) -> None:
        """목록(QListView)에 키보드 포커스를 준다 (저장 후 화살표로 stem 이동하려면)."""
        self._view.setFocus()

    def list_has_focus(self) -> bool:
        """목록(QListView)이 현재 키보드 포커스를 쥐고 있으면 True (Tab 토글 판정용)."""
        return self._view.hasFocus()

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 토글 — 목록은 열어두고(선택·팝아웃 보기 유지) 전이/삭제 메뉴만 막는다."""
        self._editable = editable

    # ── 채우기 ────────────────────────────────────────────────────────────────
    def load(self, meta: Dataset_Meta, keep: str = "") -> None:
        """두 버킷의 stem 을 상태 뱃지와 함께 채운다 (``keep`` 선택 유지 시도).

        전이 직후엔 미리 잡아둔 ``_focus_after`` 가 ``keep`` 을 덮어써 포커스가 이동 대상을 따라가지
        않게 한다(일회성). 모델 리셋이라 목록 크기와 무관하게 상수 시간이다(위젯을 다시 만들지 않는다).

        Args:
            meta: 표시할 ``Dataset_Meta``.
            keep: 갱신 후 선택을 유지할 stem (없거나 사라졌으면 첫 항목).
        """
        if self._focus_after is not None:              # 전이 후 지정 포커스가 우선 (일회성)
            keep = self._focus_after
            self._focus_after = None
        self._loading = True
        self._model.set_rows(meta)
        _row = self._model.row_of(keep)
        if _row is None and self._model.rowCount():
            _row = 0
        if _row is not None:
            _idx = self._model.index(_row, 0)
            self._view.setCurrentIndex(_idx)           # current(탐색 포커스) — 체크와는 무관
            self._view.scrollTo(_idx)
        self._loading = False
        self._refresh_count()
        self.selected.emit(self.current_stem())

    def focus(self, stem: str) -> bool:
        """밖에서 지목한 stem 을 잡아 보여준다 (찾으면 True) — 목록 재구축 없이 선택만 옮긴다.

        **검색에 걸러져 있으면 검색을 지운다.** 지목은 "이걸 보여 달라" 는 명령인데 필터 때문에 조용히
        아무 일도 안 일어나면, 왜 안 되는지 알 길이 없다(필터는 화면 이쪽에 있고 지목은 저쪽에서 온다).

        선택이 바뀌면 ``selected`` 가 흘러 본문이 그 stem 을 편다 — 여기서 따로 안 부른다.
        """
        _row = self._model.row_of(stem)
        if _row is None and self._search.text():
            self._search.clear()                       # 걸러져 있었다 (debounce 뒤 _apply_search 는 no-op)
            self._model.set_filter("")
            self._refresh_count()
            _row = self._model.row_of(stem)
        if _row is None:
            return False
        _idx = self._model.index(_row, 0)
        self._view.setCurrentIndex(_idx)
        self._view.scrollTo(_idx)
        return True

    def _apply_search(self) -> None:
        """디바운스 만료 — 검색어를 모델에 넘기고, 보이던 stem 이 남아 있으면 그대로 붙잡는다.

        검색은 **표시만** 거른다: 체크(작업 대상)도 상태별 순번(#id)도 그대로다. 그래서 걸러 놓고 체크한
        뒤 검색어를 지워도 모아 둔 것이 유지된다.
        """
        _keep = self.current_stem()
        self._loading = True                        # 프로그램 선택이 selected 를 흘리지 않게
        self._model.set_filter(self._search.text())
        _row = self._model.row_of(_keep)
        if _row is None and self._model.rowCount():
            _row = 0
        if _row is not None:
            _idx = self._model.index(_row, 0)
            self._view.setCurrentIndex(_idx)
            self._view.scrollTo(_idx)
        self._loading = False
        self._refresh_count()
        if self.current_stem() != _keep:            # 보던 stem 이 걸러졌다 — 편집기도 따라가게
            self.selected.emit(self.current_stem())

    def _refresh_count(self) -> None:
        """상단 개수 라벨 갱신 — 전체 + 상태별(라벨 순) + 검색 결과 + 체크 수(있을 때).

        체크 수를 함께 보여야 여러 카테고리에 섞인 것을 몇 개 골라 뒀는지 한눈에 안다(선택과 달리 지속되므로).
        검색 중이면 **몇 개가 걸렸는지**를 함께 보여 "안 보이는 게 없어진 것이 아님"을 드러낸다.
        """
        _counts = self._model.counts()
        _total = sum(_counts.values())
        _parts = "   ·   ".join(
            f"{_badge(_st)[0]} {_counts.get(_st, 0)}" for _st in Dataset_Meta.CATEGORIES)
        _nchecked = len(self._model.checked())
        _check = f"   ·   ☑ {_nchecked}" if _nchecked else ""
        _found = (f"   ·   검색 {self._model.visible_count()}"
                  if self._search.text().strip() else "")
        self._count_label.setText(
            f"전체 {_total}" + (f"   ·   {_parts}" if _parts else "") + _found + _check)

    def clear(self) -> None:
        """목록·개수를 비운다."""
        self._loading = True
        self._model.clear()
        self._loading = False
        self._refresh_count()
        self.selected.emit("")
