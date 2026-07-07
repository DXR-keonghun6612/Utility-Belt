"""동적 list editor 베이스 — 행(``List_row``) + 행 목록(``List_editor``) (메커니즘만, 설계는 README)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._layout import drop


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

    def __init__(self, add_label: str = "+ 추가", parent: QWidget | None = None) -> None:
        """편집기를 구성한다.

        Args:
            add_label: 하단 추가 버튼 라벨.
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._rows: list[List_row] = []
        self._root_lay = QVBoxLayout(self)
        self._root_lay.setContentsMargins(0, 0, 0, 0)
        self._root_lay.setSpacing(2)
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


# ── 공용 key/value 리스트 편집기 (list 직렬화) ────────────────────────────────

class _Pair_row(List_row):
    """key/value 한 쌍을 편집하는 행 — 옵션으로 📁(파일 선택)·🖉(ROI 그리기) 버튼."""

    def __init__(self, key: str = "", value: str = "", *, kind: str | None = None,
                 draw: bool = False, roi_provider=None, parent=None) -> None:
        super().__init__(parent)
        self._roi_provider = roi_provider

        _rl = QHBoxLayout(self)
        _rl.setContentsMargins(0, 0, 0, 0)
        _rl.setSpacing(2)

        self._key = QLineEdit(key)
        self._key.setPlaceholderText("key")
        self._key.setFixedWidth(140)
        self._key.textChanged.connect(self.changed)
        _rl.addWidget(self._key)

        self._val = QLineEdit(value)
        self._val.setPlaceholderText("path" if kind == "path" else "value")
        self._val.textChanged.connect(self.changed)
        _rl.addWidget(self._val, stretch=1)

        if kind == "path":
            _browse = QToolButton()
            _browse.setText("📁")
            _browse.clicked.connect(self._browse)
            _rl.addWidget(_browse)
        if draw:
            _d = QToolButton()
            _d.setText("🖉")
            _d.setToolTip("ROI 그리기 → 마스크 PNG 생성 (파일명 = key)")
            _d.clicked.connect(self._draw_roi)
            _rl.addWidget(_d)
        _rl.addWidget(self._remove_button())

    def _browse(self) -> None:
        _path, _ = QFileDialog.getOpenFileName(self, "파일 선택")
        if _path:
            self._val.setText(_path)

    def _draw_roi(self) -> None:
        if self._roi_provider is None:
            return
        _path = self._roi_provider(self._key.text().strip())
        if _path:
            self._val.setText(_path)

    def to_config(self) -> tuple[str, str]:
        return self._key.text().strip(), self._val.text().strip()


class Pair_list_editor(List_editor):
    """``list[tuple[str, str]]`` 을 행 단위로 편집하는 위젯 (중복 key·순서 허용).

    ``kind == 'path'`` 면 각 행에 파일 선택(📁), ``draw`` 면 ROI 그리기(🖉) 버튼이 붙는다.
    dict 가 아니라 list 직렬화라 ``pairs``/``set_pairs`` 를 베이스 위에 재정의한다.

    Attributes:
        changed: 행 추가/삭제/편집이 일어날 때 emit하는 시그널.
    """

    def __init__(self, label: str, kind: str | None = None, tip: str = "",
                 draw: bool = False, roi_provider=None, parent=None) -> None:
        """편집기를 구성한다.

        Args:
            label: 상단 라벨 (빈 문자열이면 라벨을 생략한다).
            kind: ``'path'`` 면 값 칸에 파일 선택 버튼을 붙인다.
            tip: 위젯 툴팁.
            draw: True이고 ``roi_provider`` 가 있으면 ROI 그리기 버튼을 붙인다.
            roi_provider: key를 받아 마스크 PNG 경로를 돌려주는 콜백.
            parent: 부모 위젯.
        """
        super().__init__("+ 추가", parent)
        self._kind = kind
        self._draw = draw and roi_provider is not None
        self._roi_provider = roi_provider
        if tip:
            self.setToolTip(tip)
        if label:  # 빈 라벨은 생략 — 위쪽 여백 방지
            self._root_lay.insertWidget(0, QLabel(label))

    def _make_row(self, key, spec) -> List_row:
        return _Pair_row(str(key), str(spec or ""), kind=self._kind,
                         draw=self._draw, roi_provider=self._roi_provider)

    def pairs(self) -> list[tuple[str, str]]:
        """현재 행들을 ``(key, value)`` 리스트로 반환한다 (key가 빈 행은 제외)."""
        return [(_k, _v) for _k, _v in (_r.to_config() for _r in self._rows) if _k]

    def set_pairs(self, pairs: list[tuple[str, str]] | None) -> None:
        """기존 행을 모두 비우고 주어진 쌍들로 다시 채운다.

        Args:
            pairs: 채울 ``(key, value)`` 쌍 목록. None이면 빈 상태로 둔다.
        """
        self._clear_rows()
        for _k, _v in (pairs or []):
            self._add_row(str(_k), str(_v))

    def append(self, key: str, value: str) -> None:
        """행 하나를 추가하고 ``changed`` 를 emit한다.

        Args:
            key: 새 행의 key.
            value: 새 행의 value.
        """
        self._add_row(key, value, emit=True)
