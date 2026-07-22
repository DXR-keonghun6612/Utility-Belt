"""attr 뷰어 — 인라인 값. **개념 → 없으면 파이썬 타입**이 위젯을 가른다.

LEAF format 은 `(개념, 파이썬 타입)` 이다(core `schema.Build`). 위젯도 같은 순서로 고른다: 개념이 있으면
그 개념 전용 위젯(`bbox` → 스핀 4개), 없으면 파이썬 타입대로(`int`·`float` → 스핀, `str`·`list` →
콤보/한 줄 입력).

예전엔 class_id·obj_id·bbox 가 객체 폼에 **하드코딩**돼 있었고(`_Ann_edit_form`), 그 다음엔 `("attr","xyxy")`
처럼 **타입 자리에 타입이 아닌 것**이 적혀 있었다. 이제 데이터모델이 스스로 말하므로 새 개념이 생겨도
여기 분기 하나만 늘고 **핸들러는 안 는다** — port 는 등록 안 된 개념을 전부 인라인으로 흘려보낸다.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.schema import Data_Ref

from ._base import Node_viewer, Register

#: 개념 없는 인라인 값의 등록 key — format 첫 칸이 비어 있다 (``("", "str")``).
PLAIN = ""
#: region 도메인 — bbox 는 ``("region", "bbox", style)`` 이라 **개념이 format[1]** 에 있다(도메인이 [0]).
#: 옛 ``("bbox", "list")``(개념이 [0])도 아직 받는다 — 판정은 [0]·[1] 둘 다 본다.
BBOX = "bbox"
REGION = "region"


def _python_type(ref: Data_Ref) -> str:
    return ref.format[1] if len(ref.format) > 1 else ""


class _Bbox_row(QWidget):
    """``bbox`` 개념 — 스핀 4개로 편집한다 (캔버스 드래그와 양방향)."""

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


class _Number_row(QWidget):
    """``int``/``float`` — **타입 그대로** 돌려주는 스핀 (문자열로 돌려주면 저장 때 타입이 갈린다)."""

    def __init__(self, value, type: str, on_change, parent=None) -> None:
        super().__init__(parent)
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _sp = QSpinBox() if type == "int" else QDoubleSpinBox()
        _sp.setRange(-10 ** 9, 10 ** 9)
        if isinstance(_sp, QDoubleSpinBox):
            _sp.setDecimals(4)
        _sp.setValue((int if type == "int" else float)(value or 0))
        if on_change is not None:
            _sp.valueChanged.connect(on_change)
        _lay.addWidget(_sp)


@Register(PLAIN, BBOX, REGION)
class Attr_viewer(Node_viewer):
    """인라인 값 — 개념(``bbox``) → 없으면 파이썬 타입으로 위젯을 고른다."""

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        return "" if value is None else str(value)

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx: dict | None = None,
              on_change=None) -> QWidget | None:
        """개념 → 파이썬 타입 순으로 위젯을 고른다.

        **편집한 값은 그 타입 그대로 돌려준다** — ``int`` 를 문자열로 돌려주면 다음 저장에서 detail 이
        ``str`` 이 된다(값이 곧 타입이므로). 타입이 조용히 갈리는 자리다.

        ``ctx["candidates"]`` 가 있으면 **자유 입력 가능한 콤보**가 된다. **어느 노드에 후보를 줄지는
        호출 측이 정한다** — 뷰어는 "후보가 있으면 고르게 한다"만 안다(class_id 를 여기서 알면 도메인
        지식이 뷰어로 샌다).
        """
        if ref.format[:1] == (BBOX,) or ref.format[1:2] == (BBOX,):   # 옛 [bbox,…] · 새 [region,bbox,…]
            return _Bbox_row(value, on_change)

        _type = _python_type(ref)
        if _type in ("int", "float"):
            return _Number_row(value, _type, on_change)

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
