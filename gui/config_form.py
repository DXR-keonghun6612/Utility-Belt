"""Config dataclass → UI 자동 생성.

dataclass 필드의 metadata["ui"] 를 읽어 슬라이더·체크박스를 만든다. 블록 파라미터
편집 등 어디서나 재사용한다. config_type/object_type 은 표시하지 않는다.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from typing import Any, Union

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import _FloatSliderRow, _IntSliderRow


_SKIP = frozenset({"config_type", "object_type"})


class _ListEdit(QLineEdit):
    """쉼표 구분 문자열로 list[str] 를 편집하는 line edit."""


class _PairListEdit(QLineEdit):
    """쉼표 구분 'a:b' 문자열로 list[tuple[str, str]] 를 편집하는 line edit."""


def _list_str_inner(tp) -> bool:
    """list[str] 감지."""
    return typing.get_origin(tp) is list and typing.get_args(tp) == (str,)


def _list_pair_inner(tp) -> bool:
    """list[tuple[str, str]] 감지."""
    return (
        typing.get_origin(tp) is list
        and typing.get_args(tp) == (tuple[str, str],)
    )


def _optional_float_inner(tp) -> bool:
    """float | None 또는 Optional[float] 감지."""
    origin = typing.get_origin(tp)
    is_union = origin is Union or (
        hasattr(types, "UnionType") and isinstance(tp, types.UnionType)
    )
    if not is_union:
        return False
    args = typing.get_args(tp)
    return set(args) == {float, type(None)}


class Config_form(QWidget):
    """dataclass config 클래스를 읽어 슬라이더·체크박스 UI를 자동 생성한다.

    필드 metadata["ui"] 키:
        label / tip / min / max / step / decimals / group / controls_group.
    """

    params_changed = Signal()

    def __init__(self, cfg_cls: type, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cfg_cls = cfg_cls
        self._widgets: dict[str, Any] = {}        # name → widget or (cb, slider)
        self._group_boxes: dict[str, QGroupBox] = {}
        self._build()

    # ── build ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            hints = typing.get_type_hints(self._cfg_cls)
        except Exception:
            hints = {}

        fields = [f for f in dataclasses.fields(self._cfg_cls) if f.name not in _SKIP]

        groups: dict[str | None, list[dataclasses.Field]] = {}
        for f in fields:
            g = f.metadata.get("ui", {}).get("group")
            groups.setdefault(g, []).append(f)

        for f in groups.pop(None, []):
            w = self._make_widget(f, hints)
            if w is not None:
                layout.addWidget(w)

        for group_name, gfields in groups.items():
            box = QGroupBox(group_name)
            bl = QVBoxLayout(box)
            for f in gfields:
                w = self._make_widget(f, hints)
                if w is not None:
                    bl.addWidget(w)
            layout.addWidget(box)
            self._group_boxes[group_name] = box

        for fname, w in self._widgets.items():
            if not isinstance(w, QCheckBox):
                continue
            for f in dataclasses.fields(self._cfg_cls):
                if f.name != fname:
                    continue
                cg = f.metadata.get("ui", {}).get("controls_group")
                if cg and cg in self._group_boxes:
                    box = self._group_boxes[cg]
                    box.setVisible(w.isChecked())
                    w.toggled.connect(box.setVisible)

    def _make_widget(self, f: dataclasses.Field, hints: dict) -> QWidget | None:
        ui       = f.metadata.get("ui", {})
        label    = ui.get("label", f.name.replace("_", " "))
        tip      = ui.get("tip", "")
        min_v    = ui.get("min", 0)
        max_v    = ui.get("max", 100)
        step     = ui.get("step", 0.05)
        decimals = ui.get("decimals", 2)

        if f.default is not dataclasses.MISSING:
            default = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            default = f.default_factory()
        else:
            default = None

        tp = hints.get(f.name)
        if tp is None:
            return None

        if _optional_float_inner(tp):
            wrapper = QWidget()
            wl = QVBoxLayout(wrapper)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(2)

            cb = QCheckBox(label)
            if tip:
                cb.setToolTip(tip)
            cb.setChecked(default is not None)
            wl.addWidget(cb)

            slider = _FloatSliderRow(
                f"  ↳ {label}",
                min_v, max_v,
                float(default) if default is not None else (min_v + max_v) / 2,
                step=step, decimals=decimals, tooltip=tip,
            )
            slider.setEnabled(default is not None)
            cb.toggled.connect(slider.setEnabled)
            cb.toggled.connect(lambda _: self.params_changed.emit())
            slider.value_changed.connect(lambda _: self.params_changed.emit())
            wl.addWidget(slider)

            self._widgets[f.name] = (cb, slider)
            return wrapper

        if tp is bool:
            cb = QCheckBox(label)
            if tip:
                cb.setToolTip(tip)
            cb.setChecked(bool(default))
            cb.toggled.connect(lambda _: self.params_changed.emit())
            self._widgets[f.name] = cb
            return cb

        if tp is int:
            w = _IntSliderRow(label, min_v, max_v, int(default or 0), tooltip=tip)
            w.value_changed.connect(lambda _: self.params_changed.emit())
            self._widgets[f.name] = w
            return w

        if tp is float:
            w = _FloatSliderRow(
                label, min_v, max_v, float(default or 0.0),
                step=step, decimals=decimals, tooltip=tip,
            )
            w.value_changed.connect(lambda _: self.params_changed.emit())
            self._widgets[f.name] = w
            return w

        if tp is str or _list_str_inner(tp) or _list_pair_inner(tp):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setFixedWidth(240)
            if tip:
                row.setToolTip(tip)
            rl.addWidget(lbl)
            if _list_pair_inner(tp):
                _text = ", ".join(f"{_a}:{_b}" for _a, _b in (default or []))
                edit: QLineEdit = _PairListEdit(_text)
            elif _list_str_inner(tp):
                edit = _ListEdit(", ".join(default or []))
            else:
                edit = QLineEdit(str(default or ""))
            edit.textChanged.connect(lambda _: self.params_changed.emit())
            rl.addWidget(edit, stretch=1)
            self._widgets[f.name] = edit
            return row

        return None

    # ── public API ───────────────────────────────────────────────────────────

    def get(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, w in self._widgets.items():
            if isinstance(w, tuple):
                cb, slider = w
                result[name] = slider.value() if cb.isChecked() else None
            elif isinstance(w, QCheckBox):
                result[name] = w.isChecked()
            elif isinstance(w, _PairListEdit):
                result[name] = [
                    (k.strip(), v.strip())
                    for s in w.text().split(",") if ":" in s
                    for k, v in [s.split(":", 1)]
                    if k.strip()
                ]
            elif isinstance(w, _ListEdit):
                result[name] = [s.strip() for s in w.text().split(",") if s.strip()]
            elif isinstance(w, QLineEdit):
                result[name] = w.text()
            else:
                result[name] = w.value()
        return result

    def load(self, params: dict) -> None:
        for name, val in params.items():
            w = self._widgets.get(name)
            if w is None:
                continue
            if isinstance(w, tuple):
                cb, slider = w
                cb.blockSignals(True)
                cb.setChecked(val is not None)
                cb.blockSignals(False)
                slider.setEnabled(val is not None)
                if val is not None:
                    slider._spin.blockSignals(True)
                    slider._slider.blockSignals(True)
                    slider._spin.setValue(float(val))
                    slider._spin.blockSignals(False)
                    slider._slider.blockSignals(False)
            elif isinstance(w, QCheckBox):
                w.blockSignals(True)
                w.setChecked(bool(val))
                w.blockSignals(False)
            elif isinstance(w, _PairListEdit):
                w.blockSignals(True)
                w.setText(", ".join(f"{k}:{v}" for k, v in val) if val else "")
                w.blockSignals(False)
            elif isinstance(w, _ListEdit):
                w.blockSignals(True)
                w.setText(", ".join(val) if val else "")
                w.blockSignals(False)
            elif isinstance(w, QLineEdit):
                w.blockSignals(True)
                w.setText(str(val) if val is not None else "")
                w.blockSignals(False)
            else:
                w._spin.blockSignals(True)
                w._slider.blockSignals(True)
                w._spin.setValue(val)
                w._spin.blockSignals(False)
                w._slider.blockSignals(False)
