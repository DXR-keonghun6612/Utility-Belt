"""Flow 카드 — flow 하나(= ``flows:`` 1 엔트리) config 편집 위젯 (필드 구성은 README).

process step 편집 자체는 공통 모듈 ``gui/steps`` 소유 — 이 카드는 header/shared/carry 조립과
per-unit·finalize 두 ``Step_list`` 배치만 한다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.steps import Step_list
from gui.widgets import Pair_list_editor, move_buttons


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
        for _b in move_buttons(
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

        # Processes — per-unit 체인 (최소 1 step)
        self._proc_box = QGroupBox("Processes")
        _proc_lay = QVBoxLayout(self._proc_box)
        _proc_lay.setContentsMargins(6, 4, 6, 4)
        self._steps_list = Step_list(min_count=1, add_label="+ process 추가")
        self._steps_list.changed.connect(self.changed)
        _proc_lay.addWidget(self._steps_list)
        _body_lay.addWidget(self._proc_box)

        # Finalize — 순회 후 1회 도는 체인 (carry 최종값 reduce). outputs 는 params 레벨(level 없음)
        self._fin_box = QGroupBox("Finalize (순회 후 1회)")
        self._fin_box.setToolTip("per-frame 루프 종료 후 1회 — carry 누산 최종값을 받아 reduce. "
                                 "각 step 의 outputs 는 frame/object 위치가 없어 params 로 나간다. 없어도 됨.")
        _fin_lay = QVBoxLayout(self._fin_box)
        _fin_lay.setContentsMargins(6, 4, 6, 4)
        self._fin_list = Step_list(min_count=0, outputs_block=True,
                                   add_label="+ finalize process 추가")
        self._fin_list.changed.connect(self.changed)
        _fin_lay.addWidget(self._fin_list)
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
        # Step_list 는 QWidget — setEnabled 한 번으로 스텝+추가버튼까지 캐스케이드
        for _w in (self._type_edit, self._name_edit, self._unit, self._cacheable,
                   self._shared, self._carry_edit, self._steps_list, self._fin_list):
            _w.setEnabled(_editable)

    def _toggle_collapse(self) -> None:
        _open = self._collapse_btn.isChecked()
        self._body.setVisible(_open)
        self._collapse_btn.setText("▼" if _open else "▶")

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
        _procs = self._steps_list.to_config()
        if _procs:
            _cfg["processes"] = _procs
        _fin = self._fin_list.to_config()
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
        self._type_edit.setText(str(d.get("object_type", "flow")))
        self._name_edit.setText(str(d.get("name", "")))
        self._unit.setCurrentText(str(d.get("unit", "frame")))
        self._shared.set_pairs(list((d.get("shared") or {}).items()))
        self._carry_edit.setText(", ".join(d.get("carry", []) or []))
        self._cacheable.setChecked(bool(d.get("cacheable", False)))
        self._steps_list.load(d.get("processes", []))       # min_count=1 — per-unit 최소 1 보장
        self._fin_list.load(d.get("finalize_processes", []))
        self._apply_lock()
