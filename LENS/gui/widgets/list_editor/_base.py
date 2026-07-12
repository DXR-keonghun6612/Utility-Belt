"""동적 list editor 베이스 — 행(``List_row``) + 행 목록(``List_editor``) (메커니즘만, 설계는 README)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .._layout import drop

_REMOVE_W = 26   # ✕ 버튼 폭 — 헤더 끝을 그만큼 비워 컬럼을 맞춘다


class _Header_row(QWidget):
    """컬럼 머리글 한 줄 — 행의 폭 규격과 **같은 값**으로 지어야 정렬이 맞는다."""

    def __init__(self, headers: list[tuple[str, int, str]], parent=None) -> None:
        super().__init__(parent)
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)
        for _text, _width, _tip in headers:
            _lbl = QLabel(_text)
            _lbl.setStyleSheet("color: #888; font-size: 11px;")
            if _tip:
                _lbl.setToolTip(_tip)
            if _width:
                _lbl.setFixedWidth(_width)
                _lay.addWidget(_lbl)
            else:
                _lay.addWidget(_lbl, stretch=1)
        _lay.addSpacing(_REMOVE_W)          # ✕ 자리


class List_row(QWidget):
    """``List_editor`` 한 행의 골격 — 시그널 + ✕ 버튼 헬퍼.

    서브클래스는 자기 필드를 만들어 각 필드의 변경 시그널을 ``self.changed`` 에 잇고, 행 끝에
    ``self._remove_button()`` 을 배치한다. ``to_config`` 로 ``(key, value)`` 직렬화를 구현한다.

    Attributes:
        changed: 행 내용이 바뀔 때 emit하는 시그널.
        remove_requested: ✕ 클릭 시 자기 자신을 담아 emit하는 시그널.
    """

    changed          = Signal()
    remove_requested = Signal(object)

    def _remove_button(self) -> QToolButton:
        """✕ 제거 버튼을 만들어 돌려준다 (클릭 시 ``remove_requested`` 로 자신을 emit)."""
        _rm = QToolButton()
        _rm.setText("✕")
        _rm.clicked.connect(lambda: self.remove_requested.emit(self))
        return _rm

    def to_config(self) -> tuple[str, object]:
        """행을 ``(key, value)`` 로 직렬화한다 (서브클래스 구현; key 빈 행은 상위에서 버림)."""
        raise NotImplementedError


class List_editor(QWidget):
    """행(``List_row``) 동적 목록 편집기 베이스 — 추가/삭제 + 기본 dict 직렬화.

    서브클래스는 ``_make_row(key, spec)`` 만 구현하면 추가버튼·삭제·직렬화가 따라온다. 기본
    ``to_config``/``load`` 는 ``{key: spec}`` 맵용(glob/outputs)이며, 다른 직렬화가 필요하면
    (예: ``Pair_list_editor`` 의 list) 서브클래스가 ``_clear_rows``/``_add_row`` 위에 재정의한다.

    Attributes:
        changed: 행 추가/삭제/편집 시 emit하는 시그널.
    """

    changed = Signal()

    def __init__(self, add_label: str = "+ 추가", parent: QWidget | None = None,
                 headers: list[tuple[str, int, str]] | None = None) -> None:
        """편집기를 구성한다.

        Args:
            add_label: 하단 추가 버튼 라벨.
            parent: 부모 위젯.
            headers: 컬럼 머리글 ``[(라벨, 고정폭(0=stretch), 툴팁), …]``. 행이 라벨 없는 한 줄
                입력들로 이뤄지면 placeholder 만으로는 무엇을 넣는 칸인지 안 보인다 — 컬럼이 **고정된**
                행에만 준다(칸이 상황에 따라 숨는 행은 헤더가 어긋나므로 툴팁으로 대신한다).
        """
        super().__init__(parent)
        self._rows: list[List_row] = []
        self._root_lay = QVBoxLayout(self)
        self._root_lay.setContentsMargins(0, 0, 0, 0)
        self._root_lay.setSpacing(2)
        if headers:
            self._root_lay.addWidget(_Header_row(headers))
        self._list_lay = QVBoxLayout()
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(2)
        self._root_lay.addLayout(self._list_lay)
        self._root_lay.addStretch(1)   # 행은 위로 밀착, 추가 버튼은 바닥에 고정
        _add = QPushButton(add_label)
        _add.clicked.connect(lambda: self._add_row(emit=True))
        self._root_lay.addWidget(_add)

    def _make_row(self, key, spec) -> List_row:
        """``(key, spec)`` 으로 행을 만든다 (서브클래스 구현)."""
        raise NotImplementedError

    def _add_row(self, key="", spec=None, emit: bool = False) -> List_row:
        """행을 만들어 목록에 추가한다 (행 시그널을 자신에 잇고, opt emit)."""
        _row = self._make_row(key, spec)
        _row.changed.connect(self.changed)
        _row.remove_requested.connect(self._remove_row)
        self._rows.append(_row)
        self._list_lay.addWidget(_row)
        if emit:
            self.changed.emit()
        return _row

    def _remove_row(self, row: List_row) -> None:
        """행을 목록에서 빼고 파괴한다 (``changed`` emit)."""
        if row in self._rows:
            self._rows.remove(row)
        drop(row)
        self.changed.emit()

    def _clear_rows(self) -> None:
        """모든 행을 비운다 (재로드 공용 — ``changed`` 는 emit하지 않음)."""
        for _row in list(self._rows):
            self._rows.remove(_row)
            drop(_row)

    def to_config(self) -> dict:
        """모든 행을 ``{key: spec}`` dict로 직렬화한다 (key가 빈 행은 제외)."""
        _result: dict = {}
        for _row in self._rows:
            _k, _v = _row.to_config()
            if _k:
                _result[_k] = _v
        return _result

    def load(self, d: dict | None) -> None:
        """``{key: spec}`` dict로 행들을 다시 만든다 (로드는 ``changed`` 를 내지 않음)."""
        self._clear_rows()
        for _k, _v in (d or {}).items():
            self._add_row(str(_k), _v)
