"""Flow 카드 — flow 하나(= ``flows:`` 1 엔트리) config 편집 위젯 (필드 구성은 README)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from core.process import PROCESS_REGISTRY
from gui.form import Config_form, _Model_form, specs_from_callable
from gui.widgets import List_editor, List_row, Pair_list_editor, drop, reorder


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

PROCESS_KEYS = sorted(PROCESS_REGISTRY._module_dict)
# process 키 → 분류 경로("대분류/중분류"). 없으면 "기타". 트리 팝업이 경로를 쪼개 계층을 만든다.
PROCESS_CATALOG = {
    _k: (getattr(_c, "CATEGORY", "") or "기타")
    for _k, _c in PROCESS_REGISTRY._module_dict.items()
}


def _process_has_model(cls) -> bool:
    """process 클래스가 주입형 ``model`` 필드를 선언하는지 (모델 서브폼 노출 여부)."""
    return bool(cls) and "model" in getattr(cls, "__dataclass_fields__", {})


def _move_btns(on_up, on_down, on_remove) -> list[QToolButton]:
    """위/아래/삭제 툴버튼 ``[▲, ▼, ✕]`` 을 만들어 콜백에 연결해 돌려준다."""
    _result = []
    for _txt, _slot in (("▲", on_up), ("▼", on_down), ("✕", on_remove)):
        _b = QToolButton()
        _b.setText(_txt)
        _b.clicked.connect(_slot)
        _result.append(_b)
    return _result


# ── Process step별 출력 라우팅 편집기 ──────────────────────────────────────────

class _Output_row(List_row):
    """``outputs`` 한 항목 편집 행 — ``key | → to | level | type | format | dir | ✕`` (route spec 은 README)."""

    def __init__(self, key: str = "", spec: dict | None = None,
                 keys=(), block: bool = False, parent=None) -> None:
        """행을 구성한다.

        Args:
            key: 초기 출력 키.
            spec: 초기 라우팅 스펙 (``to`` / ``level`` / ``type`` / ``format`` / ``dir``).
            keys: 키 콤보에 채울 후보(이 process의 OUTPUTS).
            block: True면 finalize/params 레벨 — level 숨김, ``to=meta`` 는 params 를 뜻한다.
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._block = block
        spec = spec or {}
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)

        self._key = QComboBox()
        self._key.setEditable(True)
        self._key.addItems(list(keys))
        self._key.setCurrentText(key)
        self._key.setToolTip("process 출력 키")

        self._to = QComboBox()
        self._to.addItems(["meta", "storage"])
        self._to.setCurrentText(spec.get("to", "meta"))
        self._to.setToolTip("meta=params(dataset-wide, 스칼라 인라인/배열 npy) · storage=params 파일"
                            if block else "meta=dataset_meta 인라인(rle/attr) · storage=파일(image/array)")

        self._level = QComboBox()
        self._level.addItems(["object", "frame"])
        self._level.setCurrentText(spec.get("level", "object"))
        self._level.setToolTip("object=object.data · frame=frame.data")

        self._type = QLineEdit(str(spec.get("type", "")))
        self._type.setPlaceholderText("type")
        self._type.setFixedWidth(72)
        self._type.setToolTip("storage 저장 타입 (segmap·image·array 등) — 비우면 format 으로 추론")

        self._format = QLineEdit(str(spec.get("format", "")))
        self._format.setPlaceholderText("format")
        self._format.setFixedWidth(56)
        self._format.setToolTip("storage일 때 ext/직렬화 (png·npy 등)")

        self._dir = QLineEdit(str(spec.get("dir", "")))
        self._dir.setPlaceholderText("dir")
        self._dir.setToolTip("storage일 때 파일이 저장될 디렉토리명 (경로 전용)")

        _rm = self._remove_button()

        _lay.addWidget(self._key, stretch=1)
        _lay.addWidget(QLabel("→"))
        _lay.addWidget(self._to)
        _lay.addWidget(self._level)
        _lay.addWidget(self._type)
        _lay.addWidget(self._format)
        _lay.addWidget(self._dir, stretch=1)
        _lay.addWidget(_rm)

        self._to.currentTextChanged.connect(self._sync_storage_fields)
        self._key.currentTextChanged.connect(self.changed)
        self._to.currentTextChanged.connect(self.changed)
        self._level.currentTextChanged.connect(self.changed)
        self._type.textChanged.connect(self.changed)
        self._format.textChanged.connect(self.changed)
        self._dir.textChanged.connect(self.changed)
        self._sync_storage_fields()

    def _sync_storage_fields(self) -> None:
        # type·format·dir 는 storage(파일 저장)일 때만, level 은 finalize/params 가 아닐 때만 의미 있음
        _storage = self._to.currentText() == "storage"
        self._type.setVisible(_storage)
        self._format.setVisible(_storage)
        self._dir.setVisible(_storage)
        self._level.setVisible(not self._block)

    def set_keys(self, keys) -> None:
        """키 콤보 후보를 갱신한다 (현재 텍스트는 유지).

        Args:
            keys: 새 키 후보 시퀀스.
        """
        _cur = self._key.currentText()
        self._key.blockSignals(True)
        self._key.clear()
        self._key.addItems(list(keys))
        self._key.setCurrentText(_cur)
        self._key.blockSignals(False)

    def to_config(self) -> tuple[str, dict]:
        """행을 ``(출력키, 스펙 dict)`` 로 직렬화한다.

        기본값(``to=meta``, ``level=object``)은 생략하고, ``type`` / ``format`` / ``dir`` 은 storage일 때만 담는다.

        Returns:
            ``(key, spec)``. key가 비면 상위에서 버려진다.
        """
        _spec: dict = {}
        _to = self._to.currentText()
        if _to != "meta":
            _spec["to"] = _to
        if not self._block and self._level.currentText() != "object":  # finalize/params 는 level 없음
            _spec["level"] = self._level.currentText()
        if _to == "storage":  # type·format·dir 는 storage 전용
            _tp = self._type.text().strip()
            if _tp:
                _spec["type"] = _tp
            _fmt = self._format.text().strip()
            if _fmt:
                _spec["format"] = _fmt
            _d = self._dir.text().strip()
            if _d:
                _spec["dir"] = _d
        return self._key.currentText().strip(), _spec


