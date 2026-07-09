"""key/value 쌍 리스트 편집기 — 베이스(``List_editor``) 위에서 list 직렬화(``pairs``)로 재정의."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
)

from ._base import List_editor, List_row


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
