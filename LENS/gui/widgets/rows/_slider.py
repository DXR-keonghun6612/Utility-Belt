"""슬라이더 ↔ 스핀박스를 동기화한 실수/정수 입력 행."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
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