class _Outputs_editor(List_editor):
    """한 step 의 ``outputs`` 규칙(행) 목록 편집기 (``List_editor`` 베이스)."""

    def __init__(self, block: bool = False, parent=None) -> None:
        """편집기를 구성한다.

        Args:
            block: True면 finalize/params 레벨 행 — level 숨김, ``to=meta`` 는 params 를 뜻한다.
            parent: 부모 위젯.
        """
        super().__init__("+ 출력 추가", parent)
        self._block = block
        self._keys: tuple[str, ...] = ()

    def set_keys(self, keys) -> None:
        """모든 행의 키 후보를 갱신하고 이후 추가될 행에도 적용한다.

        Args:
            keys: 새 키 후보 시퀀스(이 process의 OUTPUTS).
        """
        self._keys = tuple(keys)
        for _r in self._rows:
            _r.set_keys(self._keys)

    def _make_row(self, key, spec) -> List_row:
        return _Output_row(key, spec if isinstance(spec, dict) else {},
                           self._keys, block=self._block)


# ── Process 선택기 — 검색 가능한 분류 트리 팝업 ────────────────────────────────

class _Process_popup(QFrame):
    """category 경로 트리 + 검색칸 팝업 — leaf(process) 선택 시 ``selected`` emit."""

    selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(4, 4, 4, 4)
        _lay.setSpacing(4)

        self._search = QLineEdit()
        self._search.setPlaceholderText("검색 (process · 분류)")
        self._search.setClearButtonEnabled(True)
        _lay.addWidget(self._search)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumSize(300, 360)
        _lay.addWidget(self._tree)

        self._search.textChanged.connect(self._populate)
        self._search.returnPressed.connect(self._pick_first)
        self._tree.itemClicked.connect(self._on_click)
        self._populate("")

    def _populate(self, text: str) -> None:
        """검색어로 트리를 다시 채운다 (분류 경로를 ``/`` 로 쪼개 계층 노드 생성)."""
        _text = text.strip().lower()
        self._tree.clear()
        _nodes: dict[tuple[str, ...], QTreeWidgetItem] = {}
        for _key in sorted(PROCESS_CATALOG):
            _cat = PROCESS_CATALOG[_key]
            if _text and _text not in _key.lower() and _text not in _cat.lower():
                continue
            _parent: QTreeWidgetItem | None = None
            _path: tuple[str, ...] = ()
            for _part in _cat.split("/"):
                _path += (_part,)
                _item = _nodes.get(_path)
                if _item is None:
                    _item = QTreeWidgetItem([_part])
                    _item.setFlags(Qt.ItemFlag.ItemIsEnabled)   # 분류 노드는 선택 불가
                    if _parent is None:
                        self._tree.addTopLevelItem(_item)
                    else:
                        _parent.addChild(_item)
                    _nodes[_path] = _item
                _parent = _item
            _leaf = QTreeWidgetItem([_key])
            _leaf.setData(0, Qt.ItemDataRole.UserRole, _key)
            if _parent is not None:
                _parent.addChild(_leaf)
        if _text:
            self._tree.expandAll()

    def _on_click(self, item: QTreeWidgetItem, _col: int) -> None:
        _key = item.data(0, Qt.ItemDataRole.UserRole)
        if _key:
            self.selected.emit(_key)
            self.close()

    def _pick_first(self) -> None:
        """엔터 — 트리의 첫 리프를 고른다 (검색 좁힌 뒤 빠른 확정용)."""
        _it = QTreeWidgetItemIterator(self._tree)
        while _it.value():
            _key = _it.value().data(0, Qt.ItemDataRole.UserRole)
            if _key:
                self.selected.emit(_key)
                self.close()
                return
            _it += 1


