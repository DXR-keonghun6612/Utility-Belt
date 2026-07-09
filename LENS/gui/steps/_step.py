"""단일 process step — 타입 선택 + 파라미터 폼 + 입출력 배선·저장 (배선 규칙은 core/process/README)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.process import PROCESS_REGISTRY
from gui.form import Config_form, _Model_form, specs_from_callable
from gui.widgets import Pair_list_editor, move_buttons

from ._output import _Outputs_editor
from ._picker import PROCESS_KEYS, _Process_picker


def _process_has_model(cls) -> bool:
    """process 클래스가 주입형 ``model`` 필드를 선언하는지 (모델 서브폼 노출 여부)."""
    return bool(cls) and "model" in getattr(cls, "__dataclass_fields__", {})


class Process_step(QGroupBox):
    """단일 process step — 타입 콤보 + 파라미터 폼(좌) + 배선/저장(우).

    우측은 위→아래로 입력 배선(``inputs``: Run 파라미터 ← ctx 키 별칭), 출력 재배선(``slots``:
    출력 port → ctx slot), 결과 저장(``outputs``: 라우팅). 배선 규칙은 core/process/README.md.

    Attributes:
        changed: 내용 변경 시 emit.
        remove_requested: ✕ 클릭 시 self emit.
        move_requested: ▲/▼ 클릭 시 ``(self, ±1)`` emit.
    """

    changed          = Signal()
    remove_requested = Signal(object)
    move_requested   = Signal(object, int)

    def __init__(self, key: str | None = None, show_outputs: bool = True,
                 outputs_block: bool = False, parent=None) -> None:
        """step을 구성한다.

        Args:
            key: 초기 process 타입 (None이면 첫 번째 등록 타입).
            show_outputs: True면 우측에 결과 저장(outputs 라우팅) 편집기를 둔다.
            outputs_block: True면 outputs 가 finalize/params 레벨(level 숨김, to=meta=params).
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._form: Config_form | None = None
        self._show_outputs = show_outputs
        self._outputs_block = outputs_block
        self._has_model = False
        self._build(key or (PROCESS_KEYS[0] if PROCESS_KEYS else ""))

    def _build(self, key: str) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(6, 4, 6, 4)
        _lay.setSpacing(2)

        _hdr = QHBoxLayout()
        _hdr.setSpacing(4)
        # 분류 트리 팝업 선택기 (단일 콤보 대체) — 미등록 키도 그대로 표시·보존
        self._combo = _Process_picker(key)
        self._combo.changed.connect(self._rebuild_form)
        _hdr.addWidget(self._combo, stretch=1)
        for _b in move_buttons(
            lambda: self.move_requested.emit(self, -1),
            lambda: self.move_requested.emit(self, +1),
            lambda: self.remove_requested.emit(self),
        ):
            _hdr.addWidget(_b)
        _lay.addLayout(_hdr)

        # 선택된 process의 입출력 표시 (read-only)
        self._io_label = QLabel()
        self._io_label.setWordWrap(True)
        # word-wrap 라벨은 QVBoxLayout이 heightForWidth를 안 물어봐 좁은 폭에서 글자가 잘린다.
        # sizePolicy에 heightForWidth 플래그(+세로 Minimum)를 줘 줄바꿈 높이를 확보한다.
        _io_sp = self._io_label.sizePolicy()
        _io_sp.setHeightForWidth(True)
        _io_sp.setVerticalPolicy(QSizePolicy.Policy.Minimum)
        self._io_label.setSizePolicy(_io_sp)
        self._io_label.setStyleSheet("color: #888; font-size: 11px;")
        _lay.addWidget(self._io_label)

        # 모델 주입 서브폼 — model 필드를 가진 process 일 때만 보인다
        self._model_form = _Model_form()
        self._model_form.changed.connect(self.changed)
        self._model_form.setVisible(False)
        _lay.addWidget(self._model_form)

        # 좌: process 파라미터 | 우: 결과 저장(outputs 라우팅)
        self._form_holder = QWidget()
        self._form_layout = QVBoxLayout(self._form_holder)
        self._form_layout.setContentsMargins(0, 0, 0, 0)

        if self._show_outputs:
            # 우측 배선/저장 컬럼: 입력 별칭(inputs) → 출력 재배선(slots) → 결과 저장(outputs)
            self._inputs_editor: Pair_list_editor | None = Pair_list_editor(
                "", tip="Run 파라미터 ← ctx 키 별칭 (좌=파라미터[위 입력 목록], 우=ctx 키). "
                        "예: mask ← roi — producer 없이 ctx 에 얹힌 값을 다른 이름으로 읽는다")
            self._inputs_editor.changed.connect(self.changed)
            _in_box = QGroupBox("입력 배선 (inputs)")
            _in_box.setToolTip("ctx 키 이름이 Run 파라미터명과 다를 때 별칭으로 잇는다 (slots 의 입력쪽 대칭)")
            _in_lay = QVBoxLayout(_in_box)
            _in_lay.setContentsMargins(6, 4, 6, 4)
            _in_lay.addWidget(self._inputs_editor)

            self._slots_editor: Pair_list_editor | None = Pair_list_editor(
                "", tip="출력 port → ctx slot 재배선 (좌=port[위 출력 목록], 우=ctx slot). "
                        "예: mask → belt — 같은 process 를 여러 번 써도 slot 을 달리해 충돌을 피한다")
            self._slots_editor.changed.connect(self.changed)
            _slot_box = QGroupBox("출력 재배선 (slots)")
            _slot_box.setToolTip("미선언 port 는 identity(그대로 ctx slot). 재배선 뒤 slot 이름이 진실")
            _slot_lay = QVBoxLayout(_slot_box)
            _slot_lay.setContentsMargins(6, 4, 6, 4)
            _slot_lay.addWidget(self._slots_editor)

            _out_box = QGroupBox("결과 저장 (outputs)")
            _out_lay = QVBoxLayout(_out_box)
            _out_lay.setContentsMargins(6, 4, 6, 4)
            self._outputs: _Outputs_editor | None = _Outputs_editor(block=self._outputs_block)
            self._outputs.changed.connect(self.changed)
            _out_lay.addWidget(self._outputs)
            _out_lay.addStretch(1)

            _right = QWidget()
            _right_lay = QVBoxLayout(_right)
            _right_lay.setContentsMargins(0, 0, 0, 0)
            _right_lay.setSpacing(4)
            _right_lay.addWidget(_in_box)
            _right_lay.addWidget(_slot_box)
            _right_lay.addWidget(_out_box)

            _split = QSplitter(Qt.Orientation.Horizontal)
            _split.addWidget(self._form_holder)
            _split.addWidget(_right)
            _split.setStretchFactor(0, 3)
            _split.setStretchFactor(1, 2)
            _split.setSizes([300, 220])
            # 크기 조절 핸들을 또렷한 세로선으로 — 인자 폼 / 배선·저장 경계 강조
            _split.setHandleWidth(3)
            _split.setStyleSheet(
                "QSplitter::handle:horizontal { background: #6a6a6a; margin: 2px 1px; }")
            _lay.addWidget(_split)
        else:
            self._outputs = None
            self._inputs_editor = None
            self._slots_editor = None
            _lay.addWidget(self._form_holder)

        self._rebuild_form()

    def _rebuild_form(self) -> None:
        _key = self._combo.currentText()
        if self._form is not None:
            self._form_layout.removeWidget(self._form)
            self._form.deleteLater()
            self._form = None
        _cls = PROCESS_REGISTRY.Get(_key)
        if _cls is not None:
            self._form = Config_form(specs_from_callable(_cls))
            self._form.params_changed.connect(self.changed)
            self._form_layout.addWidget(self._form)
        # 모델 서브폼 노출 여부 (model 필드 보유 시)
        self._has_model = _process_has_model(_cls)
        self._model_form.setVisible(self._has_model)
        # 입출력 표시 + outputs 키 후보를 이 process의 OUTPUTS로 갱신
        _inputs  = getattr(_cls, "INPUTS",  ()) if _cls else ()
        _outputs = getattr(_cls, "OUTPUTS", ()) if _cls else ()
        self._io_label.setText(
            f"입력: {', '.join(_inputs) or '—'}    →    출력: {', '.join(_outputs) or '—'}")
        if self._outputs is not None:
            self._outputs.set_keys(_outputs)
        self.changed.emit()

    def process_outputs(self) -> tuple[str, ...]:
        """현재 선택된 process의 OUTPUTS 키 (carry 키 제안 등에 사용)."""
        _cls = PROCESS_REGISTRY.Get(self._combo.currentText())
        return tuple(getattr(_cls, "OUTPUTS", ()) or ())

    def to_config(self) -> dict:
        """step을 process config dict로 직렬화한다.

        Returns:
            ``{"object_type": ..., <params>, "model"?, "inputs"?, "slots"?, "outputs"?}``.
        """
        _params = self._form.get() if self._form else {}
        _cfg = {"object_type": self._combo.currentText(), **_params}
        if self._has_model:
            _m = self._model_form.to_config()
            if _m:
                _cfg["model"] = _m
        if self._inputs_editor is not None:
            _ins = dict(self._inputs_editor.pairs())
            if _ins:
                _cfg["inputs"] = _ins
        if self._slots_editor is not None:
            _slots = dict(self._slots_editor.pairs())
            if _slots:
                _cfg["slots"] = _slots
        if self._outputs is not None:
            _outs = self._outputs.to_config()
            if _outs:
                _cfg["outputs"] = _outs
        return _cfg

    def load(self, key: str, params: dict) -> None:
        """process config로 step을 복원한다.

        Args:
            key: process 타입.
            params: ``model`` / ``inputs`` / ``slots`` / ``outputs`` 를 포함할 수 있는 파라미터 dict.
        """
        self._combo.setCurrentText(key)   # 키가 바뀌면 changed → _rebuild_form 으로 폼 재생성
        params = dict(params)
        _outs  = params.pop("outputs", {})
        _ins   = params.pop("inputs", {})
        _slots = params.pop("slots", {})
        _model = params.pop("model", {})
        if self._form is not None:
            self._form.load(params)
        self._model_form.load(_model if isinstance(_model, dict) else {})
        if self._inputs_editor is not None:
            self._inputs_editor.set_pairs(list((_ins or {}).items()))
        if self._slots_editor is not None:
            self._slots_editor.set_pairs(list((_slots or {}).items()))
        if self._outputs is not None:
            self._outputs.load(_outs)
