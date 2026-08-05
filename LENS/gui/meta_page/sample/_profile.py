"""tasker 레시피 빌더 다이얼로그 — task/unit/ratios/salt + 실체화 체인 + 저장/불러오기 (실행 없음).

``run`` 갈래의 ``Run_dialog`` 에 대응하는 **편집 전용** 빌더 — 여기선 sample 레시피(``sample`` config)를
편집만 하고, 실제 빌드(``▶ sample``)·내보내기(``▶ split 처리``)는 ``Tasker_tab`` 툴바가 보유 cfg 로 직접
한다(빌더 ↔ 실행 분리). tasker 이름(폴더 key)은 탭이 소유하므로 여기 cfg 엔 없다. Processes 체인이 곧
crop 실체화 — 공통 ``gui.steps.Step_list``(sampler·run 공유)로 편집한다.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.export import TASKS as _TASK_SPECS

from gui._io import load_dict, save_dict
from gui.steps import Step_list
from gui.widgets import Pop_dialog

TASKS = list(_TASK_SPECS)                 # export 레지스트리에서 (task 늘면 자동 반영 — 하드코딩 drift 방지)


class Tasker_profile_dialog(Pop_dialog):
    """sample 레시피 빌더 — task/unit/ratios/salt + 실체화 체인 (편집 전용, 저장/불러오기)."""

    def __init__(self, cfg: dict | None = None, parent=None) -> None:
        """다이얼로그를 구성한다.

        Args:
            cfg: 복원할 sample 레시피 (탭이 보유 중인 현재 cfg). None 이면 기본값.
            parent: 부모 위젯.
        """
        super().__init__("tasker 레시피 — 빌더", size=(560, 520), parent=parent)
        self._build()
        self.load(cfg or {})

        _save = QPushButton("레시피 저장")
        _save.setToolTip("현재 설정을 tasker 레시피(yaml)로 저장 (재현용 config)")
        _save.clicked.connect(self._on_save)
        _load = QPushButton("불러오기")
        _load.setToolTip("tasker 레시피(yaml)를 폼에 싣는다")
        _load.clicked.connect(self._on_load)
        self._bottom_bar(left=[_save, _load], on_reject=self.accept)

    def _build(self) -> None:
        _box = QGroupBox("설정")
        _form = QFormLayout(_box)
        self._task = QComboBox()
        self._task.addItems(TASKS)
        self._task.setToolTip("데이터 성격 — 순회 unit 은 task 가 정한다 "
                              "(classification=object/crop · detection/segmentation=frame)")
        self._tr, self._va, self._te = self._ratio_spin(), self._ratio_spin(), self._ratio_spin()
        _ratios = QHBoxLayout()
        for _lbl, _sp in (("train", self._tr), ("val", self._va), ("test", self._te)):
            _ratios.addWidget(QLabel(_lbl))
            _ratios.addWidget(_sp)
        _rw = QWidget()
        _rw.setLayout(_ratios)
        self._salt = QLineEdit()
        self._salt.setPlaceholderText("split 해시 소금 (선택 — 같은 재현성, 다른 분할)")
        _form.addRow("task", self._task)
        _form.addRow("ratios (내보내기 split)", _rw)
        _form.addRow("salt", self._salt)

        # ── Processes — 실체화 체인 (staged 정본 payload → sample) ────────────
        # 체인이 곧 실체화(materialize) — Step_list(min_count=1)로 최소 1 step 강제. 비면 payload
        # 없는 껍데기 sample 이 되므로 허용하지 않는다. 최종 출력 key 'crop' 이 sample payload 로 저장.
        _proc_box = QGroupBox("Processes (실체화 체인 — 정본 payload → sample)")
        _proc_box.setToolTip("staged 정본에서 payload 를 resolve 해 태우는 per-unit 체인. "
                             "최종 출력 key 'crop' 이 sample payload 로 저장된다(slots 로 재배선 가능). "
                             "classification 은 필요(crop). detection/segmentation 은 정본 프레임 "
                             "역참조라 비워도 된다(순수 참조 sample).")
        _proc_lay = QVBoxLayout(_proc_box)
        _proc_lay.setContentsMargins(6, 4, 6, 4)
        self._steps_list = Step_list(min_count=0, add_label="+ process 추가")
        _proc_lay.addWidget(self._steps_list)

        _body = QWidget()
        _bl = QVBoxLayout(_body)
        _bl.setContentsMargins(0, 0, 0, 0)
        _bl.setSpacing(6)
        _bl.addWidget(_box)
        _bl.addWidget(_proc_box)
        _bl.addStretch(1)
        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setWidget(_body)
        self._set_body(_scroll)

    @staticmethod
    def _ratio_spin() -> QDoubleSpinBox:
        _sp = QDoubleSpinBox()
        _sp.setRange(0.0, 1.0)
        _sp.setSingleStep(0.05)
        _sp.setDecimals(2)
        _sp.setFixedWidth(64)
        return _sp

    # ── 폼 ↔ config ───────────────────────────────────────────────────────────
    def load(self, cfg: dict) -> None:
        """레시피 dict 를 폼에 싣는다 (task/ratios/salt/processes). unit 은 task 가 정하므로 안 싣는다."""
        self._task.setCurrentText(cfg.get("task", "classification"))
        _r = cfg.get("ratios") or {"train": 0.8, "val": 0.1, "test": 0.1}
        self._tr.setValue(float(_r.get("train", 0.0)))
        self._va.setValue(float(_r.get("val", 0.0)))
        self._te.setValue(float(_r.get("test", 0.0)))
        self._salt.setText(str(cfg.get("salt", "")))
        self._steps_list.load(cfg.get("processes", []))   # min_count=1 — 빈 체인(껍데기 sample) 방지

    def cfg(self) -> dict:
        """현재 편집된 sample 레시피를 반환한다 (탭이 닫을 때 읽어 보유). unit 은 task 가 정한다."""
        _task = self._task.currentText()
        return {
            "task": _task,
            "unit": _TASK_SPECS[_task].unit,             # task 가 정한다 — 별도 위젯 없음
            "ratios": {"train": self._tr.value(), "val": self._va.value(), "test": self._te.value()},
            "salt": self._salt.text().strip(),
            "processes": self._steps_list.to_config(),   # 실체화 체인 (classification=crop, det/seg 는 비움)
        }

    # ── 레시피(config) 저장/불러오기 ────────────────────────────────────────────
    def _on_save(self) -> None:
        save_dict(self, "tasker.yaml", self.cfg())

    def _on_load(self) -> None:
        _, _d = load_dict(self)
        if _d is not None:
            self.load(_d)