class _Process_picker(QWidget):
    """현재 process 키 버튼 — 누르면 검색 트리 팝업 (``currentText``/``setCurrentText`` 호환).

    Attributes:
        changed: 선택 키 변경 시 emit.
    """

    changed = Signal()

    def __init__(self, key: str = "", parent=None) -> None:
        super().__init__(parent)
        self._key = key
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        self._btn = QToolButton()
        self._btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn.setArrowType(Qt.ArrowType.NoArrow)
        self._btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn.setText(self._label(key))
        self._btn.setToolTip("클릭해 분류 트리에서 process 선택")
        self._btn.clicked.connect(self._open)
        _lay.addWidget(self._btn)

    @staticmethod
    def _label(key: str) -> str:
        if not key:
            return "(process 선택) ▾"
        _cat = PROCESS_CATALOG.get(key)
        return f"{key}   [{_cat}] ▾" if _cat else f"{key} ▾"

    def _open(self) -> None:
        _popup = _Process_popup(self)
        _popup.selected.connect(self._on_select)
        _popup.move(self._btn.mapToGlobal(self._btn.rect().bottomLeft()))
        _popup.show()
        _popup._search.setFocus()

    def _on_select(self, key: str) -> None:
        self.setCurrentText(key)

    # ── QComboBox 호환 API ──────────────────────────────────────────────────────

    def currentText(self) -> str:  # noqa: N802 — QComboBox API 관례 유지
        return self._key

    def setCurrentText(self, key: str) -> None:  # noqa: N802
        """현재 키를 설정한다. 값이 실제로 바뀔 때만 ``changed`` 를 emit한다."""
        self._btn.setText(self._label(key))
        if key != self._key:
            self._key = key
            self.changed.emit()


