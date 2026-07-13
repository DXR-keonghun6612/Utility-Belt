"""슬라이더 ↔ 스핀박스를 동기화한 실수/정수 입력 행 + **스냅 슬라이더**(툴바용 좁은 행).

`*_slider_row` 는 폼용(라벨이 넓다)이고, `Snap_slider_row` 는 툴바에 얹을 만큼 좁으면서 **기준값에
달라붙는다** — 밝기의 0 처럼 "원래대로"가 있는 값은 손으로 되찾기 어렵다(±1 을 못 맞춘다).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QStyle,
    QStyleOptionSlider,
    QWidget,
)


class Float_slider_row(QWidget):
    """슬라이더와 스핀박스를 동기화한 실수 입력 행.

    Attributes:
        value_changed: 값이 바뀔 때 새 실수값을 emit하는 시그널.
    """

    value_changed = Signal(float)

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        default: float,
        step: float = 0.05,
        decimals: int = 2,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """행을 구성한다.

        Args:
            label: 좌측 라벨 텍스트.
            min_val: 최솟값.
            max_val: 최댓값.
            default: 초기값.
            step: 슬라이더 한 칸 / 스핀박스 증감 단위.
            decimals: 스핀박스 소수 자릿수.
            tooltip: 위젯 툴팁.
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._step = step
        self._min = min_val
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label)
        lbl.setFixedWidth(240)
        if tooltip:
            self.setToolTip(tooltip)
        layout.addWidget(lbl)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(round((max_val - min_val) / step))
        self._slider.setValue(round((default - min_val) / step))
        layout.addWidget(self._slider, stretch=1)

        self._spin = QDoubleSpinBox()
        self._spin.setRange(min_val, max_val)
        self._spin.setSingleStep(step)
        self._spin.setDecimals(decimals)
        self._spin.setValue(default)
        self._spin.setFixedWidth(80)
        layout.addWidget(self._spin)

        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)

    def _on_slider(self, idx: int) -> None:
        """슬라이더 변화를 스핀박스에 반영하고 시그널을 emit한다."""
        v = round(self._min + idx * self._step, 8)
        self._spin.blockSignals(True)
        self._spin.setValue(v)
        self._spin.blockSignals(False)
        self.value_changed.emit(v)

    def _on_spin(self, v: float) -> None:
        """스핀박스 변화를 슬라이더에 반영하고 시그널을 emit한다."""
        idx = round((v - self._min) / self._step)
        self._slider.blockSignals(True)
        self._slider.setValue(idx)
        self._slider.blockSignals(False)
        self.value_changed.emit(v)

    def value(self) -> float:
        """현재 값을 반환한다."""
        return self._spin.value()

    def set_value(self, v: float) -> None:
        """값을 설정한다 — **시그널 없이**(복원용). 슬라이더·스핀을 함께 맞춘다.

        폼 복원처럼 "값을 되돌리는" 자리에서 쓴다. 사용자의 편집과 구별되어야 하므로
        ``value_changed`` 를 emit 하지 않는다.
        """
        self._spin.blockSignals(True)
        self._slider.blockSignals(True)
        self._spin.setValue(float(v))
        self._slider.setValue(round((float(v) - self._min) / self._step))
        self._spin.blockSignals(False)
        self._slider.blockSignals(False)


class _Snap_slider(QSlider):
    """스냅 지점에 **달라붙는** 슬라이더 — 그 값 근처로 끌면 정확히 그 값에 서고, 눈금으로 보인다.

    붙는 폭은 범위에 비례한다(3%) — 범위가 -100~100 이든 0~1000 이든 손끝 감각이 같아야 한다.

    Args:
        snaps: 달라붙을 값들. 범위 밖 값은 무시된다.
    """

    _SNAP_RATIO = 0.03

    def __init__(self, snaps: list[int], parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._snaps = list(snaps)
        self._snapping = False
        self.valueChanged.connect(self._snap)

    def _tolerance(self) -> int:
        return max(1, round((self.maximum() - self.minimum()) * self._SNAP_RATIO))

    def _snap(self, value: int) -> None:
        """스냅 지점 근처면 그 값으로 당긴다 (재진입 방지 — setValue 가 다시 이 슬롯을 부른다)."""
        if self._snapping or not self._snaps:
            return
        _near = min(self._snaps, key=lambda _s: abs(_s - value))
        if _near != value and abs(_near - value) <= self._tolerance():
            self._snapping = True
            self.setValue(_near)
            self._snapping = False

    def paintEvent(self, event) -> None:  # noqa: N802
        """기본 슬라이더 위에 스냅 지점 눈금을 그린다 — 어디에 붙는지 보이지 않으면 없는 것과 같다."""
        super().paintEvent(event)
        if not self._snaps:
            return
        _opt = QStyleOptionSlider()
        self.initStyleOption(_opt)
        _groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, _opt, QStyle.SubControl.SC_SliderGroove, self)
        _handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, _opt, QStyle.SubControl.SC_SliderHandle, self)
        _span = _groove.width() - _handle.width()

        _painter = QPainter(self)
        _painter.setPen(QPen(self.palette().mid().color(), 1))
        for _s in self._snaps:
            if not self.minimum() <= _s <= self.maximum():
                continue
            _x = _groove.left() + _handle.width() / 2 + QStyle.sliderPositionFromValue(
                self.minimum(), self.maximum(), _s, _span)
            _painter.drawLine(int(_x), _groove.top(), int(_x), _groove.top() + 3)


