"""파라미터 폼 — ``_Spec`` 리스트를 타입별 위젯으로 빌드 + 모델 주입 서브폼 (타입→위젯 표는 README)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core import MODEL_BUILDERS
from gui.widgets import Float_slider_row, Int_slider_row, Pair_list_editor

from ._spec import _Spec, _list_pair, _list_str, _optional_float, specs_from_callable

# 이 폼이 **일부러 안 그리는** 파라미터 — 다른 위젯이 소유한다.
# (``model`` 은 nested 스펙이라 ``_Model_form`` 이 따로 편집한다.)
_DELEGATED = frozenset({"model"})


class _List_edit(QLineEdit):
    """쉼표로 구분된 문자열을 ``list[str]`` 로 편집하는 한 줄 입력."""


class Config_form(QWidget):
    """``_Spec`` 리스트로부터 파라미터 편집 폼을 자동 생성하는 위젯 (값은 ``get``/``load``).

    **모르는 타입은 조용히 넘기지 않고 실패한다.** 위젯이 안 생기면 그 파라미터는 ``get()`` 에서
    빠져 config 에 안 실리고, process 는 기본값으로 돌아버린다 — 사용자는 값을 넣었다고 믿는데.
    (실제로 gate 의 ``keep`` 이 그렇게 샜다.) 그래서 렌더 못 하는 타입은 **에러로 드러낸다**:
    폼을 고치든지, 그 파라미터를 다른 위젯에 위임(``_DELEGATED``)하든지 둘 중 하나를 하게 한다.

    Attributes:
        params_changed: 값 변경 시 emit.
    """

    params_changed = Signal()

    def __init__(self, specs: list[_Spec], parent=None, roi_provider=None) -> None:
        """Args:
        specs: 위젯을 만들 ``_Spec`` 목록.
        roi_provider: pair-list ROI 그리기 버튼 콜백 (없으면 비활성).

        Raises:
            TypeError: 폼이 렌더할 수 없는 타입의 파라미터가 있을 때 (조용히 버리지 않는다).
        """
        super().__init__(parent)
        self._specs = [_s for _s in specs if _s.name not in _DELEGATED]
        self._roi_provider = roi_provider
        self._widgets: dict[str, Any] = {}
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setSpacing(4)
        _lay.setContentsMargins(0, 0, 0, 0)
        _unsupported: list[_Spec] = []
        for _spec in self._specs:
            _w = self._make_widget(_spec)
            if _w is None:
                _unsupported.append(_spec)
                continue
            _lay.addWidget(_w)
        if _unsupported:
            raise TypeError(
                "Config_form 이 렌더할 수 없는 파라미터: "
                + ", ".join(f"{_s.name}: {_s.type}" for _s in _unsupported)
                + " — 위젯을 추가하거나 _DELEGATED 로 위임하세요 "
                  "(조용히 버리면 config 에 안 실려 기본값으로 돕니다).")

    def _make_widget(self, spec: _Spec) -> QWidget | None:
        _ui      = spec.ui
        _label   = _ui.get("label") or spec.name.replace("_", " ")
        _tip     = _ui.get("tip", "")
        _min     = _ui.get("min") if _ui.get("min") is not None else 0
        _max     = _ui.get("max") if _ui.get("max") is not None else 100
        _step    = _ui.get("step") if _ui.get("step") is not None else 0.05
        _default = spec.default
        _tp      = spec.type

        if _optional_float(_tp):
            _wrap = QWidget()
            _wl = QVBoxLayout(_wrap)
            _wl.setContentsMargins(0, 0, 0, 0)
            _wl.setSpacing(2)
            _cb = QCheckBox(_label)
            if _tip:
                _cb.setToolTip(_tip)
            _cb.setChecked(_default is not None)
            _wl.addWidget(_cb)
            _slider = Float_slider_row(
                f"  ↳ {_label}", _min, _max,
                float(_default) if _default is not None else (_min + _max) / 2,
                step=_step, tooltip=_tip)
            _slider.setEnabled(_default is not None)
            _cb.toggled.connect(_slider.setEnabled)
            _cb.toggled.connect(lambda _: self.params_changed.emit())
            _slider.value_changed.connect(lambda _: self.params_changed.emit())
            _wl.addWidget(_slider)
            self._widgets[spec.name] = (_cb, _slider)
            return _wrap

        if _tp is bool:
            _cb = QCheckBox(_label)
            if _tip:
                _cb.setToolTip(_tip)
            _cb.setChecked(bool(_default))
            _cb.toggled.connect(lambda _: self.params_changed.emit())
            self._widgets[spec.name] = _cb
            return _cb

        if _tp is int:
            _w = Int_slider_row(_label, _min, _max, int(_default or 0), tooltip=_tip)
            _w.value_changed.connect(lambda _: self.params_changed.emit())
            self._widgets[spec.name] = _w
            return _w

        if _tp is float:
            _w = Float_slider_row(_label, _min, _max, float(_default or 0.0),
                                   step=_step, tooltip=_tip)
            _w.value_changed.connect(lambda _: self.params_changed.emit())
            self._widgets[spec.name] = _w
            return _w

        if _list_pair(_tp):
            _editor = Pair_list_editor(
                _label, kind=_ui.get("kind"), tip=_tip,
                draw=_ui.get("draw", False), roi_provider=self._roi_provider)
            _editor.set_pairs(_default or [])
            _editor.changed.connect(lambda: self.params_changed.emit())
            self._widgets[spec.name] = _editor
            return _editor

        if _tp is str or _list_str(_tp):
            _row = QWidget()
            _rl = QHBoxLayout(_row)
            _rl.setContentsMargins(0, 0, 0, 0)
            _lbl = QLabel(_label)
            _lbl.setFixedWidth(240)
            if _tip:
                _row.setToolTip(_tip)
            _rl.addWidget(_lbl)
            if _list_str(_tp):
                _edit: QLineEdit = _List_edit(", ".join(_default or []))
            else:
                _edit = QLineEdit(str(_default or ""))
            _edit.textChanged.connect(lambda _: self.params_changed.emit())
            _rl.addWidget(_edit, stretch=1)
            self._widgets[spec.name] = _edit
            return _row

        return None

    # ── public API ───────────────────────────────────────────────────────────

    def get(self) -> dict[str, Any]:
        """현재 폼 값을 ``{이름: 값}`` dict 로 반환한다 (optional-float 해제 시 None)."""
        _res: dict[str, Any] = {}
        for _name, _w in self._widgets.items():
            if isinstance(_w, tuple):
                _cb, _slider = _w
                _res[_name] = _slider.value() if _cb.isChecked() else None
            elif isinstance(_w, QCheckBox):
                _res[_name] = _w.isChecked()
            elif isinstance(_w, Pair_list_editor):
                _res[_name] = _w.pairs()
            elif isinstance(_w, _List_edit):
                _res[_name] = [s.strip() for s in _w.text().split(",") if s.strip()]
            elif isinstance(_w, QLineEdit):
                _res[_name] = _w.text()
            else:
                _res[_name] = _w.value()
        return _res

    def append_pair(self, name: str, key: str, value: str) -> None:
        """``name`` pair-list 위젯에 ``(key, value)`` 행을 추가한다."""
        _w = self._widgets.get(name)
        if isinstance(_w, Pair_list_editor):
            _w.append(key, value)

    def load(self, params: dict) -> None:
        """저장된 값으로 폼을 복원한다 (시그널 없이; 폼에 없는 키는 무시).

        복원은 사용자의 편집과 구별되어야 하므로 ``params_changed`` 를 emit 하지 않는다 —
        슬라이더는 ``set_value``(시그널 없는 설정)를 쓴다.
        """
        for _name, _val in params.items():
            _w = self._widgets.get(_name)
            if _w is None:
                continue
            if isinstance(_w, tuple):                  # optional-float: (체크박스, 슬라이더)
                _cb, _slider = _w
                _cb.blockSignals(True)
                _cb.setChecked(_val is not None)
                _cb.blockSignals(False)
                _slider.setEnabled(_val is not None)
                if _val is not None:
                    _slider.set_value(float(_val))
            elif isinstance(_w, QCheckBox):
                _w.blockSignals(True)
                _w.setChecked(bool(_val))
                _w.blockSignals(False)
            elif isinstance(_w, Pair_list_editor):
                _w.blockSignals(True)
                _w.set_pairs(_val)
                _w.blockSignals(False)
            elif isinstance(_w, _List_edit):
                _w.blockSignals(True)
                _w.setText(", ".join(_val) if _val else "")
                _w.blockSignals(False)
            elif isinstance(_w, QLineEdit):
                _w.blockSignals(True)
                _w.setText(str(_val) if _val is not None else "")
                _w.blockSignals(False)
            else:                                      # Int/Float_slider_row
                _w.set_value(_val)


class _Model_form(QWidget):
    """process step 의 nested ``model: {type, …}`` 주입 스펙 편집기 (동작은 README).

    Attributes:
        changed: type/필드 변경 시 emit.
    """

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fields: Config_form | None = None

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(2)

        _row = QHBoxLayout()
        _lbl = QLabel("model.type")
        _lbl.setFixedWidth(120)
        _lbl.setToolTip("주입할 prediction 모델 (빈 값=없음). 선택 시 빌더 파라미터 노출")
        _row.addWidget(_lbl)
        self._type = QComboBox()
        self._type.addItem("")                       # 빈 값 = 모델 없음
        self._type.addItems(sorted(MODEL_BUILDERS))
        self._type.currentTextChanged.connect(self._rebuild)
        _row.addWidget(self._type, stretch=1)
        _lay.addLayout(_row)

        self._holder = QWidget()
        self._holder_lay = QVBoxLayout(self._holder)
        self._holder_lay.setContentsMargins(0, 0, 0, 0)
        _lay.addWidget(self._holder)
        self._rebuild()

    def _rebuild(self, *_args) -> None:
        """선택된 모델 타입의 빌더 ``__init__`` 파라미터로 하위 필드 폼을 다시 만든다."""
        if self._fields is not None:
            self._holder_lay.removeWidget(self._fields)
            self._fields.deleteLater()
            self._fields = None
        _builder = MODEL_BUILDERS.get(self._type.currentText())
        if _builder is not None:
            self._fields = Config_form(specs_from_callable(_builder))
            self._fields.params_changed.connect(self.changed)
            self._holder_lay.addWidget(self._fields)
        self.changed.emit()

    def to_config(self) -> dict:
        """``{"type": …, **빌더 파라미터}`` 를 반환한다. type이 비면 ``{}`` (모델 없음)."""
        _type = self._type.currentText().strip()
        if not _type:
            return {}
        _d: dict = {"type": _type}
        if self._fields is not None:
            _d.update(self._fields.get())
        return _d

    def load(self, d: dict | None) -> None:
        """``model`` 스펙 dict(``{"type": …, …}``)로 복원한다 (None/빈 = 모델 없음)."""
        d = d or {}
        self._type.blockSignals(True)
        self._type.setCurrentText(str(d.get("type", "")))
        self._type.blockSignals(False)
        self._rebuild()
        if self._fields is not None:
            self._fields.load({_k: _v for _k, _v in d.items() if _k != "type"})