# ── Process 단계 ─────────────────────────────────────────────────────────────

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
        for _b in _move_btns(
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


# ── Flow 카드 ─────────────────────────────────────────────────────────────────

class Flow_card(QGroupBox):
    """flow 하나(``flows:`` 1 엔트리) config 편집 카드.

    Attributes:
        changed: 내용 변경 시 emit.
        remove_requested: ✕ 클릭 시 self emit.
        move_requested: ▲/▼ 클릭 시 ``(self, ±1)`` emit.
    """

    changed          = Signal()
    remove_requested = Signal(object)
    move_requested   = Signal(object, int)

    def __init__(self, locked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._locked = locked
        self._steps: list[Process_step] = []          # per-frame 체인
        self._fin_steps: list[Process_step] = []      # finalize(순회 후 1회) 체인
        self._build()

    # ── 구성 ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(6, 4, 6, 4)
        _lay.setSpacing(4)

        # 헤더: 접기 | object_type | name | 🔒/이동/삭제
        _hdr = QHBoxLayout()
        self._collapse_btn = QToolButton()
        self._collapse_btn.setCheckable(True)
        self._collapse_btn.setChecked(True)
        self._collapse_btn.setText("▼")
        self._collapse_btn.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        _hdr.addWidget(self._collapse_btn)

        # object_type — 진행 표시용 자유 명명 (등록 타입 아님)
        self._type_edit = QLineEdit("flow")
        self._type_edit.setPlaceholderText("object_type (진행 라벨)")
        self._type_edit.setToolTip("flow 진행 표시용 자유 명명 — 등록 타입이 아니다")
        self._type_edit.setFixedWidth(160)
        self._type_edit.textChanged.connect(self.changed)
        _hdr.addWidget(self._type_edit)

        # name — 진행바 표시 이름 (선택). 비우면 object_type 사용.
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("이름 (선택)")
        self._name_edit.setToolTip("진행바 표시 이름 — 비우면 object_type 사용")
        self._name_edit.textChanged.connect(self.changed)
        _hdr.addWidget(self._name_edit, stretch=1)

        self._lock_btn = QToolButton()
        self._lock_btn.setCheckable(True)
        self._lock_btn.setChecked(self._locked)
        self._lock_btn.setToolTip("편집 동결 (UI는 그대로, 컨트롤만 비활성화)")
        self._lock_btn.clicked.connect(self._on_lock_toggle)
        self._sync_lock_icon()
        _hdr.addWidget(self._lock_btn)
        for _b in _move_btns(
            lambda: self.move_requested.emit(self, -1),
            lambda: self.move_requested.emit(self, +1),
            lambda: self.remove_requested.emit(self),
        ):
            _hdr.addWidget(_b)
        _lay.addLayout(_hdr)

        self._body = QWidget()
        _body_lay = QVBoxLayout(self._body)
        _body_lay.setContentsMargins(0, 0, 0, 0)
        _body_lay.setSpacing(4)

        # 순회 단위 + 재실행 캐시
        _opt_row = QHBoxLayout()
        _opt_row.addWidget(QLabel("unit"))
        self._unit = QComboBox()
        self._unit.addItems(["frame", "object"])
        self._unit.setToolTip("frame=프레임당 1회(첫 객체) · object=프레임의 객체마다")
        self._unit.currentTextChanged.connect(self.changed)
        _opt_row.addWidget(self._unit)
        self._cacheable = QCheckBox("cacheable")
        self._cacheable.setToolTip("flow 의 params 출력이 meta.params 에 모두 있으면 순회 건너뜀")
        self._cacheable.toggled.connect(self.changed)
        _opt_row.addWidget(self._cacheable)
        _opt_row.addStretch(1)
        _body_lay.addLayout(_opt_row)

        # shared — 모든 step 에 주입할 공통 config (key → value)
        _shared_box = QGroupBox("shared (모든 step 공통 주입)")
        _shared_box.setToolTip("모든 step params 앞에 merge — step 이 선언한 키만 받는다 (예: space)")
        _shared_lay = QVBoxLayout(_shared_box)
        _shared_lay.setContentsMargins(6, 4, 6, 4)
        self._shared = Pair_list_editor("")
        self._shared.changed.connect(self.changed)
        _shared_lay.addWidget(self._shared)
        _body_lay.addWidget(_shared_box)

        # Processes (step마다 param + outputs)
        self._proc_box = QGroupBox("Processes")
        _proc_lay = QVBoxLayout(self._proc_box)
        _proc_lay.setContentsMargins(6, 4, 6, 4)
        _proc_lay.setSpacing(4)
        self._steps_layout = QVBoxLayout()
        self._steps_layout.setSpacing(4)
        _proc_lay.addLayout(self._steps_layout)
        self._add_proc_btn = QPushButton("+ process 추가")
        self._add_proc_btn.clicked.connect(lambda: self._add_step())
        _proc_lay.addWidget(self._add_proc_btn)
        _body_lay.addWidget(self._proc_box)

        # Finalize processes (순회 후 1회 — carry 최종값 → outputs 는 params 로)
        self._fin_box = QGroupBox("Finalize (순회 후 1회)")
        self._fin_box.setToolTip("per-frame 루프 종료 후 1회 — carry 누산 최종값을 받아 reduce. "
                                 "각 step 의 outputs 는 frame/object 위치가 없어 params 로 나간다. 없어도 됨.")
        _fin_lay = QVBoxLayout(self._fin_box)
        _fin_lay.setContentsMargins(6, 4, 6, 4)
        _fin_lay.setSpacing(4)
        self._fin_steps_layout = QVBoxLayout()
        self._fin_steps_layout.setSpacing(4)
        _fin_lay.addLayout(self._fin_steps_layout)
        self._add_fin_btn = QPushButton("+ finalize process 추가")
        self._add_fin_btn.clicked.connect(lambda: self._add_step(finalize=True))
        _fin_lay.addWidget(self._add_fin_btn)
        _body_lay.addWidget(self._fin_box)

        # carry — 프레임 간 이월할 ctx 키 (쉼표 구분)
        _carry_row = QHBoxLayout()
        _carry_lbl = QLabel("carry")
        _carry_lbl.setToolTip("다음 프레임 ctx 로 넘겨 누산할 키 (쉼표 구분)")
        _carry_row.addWidget(_carry_lbl)
        self._carry_edit = QLineEdit()
        self._carry_edit.setPlaceholderText("c0_acc, c1_acc")
        self._carry_edit.textChanged.connect(self.changed)
        _carry_row.addWidget(self._carry_edit, stretch=1)
        _body_lay.addLayout(_carry_row)

        _lay.addWidget(self._body)
        self._add_step()  # 신규 카드는 per-frame step 하나로 시작 (finalize 는 비워둠)

    # ── lock — UI는 그대로, 편집 컨트롤만 동결 ─────────────────────────────────

    def _sync_lock_icon(self) -> None:
        # 잠김 → 🔑(키), 풀림 → 🔒(자물쇠).
        self._lock_btn.setText("🔑" if self._lock_btn.isChecked() else "🔒")

    def _on_lock_toggle(self) -> None:
        self._locked = self._lock_btn.isChecked()
        self._sync_lock_icon()
        self._apply_lock()

    def _apply_lock(self) -> None:
        _editable = not self._locked
        for _w in (self._type_edit, self._name_edit, self._unit, self._cacheable,
                   self._shared, self._carry_edit, self._add_proc_btn, self._add_fin_btn):
            _w.setEnabled(_editable)
        for _s in self._steps + self._fin_steps:
            _s.setEnabled(_editable)

    def _toggle_collapse(self) -> None:
        _open = self._collapse_btn.isChecked()
        self._body.setVisible(_open)
        self._collapse_btn.setText("▼" if _open else "▶")

    # ── step 관리 (per-frame / finalize 공용) ──────────────────────────────────

    def _steps_of(self, step: Process_step) -> tuple[list, QVBoxLayout]:
        """이 step이 속한 ``(리스트, 레이아웃)`` 을 돌려준다 — 공용 핸들러용."""
        if step in self._fin_steps:
            return self._fin_steps, self._fin_steps_layout
        return self._steps, self._steps_layout

    def _add_step(self, key: str | None = None, finalize: bool = False) -> Process_step:
        _steps  = self._fin_steps if finalize else self._steps
        _layout = self._fin_steps_layout if finalize else self._steps_layout
        # finalize step 의 outputs 는 params 레벨(level 없음)
        _step = Process_step(key, show_outputs=True, outputs_block=finalize)
        _step.changed.connect(self.changed)
        _step.remove_requested.connect(self._remove_step)
        _step.move_requested.connect(self._move_step)
        _step.setEnabled(not self._locked)
        _steps.append(_step)
        reorder(_layout, _steps)
        self.changed.emit()
        return _step

    def _remove_step(self, step: Process_step) -> None:
        _steps, _layout = self._steps_of(step)
        if _steps is self._steps and len(_steps) <= 1:  # per-frame은 최소 1개 유지 (finalize는 0 허용)
            return
        _steps.remove(step)
        drop(step)
        reorder(_layout, _steps)
        self.changed.emit()

    def _move_step(self, step: Process_step, direction: int) -> None:
        _steps, _layout = self._steps_of(step)
        _i = _steps.index(step)
        _j = _i + direction
        if 0 <= _j < len(_steps):
            _steps[_i], _steps[_j] = _steps[_j], _steps[_i]
            reorder(_layout, _steps)
            self.changed.emit()

    # ── Public API ────────────────────────────────────────────────────────────

    def to_config(self) -> dict:
        """카드를 flow config dict로 직렬화한다 (기본값/빈 항목은 생략)."""
        _cfg: dict = {"object_type": self._type_edit.text().strip() or "flow"}
        _nm = self._name_edit.text().strip()
        if _nm:
            _cfg["name"] = _nm
        _cfg["unit"] = self._unit.currentText()
        _shared = dict(self._shared.pairs())
        if _shared:
            _cfg["shared"] = _shared
        _procs = [_s.to_config() for _s in self._steps]
        if _procs:
            _cfg["processes"] = _procs
        _fin = [_s.to_config() for _s in self._fin_steps]
        if _fin:
            _cfg["finalize_processes"] = _fin
        _carry = [_s.strip() for _s in self._carry_edit.text().split(",") if _s.strip()]
        if _carry:
            _cfg["carry"] = _carry
        if self._cacheable.isChecked():
            _cfg["cacheable"] = True
        return _cfg

    def load(self, d: dict) -> None:
        """flow config dict로 카드를 복원한다."""
        for _lst in (self._steps, self._fin_steps):
            for _s in list(_lst):
                _lst.remove(_s)
                drop(_s)

        self._type_edit.setText(str(d.get("object_type", "flow")))
        self._name_edit.setText(str(d.get("name", "")))
        self._unit.setCurrentText(str(d.get("unit", "frame")))
        self._shared.set_pairs(list((d.get("shared") or {}).items()))
        self._carry_edit.setText(", ".join(d.get("carry", []) or []))
        self._cacheable.setChecked(bool(d.get("cacheable", False)))

        for _pmeta in d.get("processes", []) or []:
            _key = _pmeta.get("object_type", "") if isinstance(_pmeta, dict) else str(_pmeta)
            _step = self._add_step(_key)
            if isinstance(_pmeta, dict):
                _step.load(_key, {_k: _v for _k, _v in _pmeta.items() if _k != "object_type"})
        if not self._steps:
            self._add_step()

        for _pmeta in d.get("finalize_processes", []) or []:
            _key = _pmeta.get("object_type", "") if isinstance(_pmeta, dict) else str(_pmeta)
            _step = self._add_step(_key, finalize=True)
            if isinstance(_pmeta, dict):
                _step.load(_key, {_k: _v for _k, _v in _pmeta.items() if _k != "object_type"})

        self._apply_lock()