class Snap_slider_row(QWidget):
    """툴바용 좁은 슬라이더 — 라벨 + 스냅 슬라이더 + 현재값.

    보면서 끌어 맞추는 값에 쓴다(밝기 등). **기준값이 있는 값은 그 지점에 달라붙어야 한다** — 밝기 0
    처럼 "원래대로"가 있는 값은 손으로 되찾기 어렵기 때문이다.

    Attributes:
        value_changed: 값이 바뀔 때 새 정수값을 emit.
    """

    value_changed = Signal(int)

    def __init__(self, label: str, min_val: int, max_val: int, default: int,
                 snaps: list[int] | None = None, tooltip: str = "", width: int = 110,
                 parent: QWidget | None = None) -> None:
        """행을 구성한다.

        Args:
            label: 좌측 라벨.
            min_val: 최솟값.
            max_val: 최댓값.
            default: 초기값.
            snaps: 달라붙을 값들 (예: 밝기의 ``[0]``, 배율의 ``[0, 100, 200]``).
            tooltip: 위젯 툴팁.
            width: 슬라이더 폭(px) — 툴바에 얹으므로 좁게.
            parent: 부모 위젯.
        """
        super().__init__(parent)
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)
        _lay.addWidget(QLabel(label))

        self._slider = _Snap_slider(snaps or [])
        self._slider.setRange(min_val, max_val)
        self._slider.setValue(default)
        self._slider.setFixedWidth(width)
        _lay.addWidget(self._slider)

        self._read = QLabel(str(default))
        self._read.setFixedWidth(30)
        self._read.setStyleSheet("color: #888;")
        _lay.addWidget(self._read)

        if tooltip:
            self.setToolTip(tooltip)
        self._slider.valueChanged.connect(lambda _v: self._read.setText(str(_v)))
        self._slider.valueChanged.connect(self.value_changed)

    def value(self) -> int:
        """현재 값."""
        return self._slider.value()

    def set_value(self, v: int) -> None:
        """값을 설정한다 (스냅은 그대로 적용된다)."""
        self._slider.setValue(int(v))


class Int_slider_row(QWidget):
    """슬라이더와 스핀박스를 동기화한 정수 입력 행.

    Attributes:
        value_changed: 값이 바뀔 때 새 정수값을 emit하는 시그널.
    """

    value_changed = Signal(int)

    def __init__(
        self,
        label: str,
        min_val: int,
        max_val: int,
        default: int,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """행을 구성한다.

        Args:
            label: 좌측 라벨 텍스트.
            min_val: 최솟값.
            max_val: 최댓값.
            default: 초기값.
            tooltip: 위젯 툴팁.
            parent: 부모 위젯.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label)
        lbl.setFixedWidth(240)
        if tooltip:
            self.setToolTip(tooltip)
        layout.addWidget(lbl)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(min_val, max_val)
        self._slider.setValue(default)
        layout.addWidget(self._slider, stretch=1)

        self._spin = QSpinBox()
        self._spin.setRange(min_val, max_val)
        self._spin.setValue(default)
        self._spin.setFixedWidth(80)
        layout.addWidget(self._spin)

        self._slider.valueChanged.connect(self._spin.setValue)
        self._spin.valueChanged.connect(self._slider.setValue)
        self._slider.valueChanged.connect(self.value_changed)

    def value(self) -> int:
        """현재 값을 반환한다."""
        return self._spin.value()

    def set_value(self, v: int) -> None:
        """값을 설정한다 — **시그널 없이**(복원용). 슬라이더·스핀을 함께 맞춘다."""
        self._spin.blockSignals(True)
        self._slider.blockSignals(True)
        self._spin.setValue(int(v))
        self._slider.setValue(int(v))
        self._spin.blockSignals(False)
        self._slider.blockSignals(False)
