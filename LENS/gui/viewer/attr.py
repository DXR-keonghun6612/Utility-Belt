"""attr 뷰어 — 인라인 값. **개념 → 없으면 파이썬 타입**이 위젯을 가른다.

LEAF format 은 `(개념, 파이썬 타입)` 이다(core `schema.Build`). 위젯도 같은 순서로 고른다: 개념이 있으면
그 개념 전용 위젯(`bbox` → 스핀 4개, `pose` → **평면으로 자른** x·y·θ 셋), 없으면 파이썬 타입대로
(`int`·`float` → 스핀, `str`·`list` → 콤보/한 줄 입력).

**개념 위젯은 저장 표현을 자를 수 있다** — `pose` 정본은 7개(xyz + quaternion)지만 화면은 이미지 한
장이라 만질 자유도가 셋뿐이다. 자르는 규약은 [`core/format/pose`](../../core/format/pose.py) 가 소유하고
여기는 읽고 쓰기만 한다 — 자를 수 없는 값(화면 안팎으로 기운 자세)은 **7개 그대로 드러낸다**.

예전엔 class_id·obj_id·bbox 가 객체 폼에 **하드코딩**돼 있었고(`_Ann_edit_form`), 그 다음엔 `("attr","xyxy")`
처럼 **타입 자리에 타입이 아닌 것**이 적혀 있었다. 이제 데이터모델이 스스로 말하므로 새 개념이 생겨도
여기 분기 하나만 늘고 **핸들러는 안 는다** — port 는 등록 안 된 개념을 전부 인라인으로 흘려보낸다.
"""
from __future__ import annotations

import math
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

from core.format import pose
from core.schema import Data_Ref

from ._base import Node_viewer, Register

#: 개념 없는 인라인 값의 등록 key — format 첫 칸이 비어 있다 (``("", "str")``).
PLAIN = ""
#: region 도메인 — bbox 는 ``("region", "bbox", style)`` 이라 **개념이 format[1]** 에 있다(도메인이 [0]).
#: 옛 ``("bbox", "list")``(개념이 [0])도 아직 받는다 — 판정은 [0]·[1] 둘 다 본다.
BBOX = "bbox"
REGION = "region"
#: 자세 — ``("pose", "list")``. 파일 I/O 가 없어 port 도메인이 없고, 개념이 첫 칸이다.
POSE = "pose"


def _python_type(ref: Data_Ref) -> str:
    return ref.format[1] if len(ref.format) > 1 else ""


def _to_planar(value) -> tuple[float, float, float] | None:
    """저장된 자세 → 평면 ``(x, y, rad)``. 평면 밖이거나 7개가 아니면 None.

    **자를 수 없는 값을 메우지 않는다** — None 이면 호출 측이 7개를 그대로 드러낸다(자유 입력).
    """
    try:
        return pose.To_2d(value)
    except (TypeError, ValueError):
        return None


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


class _Pose_row(QWidget):
    """``pose`` 개념 — **평면으로 잘라** x·y·θ 세 칸으로 편집한다 (정본은 7개: xyz + quaternion).

    정본을 3D 로 드는 이유는 [`core/format/pose`](../../core/format/pose.py) 가 말한다. 화면은 이미지
    한 장이라 사람이 만질 수 있는 자유도가 셋뿐이므로 여기서 자른다 — 자르는 규약(``z=0``, z축 회전,
    양수 = 시계방향)은 그 모듈이 소유하고 이 위젯은 **읽고 쓰기만** 한다.

    각은 **도(°)** 로 보인다 — 라디안은 사람이 못 읽는다. 저장은 rad 다.
    """

    def __init__(self, planar: tuple[float, float, float], on_change, parent=None) -> None:
        super().__init__(parent)
        self._on_change = on_change
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        self._spins: list[QDoubleSpinBox] = []
        for _label, _value, _rng, _dec in (
                ("x", planar[0], (-10 ** 6, 10 ** 6), 1),
                ("y", planar[1], (-10 ** 6, 10 ** 6), 1),
                ("θ", math.degrees(planar[2]), (-180.0, 180.0), 2)):
            _sp = QDoubleSpinBox()
            _sp.setRange(*_rng)
            _sp.setDecimals(_dec)
            _sp.setPrefix(f"{_label} ")
            _sp.setValue(_value)
            _sp.valueChanged.connect(self._emit)
            self._spins.append(_sp)
            _lay.addWidget(_sp)
        self._spins[2].setSuffix("°")
        self._spins[2].setWrapping(True)          # ±180° 가 이어져 있다 (각은 순환한다)

    def _emit(self) -> None:
        """세 칸 → 7개 정본. **자르기의 역이 곧 저장**이라 왕복이 닫힌다."""
        if self._on_change is not None:
            _x, _y, _deg = (_s.value() for _s in self._spins)
            self._on_change(pose.From_2d((_x, _y), math.radians(_deg)))


