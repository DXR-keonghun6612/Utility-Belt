"""attr 뷰어 — 인라인 값. **detail 이 위젯을 가른다** (`str` → 콤보/입력, `xyxy` → 스핀 4개).

예전엔 class_id·obj_id·bbox 가 객체 폼에 **하드코딩**돼 있었다(`_Ann_edit_form`). 그런데 그것들은
특별한 종류가 아니라 그냥 `("attr", …)` LEAF 다 — 데이터모델이 그렇게 말한다. 여기서 detail 로 갈라주면
새 attr(예: `("attr","float")`)이 생겨도 UI 를 손댈 필요가 없다.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.schema import Data_Ref

from ._base import Node_viewer, Register


def _detail(ref: Data_Ref) -> str:
    return ref.format[1] if len(ref.format) > 1 else ""


class _Bbox_row(QWidget):
    """``xyxy`` 값을 스핀 4개로 편집한다 (그림 편집과 양방향)."""

    def __init__(self, value, on_change, parent=None) -> None:
        super().__init__(parent)
        self._on_change = on_change
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        self._spins: list[QSpinBox] = []
        _vals = list(value or [0, 0, 0, 0])
        for _i, _label in enumerate(("x0", "y0", "x1", "y1")):
            _sp = QSpinBox()
            _sp.setRange(0, 100000)
            _sp.setPrefix(f"{_label} ")
            _sp.setValue(int(_vals[_i]) if _i < len(_vals) else 0)
            _sp.valueChanged.connect(self._emit)
            self._spins.append(_sp)
            _lay.addWidget(_sp)

    def _emit(self) -> None:
        if self._on_change is not None:
            self._on_change([_s.value() for _s in self._spins])

    def set_value(self, value) -> None:
        """그림으로 그린 bbox 를 스핀에 반영한다 (시그널 없이)."""
        for _sp, _v in zip(self._spins, value):
            _sp.blockSignals(True)
            _sp.setValue(int(_v))
            _sp.blockSignals(False)


@Register("attr")
class Attr_viewer(Node_viewer):
    """인라인 값 — detail 로 위젯을 고른다."""

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        return "" if value is None else str(value)

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx: dict | None = None,
              on_change=None) -> QWidget | None:
        """detail 로 위젯을 고른다 — ``xyxy`` = 스핀 4개, 그 외 = 한 줄 입력.

        ``ctx["candidates"]`` 가 있으면 **자유 입력 가능한 콤보**가 된다. **어느 노드에 후보를 줄지는
        호출 측이 정한다** — 뷰어는 "후보가 있으면 고르게 한다"만 안다(class_id 를 여기서 알면 도메인
        지식이 뷰어로 샌다).
        """
        if _detail(ref) == "xyxy":
            return _Bbox_row(value, on_change)

        _cands = (ctx or {}).get("candidates")
        _w = QWidget()
        _lay = QVBoxLayout(_w)
        _lay.setContentsMargins(0, 0, 0, 0)
        if _cands:
            _edit = QComboBox()
            _edit.setEditable(True)
            _edit.addItems(sorted(set(_cands) | {str(value or "")}))
            _edit.setCurrentText(str(value or ""))
            if on_change is not None:
                _edit.currentTextChanged.connect(on_change)
        else:
            _edit = QLineEdit(str(value or ""))
            if on_change is not None:
                _edit.textChanged.connect(on_change)
        _lay.addWidget(_edit)
        return _w
