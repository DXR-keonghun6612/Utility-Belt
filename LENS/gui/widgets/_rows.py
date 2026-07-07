"""라벨 + 입력을 한 줄로 묶은 재사용 입력 행 — 경로 행 · 실수/정수 슬라이더 행."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QToolButton,
    QWidget,
)


class Path_row(QWidget):
    """라벨 + 경로 입력 + 탐색(📁) 버튼을 한 줄로 묶은 재사용 위젯.

    ``mode`` 에 따라 디렉터리(``'dir'``) 또는 파일(``'file'``) 선택 다이얼로그를 띄운다.
    ``refresh`` 가 True면 ↺ 버튼이 추가된다. 경로 확정(편집 완료·탐색·새로고침)마다
    ``committed`` 를 emit한다.

    Attributes:
        committed: 경로가 확정될 때 emit하는 시그널.
    """

    committed = Signal()

    def __init__(
        self,
        label: str,
        placeholder: str = "",
        mode: str = "dir",
        refresh: bool = False,
        file_filter: str = "",
        read_only: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """행을 구성한다.

        Args:
            label: 좌측 라벨 텍스트.
            placeholder: 입력칸 placeholder.
            mode: ``'dir'`` 이면 디렉터리, ``'file'`` 이면 파일 선택.
            refresh: True면 ↺ 새로고침 버튼을 추가한다.
            file_filter: ``mode == 'file'`` 일 때 다이얼로그 필터 (예: ``"YAML (*.yaml *.yml)"``).
            read_only: True면 뷰어로만 동작한다 — 직접 편집·탐색(📁) 불가, 값은
                ``setText`` 로만 바뀐다 (refresh 버튼은 그대로 ``committed`` 를 emit).
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._mode = mode
        self._filter = file_filter

        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.addWidget(QLabel(label))

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        if read_only:
            self._edit.setReadOnly(True)
        else:
            self._edit.editingFinished.connect(self.committed)
        _lay.addWidget(self._edit, stretch=1)

        if not read_only:
            _browse = QToolButton()
            _browse.setText("📁")
            _browse.setToolTip("디렉터리 선택" if mode == "dir" else "파일 선택")
            _browse.clicked.connect(self._browse)
            _lay.addWidget(_browse)

        if refresh:
            _refresh = QToolButton()
            _refresh.setText("↺")
            _refresh.setToolTip("새로고침")
            _refresh.clicked.connect(self.committed)
            _lay.addWidget(_refresh)

    def _browse(self) -> None:
        if self._mode == "file":
            _p, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", self._filter)
        else:
            _p = QFileDialog.getExistingDirectory(self, "디렉터리 선택")
        if _p:
            self._edit.setText(_p)
            self.committed.emit()

    def text(self) -> str:
        """현재 입력된 경로 문자열을 반환한다."""
        return self._edit.text()

    def setText(self, value: str) -> None:  # noqa: N802 — QLineEdit API 관례 유지
        """경로 문자열을 설정한다 (시그널은 발생시키지 않음).

        Args:
            value: 설정할 경로 문자열.
        """
        self._edit.setText(value)


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