class _Choice_row(QWidget):
    """후보가 있는 값 — **보여주는 이름과 저장하는 값이 다르다** (``{표시 이름: 저장 값}``).

    자유 입력을 막는다: 후보 밖 값을 손으로 적을 수 있으면 오타 하나가 곧 어디에도 안 걸리는 라벨이
    된다(class 를 이름 문자열로 저장하던 시절 실제로 라벨 19만 건이 id_map 과 끊겼다).

    후보에 없는 값이 이미 저장돼 있으면 **그 항목을 그대로 드러낸다** — 조용히 첫 후보로 바꾸면
    사용자가 모르는 사이 라벨이 갈린다.
    """

    def __init__(self, value, choices: dict, on_change, parent=None) -> None:
        super().__init__(parent)
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        for _label, _val in sorted(choices.items(), key=lambda _kv: (_kv[1], _kv[0])):
            self._combo.addItem(str(_label), _val)
        # **문자열로 견준다** — 같은 class_id 가 저장 경로에 따라 int(flow) 또는 str(GUI, ``Set_attr``)
        # 로 들어 있다. 타입으로 찾으면 한쪽이 늘 "후보에 없음" 으로 떨어져 이름이 안 보인다.
        _at = next((_i for _i in range(self._combo.count())
                    if str(self._combo.itemData(_i)) == str(value)), -1)
        if value is None:
            _at = -1
        if _at < 0:                                   # 후보 밖 (또는 값 없음) — 만들어서 보여준다
            self._combo.addItem("(없음)" if value is None else f"{value} — 후보에 없음", value)
            _at = self._combo.count() - 1
        self._combo.setCurrentIndex(_at)
        if on_change is not None:
            self._combo.currentIndexChanged.connect(
                lambda _i: on_change(self._combo.itemData(_i)))
        _lay.addWidget(self._combo)


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


@Register(PLAIN, BBOX, REGION, POSE)
class Attr_viewer(Node_viewer):
    """인라인 값 — 개념(``bbox``·``pose``) → 없으면 파이썬 타입으로 위젯을 고른다."""

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        """트리 한 줄 — ``pose`` 만 **평면으로 줄여** 보인다(7개 숫자는 줄에서 안 읽힌다)."""
        if value is None:
            return ""
        if ref.format[:1] == (POSE,) and (_planar := _to_planar(value)) is not None:
            _x, _y, _rad = _planar
            return f"({_x:.0f}, {_y:.0f}) {math.degrees(_rad):.1f}°"
        return str(value)

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx: dict | None = None,
              on_change=None) -> QWidget | None:
        """개념 → 파이썬 타입 순으로 위젯을 고른다.

        **편집한 값은 그 타입 그대로 돌려준다** — ``int`` 를 문자열로 돌려주면 다음 저장에서 detail 이
        ``str`` 이 된다(값이 곧 타입이므로). 타입이 조용히 갈리는 자리다.

        ``ctx["candidates"]`` (``{표시 이름: 저장 값}``)가 있으면 **고르는 값**이라 파이썬 타입보다
        먼저 본다 — 후보가 있는 값에 스핀·자유 입력을 주면 후보 밖 값을 만들 수 있다. **어느 노드에
        후보를 줄지는 호출 측이 정한다** — 뷰어는 "후보가 있으면 고르게 한다"만 안다(class_id 를 여기서
        알면 도메인 지식이 뷰어로 샌다).
        """
        if ref.format[:1] == (BBOX,) or ref.format[1:2] == (BBOX,):   # 옛 [bbox,…] · 새 [region,bbox,…]
            return _Bbox_row(value, on_change)

        if ref.format[:1] == (POSE,):
            # 평면으로 못 줄이는 자세(화면 안팎으로 기운 것)는 **7개 그대로 드러낸다** — 아래 자유
            # 입력으로 떨어진다. 억지로 투영하면 기울기가 조용히 사라진다.
            if (_planar := _to_planar(value)) is not None:
                return _Pose_row(_planar, on_change)

        if _cands := (ctx or {}).get("candidates"):
            return _Choice_row(value, _cands, on_change)

        _type = _python_type(ref)
        if _type in ("int", "float"):
            return _Number_row(value, _type, on_change)

        _w = QWidget()
        _lay = QVBoxLayout(_w)
        _lay.setContentsMargins(0, 0, 0, 0)
        _edit = QLineEdit(str(value or ""))
        if on_change is not None:
            _edit.textChanged.connect(on_change)
        _lay.addWidget(_edit)
        return _w
