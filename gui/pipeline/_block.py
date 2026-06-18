"""process 시퀀스의 단일 블록 카드.

batch 블록(예: aggregate_hs)은 그 process 파라미터를 직접 편집한다.
frame_batch 블록은 내부 frame process 를 **여러 개 순서대로** 담는 미니 시퀀스다 —
각 step(=frame process)을 추가/삭제/순서변경하고, 프레임마다 그 순서대로 실행된다.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core import config_registry
from core.process import pipeline_registry
from core.process.batch.frame_batch import Base_frame_batch
from gui.config_form import Config_form

WRAPPER_KEY = "frame_batch_process"

# 등록된 process 를 frame / batch 로 분류. config 는 {name}_config 규칙으로 도출.
_PROCESS_KEYS = sorted(pipeline_registry._module_dict)
FRAME_KEYS = [k for k in _PROCESS_KEYS if not issubclass(pipeline_registry.Get(k), Base_frame_batch)]
BATCH_KEYS = [k for k in _PROCESS_KEYS if issubclass(pipeline_registry.Get(k), Base_frame_batch)]


def _config_class(key: str) -> type | None:
    try:
        return config_registry.Get(f"{key}_config")
    except KeyError:
        return None


def _input_keys(key: str) -> list[str]:
    return list(pipeline_registry.Get(key).INPUTS)


def _output_keys(key: str) -> list[str]:
    return list(pipeline_registry.Get(key).OUTPUTS)


def _io_text(in_keys: list[str], out_keys: list[str]) -> str:
    return (f"in: {', '.join(in_keys) or '—'}"
            f"    →    out: {', '.join(out_keys) or '—'}")


def _meta(key: str, params: dict) -> str | dict:
    """config 클래스가 없으면 object_type 문자열만 반환 (Build_process string 경로 활용)."""
    _cls = _config_class(key)
    if _cls is None:
        return key
    _valid = set(_cls.__dataclass_fields__)
    return _cls(**{_k: _v for _k, _v in params.items() if _k in _valid}).Serialize()


def _move_buttons(on_up, on_down, on_remove) -> list[QToolButton]:
    _btns = []
    for _txt, _slot in (("▲", on_up), ("▼", on_down), ("✕", on_remove)):
        _b = QToolButton()
        _b.setText(_txt)
        _b.clicked.connect(_slot)
        _btns.append(_b)
    return _btns


class Frame_step(QGroupBox):
    """frame_batch 내부의 단일 frame process step."""

    changed          = Signal()
    remove_requested = Signal(object)
    move_requested   = Signal(object, int)

    def __init__(self, key: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._form: Config_form | None = None
        self._build(key or (FRAME_KEYS or [""])[0])

    def _build(self, key: str) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(6, 4, 6, 4)
        _lay.setSpacing(2)

        _hdr = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.addItems(FRAME_KEYS)
        self._combo.setCurrentText(key)
        self._combo.currentTextChanged.connect(self._rebuild_form)
        _hdr.addWidget(self._combo, stretch=1)

        for _b in _move_buttons(
            lambda: self.move_requested.emit(self, -1),
            lambda: self.move_requested.emit(self, +1),
            lambda: self.remove_requested.emit(self),
        ):
            _hdr.addWidget(_b)
        _lay.addLayout(_hdr)

        self._io_lbl = QLabel()           # in/out 키: 콤보 아래 별도 줄
        self._io_lbl.setStyleSheet("color: #8aa;")
        _lay.addWidget(self._io_lbl)

        self._form_holder = QWidget()
        self._form_layout = QVBoxLayout(self._form_holder)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        _lay.addWidget(self._form_holder)

        self._rebuild_form()

    def key(self) -> str:
        return self._combo.currentText()

    def _rebuild_form(self) -> None:
        _key = self.key()
        if self._form is not None:
            self._form_layout.removeWidget(self._form)
            self._form.deleteLater()
            self._form = None
        _cls = _config_class(_key)
        if _cls is not None:
            self._form = Config_form(_cls)
            self._form.params_changed.connect(self.changed)
            self._form_layout.addWidget(self._form)
        self._io_lbl.setText(_io_text(_input_keys(_key), _output_keys(_key)))
        self.changed.emit()

    def meta(self) -> str | dict:
        return _meta(self.key(), self._form.get() if self._form else {})

    def load(self, key: str, params: dict) -> None:
        self._combo.setCurrentText(key)
        if self._form is not None:
            self._form.load(params)


class Block(QGroupBox):
    """시퀀스 한 단계를 나타내는 블록 카드."""

    changed          = Signal()
    remove_requested = Signal(object)
    move_requested   = Signal(object, int)

    def __init__(self, key: str, parent=None) -> None:
        super().__init__(parent)
        self.key = key
        self._is_wrapper = (key == WRAPPER_KEY)
        self._steps: list[Frame_step] = []
        self._form: Config_form | None = None
        self._build()

    def _build(self) -> None:
        _icon = "🖼" if self._is_wrapper else "⚙"
        self.setTitle(f"{_icon}  {self.key}")

        _lay = QVBoxLayout(self)
        _lay.setSpacing(4)

        _hdr = QHBoxLayout()
        _hdr.addStretch(1)

        for _b in _move_buttons(
            lambda: self.move_requested.emit(self, -1),
            lambda: self.move_requested.emit(self, +1),
            lambda: self.remove_requested.emit(self),
        ):
            _hdr.addWidget(_b)
        _lay.addLayout(_hdr)

        if not self._is_wrapper:           # in/out 키: 헤더 아래 별도 줄
            _io = QLabel(_io_text(_input_keys(self.key), _output_keys(self.key)))
            _io.setStyleSheet("color: #8aa;")
            _lay.addWidget(_io)

        if self._is_wrapper:
            _cls = _config_class(WRAPPER_KEY)
            if _cls is not None:
                self._form = Config_form(_cls)        # is_flatten 등 batch 파라미터
                self._form.params_changed.connect(self.changed)
                _lay.addWidget(self._form)
            self._steps_layout = QVBoxLayout()
            self._steps_layout.setSpacing(4)
            _lay.addLayout(self._steps_layout)
            _add = QPushButton("+ frame process")
            _add.clicked.connect(lambda: self._add_step())
            _lay.addWidget(_add)
            self._add_step()
        else:
            _cls = _config_class(self.key)
            if _cls is not None:
                self._form = Config_form(_cls)
                self._form.params_changed.connect(self.changed)
                _lay.addWidget(self._form)

    def _add_step(self, key: str | None = None) -> Frame_step:
        _step = Frame_step(key)
        _step.changed.connect(self.changed)
        _step.remove_requested.connect(self._remove_step)
        _step.move_requested.connect(self._move_step)
        self._steps.append(_step)
        self._relayout_steps()
        self.changed.emit()
        return _step

    def _remove_step(self, step: Frame_step) -> None:
        if len(self._steps) <= 1:
            return
        self._steps.remove(step)
        step.setParent(None)
        step.deleteLater()
        self._relayout_steps()
        self.changed.emit()

    def _move_step(self, step: Frame_step, direction: int) -> None:
        _i = self._steps.index(step)
        _j = _i + direction
        if 0 <= _j < len(self._steps):
            self._steps[_i], self._steps[_j] = self._steps[_j], self._steps[_i]
            self._relayout_steps()
            self.changed.emit()

    def _relayout_steps(self) -> None:
        while self._steps_layout.count():
            _item = self._steps_layout.takeAt(0)
            _w = _item.widget()
            if _w is not None:
                _w.setParent(None)
        for _step in self._steps:
            self._steps_layout.addWidget(_step)

    def to_config(self) -> str | dict:
        if self._is_wrapper:
            _cls = _config_class(WRAPPER_KEY)
            assert _cls is not None
            _valid  = set(_cls.__dataclass_fields__)
            _params = {
                _k: _v for _k, _v in (self._form.get() if self._form else {}).items()
                if _k in _valid and _k != "processes"
            }
            return _cls(
                processes=[_s.meta() for _s in self._steps], **_params
            ).Serialize()
        return _meta(self.key, self._form.get() if self._form else {})
