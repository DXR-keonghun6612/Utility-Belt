"""Shared low-level widgets: image label, slider rows, divider."""

from __future__ import annotations

import cv2
import numpy as np

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# numpy → QPixmap helpers
# ---------------------------------------------------------------------------

def _bgr_to_pixmap(img_bgr: np.ndarray) -> QPixmap:
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = img_rgb.shape
    q_img = QImage(img_rgb.data.tobytes(), w, h, w * ch, QImage.Format_RGB888)
    return QPixmap.fromImage(q_img)


def _gray_to_pixmap(mask: np.ndarray) -> QPixmap:
    return _bgr_to_pixmap(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR))


# ---------------------------------------------------------------------------
# Horizontal divider
# ---------------------------------------------------------------------------

def _hline() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet("background: #3a3a3a;")
    return w


# ---------------------------------------------------------------------------
# Auto-scaling + zoomable image label
# ---------------------------------------------------------------------------

class _ImageLabel(QWidget):
    """Zoomable image view backed by a QScrollArea.

    zoom=None (default): fit-to-viewport, auto-rescales on window resize.
    zoom=float: absolute scale relative to the source pixmap's pixel size.
                Mouse-wheel zooms centered on the cursor position.
    """

    zoom_changed = Signal(float)  # emits effective scale; 0.0 signals "fit" mode

    _STEP = 1.15
    _ZOOM_MIN = 0.05
    _ZOOM_MAX = 8.0

    def __init__(self, placeholder: str = "이미지 없음", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._src: QPixmap | None = None
        self._zoom: float | None = None  # None = fit-to-viewport

        self._inner = QLabel(placeholder)
        self._inner.setAlignment(Qt.AlignCenter)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._inner)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setStyleSheet("background: #1a1a1a; border: 1px solid #333;")
        self._scroll.viewport().installEventFilter(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._scroll)

        self.setMinimumSize(160, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # -- public API --------------------------------------------------------

    def set_image(self, img_bgr: np.ndarray) -> None:
        self._src = _bgr_to_pixmap(img_bgr)
        self._render()

    def set_pixmap_source(self, pix: QPixmap) -> None:
        self._src = pix
        self._render()

    def set_mask(self, mask: np.ndarray) -> None:
        self.set_pixmap_source(_gray_to_pixmap(mask))

    def clear_image(self, msg: str = "이미지 없음") -> None:
        self._src = None
        self._inner.clear()
        self._inner.setText(msg)

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(self._ZOOM_MIN, min(self._ZOOM_MAX, zoom))
        self._render()
        self.zoom_changed.emit(self._zoom)

    def reset_zoom(self) -> None:
        self._zoom = None
        self._render()
        self.zoom_changed.emit(0.0)

    def effective_zoom(self) -> float:
        return self._fit_scale() if self._zoom is None else self._zoom

    # -- internals ---------------------------------------------------------

    def _fit_scale(self) -> float:
        if self._src is None:
            return 1.0
        vw = max(1, self._scroll.viewport().width())
        vh = max(1, self._scroll.viewport().height())
        return min(vw / self._src.width(), vh / self._src.height())

    def _render(self) -> None:
        if self._src is None:
            return
        scale = self.effective_zoom()
        w = max(1, int(self._src.width() * scale))
        h = max(1, int(self._src.height() * scale))
        self._inner.setPixmap(
            self._src.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self._inner.resize(w, h)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._zoom is None:
            self._render()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self._scroll.viewport() and event.type() == QEvent.Type.Wheel:
            delta = event.angleDelta().y()
            factor = self._STEP if delta > 0 else 1.0 / self._STEP
            old = self.effective_zoom()
            new = max(self._ZOOM_MIN, min(self._ZOOM_MAX, old * factor))

            mouse = event.position().toPoint()
            hbar = self._scroll.horizontalScrollBar()
            vbar = self._scroll.verticalScrollBar()

            self._zoom = new
            self._render()
            self.zoom_changed.emit(new)

            # keep the pixel under the cursor stationary while zooming
            ratio = new / old
            hbar.setValue(int((hbar.value() + mouse.x()) * ratio - mouse.x()))
            vbar.setValue(int((vbar.value() + mouse.y()) * ratio - mouse.y()))
            return True
        return super().eventFilter(obj, event)


# ---------------------------------------------------------------------------
# Slider rows
# ---------------------------------------------------------------------------

class _FloatSliderRow(QWidget):
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
        v = round(self._min + idx * self._step, 8)
        self._spin.blockSignals(True)
        self._spin.setValue(v)
        self._spin.blockSignals(False)
        self.value_changed.emit(v)

    def _on_spin(self, v: float) -> None:
        idx = round((v - self._min) / self._step)
        self._slider.blockSignals(True)
        self._slider.setValue(idx)
        self._slider.blockSignals(False)
        self.value_changed.emit(v)

    def value(self) -> float:
        return self._spin.value()


class _IntSliderRow(QWidget):
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
        return self._spin.value()
