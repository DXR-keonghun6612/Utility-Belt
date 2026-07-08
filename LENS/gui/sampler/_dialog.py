"""Sampler 창 — tasker 목록 + 설정 + ``▶ sample`` 실행 (비모달).

정본(staged ``Dataset_Meta``)에서 **이름 붙은 tasker**(파생 학습셋)를 빌드한다 — Converter 창이
raw→meta 를 자체 실행하는 패턴과 대칭으로, 여기선 meta→sample 을 ``Pipeline.Sample(name, cfg)`` 로
백그라운드 실행한다(``Pipeline_worker``). tasker 는 ``{root}/sample/{name}`` 폴더 + ``taskers.yaml``
레시피로 영속되며, 목록은 ``Pipeline.Taskers()`` 가 소스. Processes 체인(Run 의 ``Process_step`` 재사용)이
곧 실체화 — 정본 payload 를 resolve 해 태우고 최종 ``crop`` 을 sample payload 로 떨군다(빈 체인 불가).
뷰어(트리+crop 미리보기)는 [`_viewer`](_viewer.py) — ``open_viewer`` 로 연다.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui._io import load_dict, save_dict
from gui._worker import Pipeline_worker
from gui.run._flow_card import Process_step
from gui.widgets import Pop_dialog, drop, reorder

TASKS = ["classification", "detection"]   # sink 종류 (core SAMPLE_SINKS)
UNITS = ["object", "frame"]               # 순회 단위


class Sampler_dialog(Pop_dialog):
    """파생 tasker 빌더 — tasker 목록 + 설정 폼 + ``▶ sample`` 실행.

    Attributes:
        built: tasker 빌드/삭제로 목록이 바뀌었을 때 emit (``name`` — 삭제·초기화는 "").
        view_requested: 선택 tasker 를 뷰어로 열어달라는 요청 (``name``).
    """

    built          = Signal(str)
    view_requested = Signal(str)

    def __init__(self, get_pipeline: Callable[[], object | None], parent=None) -> None:
        """Args:
        get_pipeline: 보유 ``Pipeline`` 을 돌려주는 콜백 (없으면 None — Convert/Run 과 동일 패턴).
        """
        super().__init__("Sampler — 파생 tasker 빌드", size=(760, 520), parent=parent)
        self._get_pipeline = get_pipeline
        self._thread: QThread | None = None
        self._worker: Pipeline_worker | None = None
        self._build()
        self.reload_taskers()

    def _build(self) -> None:
        _split = QSplitter(Qt.Orientation.Horizontal)

        # ── 좌: tasker 목록 ──────────────────────────────────────────────────
        _left = QWidget()
        _ll = QVBoxLayout(_left)
        _ll.setContentsMargins(0, 0, 0, 0)
        _ll.addWidget(QLabel("tasker"))
        self._list = QListWidget()
        self._list.currentTextChanged.connect(self._on_select)
        self._list.itemDoubleClicked.connect(
            lambda _it: self.view_requested.emit(_it.text()))
        _ll.addWidget(self._list, stretch=1)
        _lbtns = QHBoxLayout()
        _new = QPushButton("새 tasker")
        _new.clicked.connect(self._on_new)
        _del = QPushButton("삭제")
        _del.clicked.connect(self._on_delete)
        _lbtns.addWidget(_new)
        _lbtns.addWidget(_del)
        _ll.addLayout(_lbtns)
        _split.addWidget(_left)

        # ── 우: 설정 폼 ──────────────────────────────────────────────────────
        _box = QGroupBox("설정")
        _form = QFormLayout(_box)
        self._name = QLineEdit()
        self._name.setPlaceholderText("tasker 이름 (폴더·레지스트리 key)")
        self._task = QComboBox()
        self._task.addItems(TASKS)
        self._unit = QComboBox()
        self._unit.addItems(UNITS)
        self._tr, self._va, self._te = self._ratio_spin(), self._ratio_spin(), self._ratio_spin()
        _ratios = QHBoxLayout()
        for _lbl, _sp in (("train", self._tr), ("val", self._va), ("test", self._te)):
            _ratios.addWidget(QLabel(_lbl))
            _ratios.addWidget(_sp)
        _rw = QWidget()
        _rw.setLayout(_ratios)
        self._salt = QLineEdit()
        self._salt.setPlaceholderText("split 해시 소금 (선택 — 같은 재현성, 다른 분할)")
        _form.addRow("name", self._name)
        _form.addRow("task", self._task)
        _form.addRow("unit", self._unit)
        _form.addRow("ratios", _rw)
        _form.addRow("salt", self._salt)

        # ── Processes — 실체화 체인 (staged 정본 payload → sample) ────────────
        # 체인이 곧 실체화(materialize) — 최소 1 step 강제. 비면 payload 없는 껍데기
        # sample 이 되므로 허용하지 않는다. 최종 출력 key ``crop`` 이 sample payload 로
        # 저장된다(step 의 slots 로 재배선 가능).
        self._steps: list[Process_step] = []
        _proc_box = QGroupBox("Processes (실체화 체인 — 정본 payload → sample)")
        _proc_box.setToolTip("staged 정본에서 payload 를 resolve 해 태우는 per-unit 체인. "
                             "최종 출력 key 'crop' 이 sample payload 로 저장된다(slots 로 재배선 가능). "
                             "비울 수 없다 — 체인이 없으면 이미지 없는 sample 이 된다.")
        _proc_lay = QVBoxLayout(_proc_box)
        _proc_lay.setContentsMargins(6, 4, 6, 4)
        _proc_lay.setSpacing(4)
        self._steps_layout = QVBoxLayout()
        self._steps_layout.setSpacing(4)
        _proc_lay.addLayout(self._steps_layout)
        _add = QPushButton("+ process 추가")
        _add.clicked.connect(lambda: self._add_step())
        _proc_lay.addWidget(_add)

        _right = QWidget()
        _rlay = QVBoxLayout(_right)
        _rlay.setContentsMargins(0, 0, 0, 0)
        _rlay.setSpacing(6)
        _rlay.addWidget(_box)
        _rlay.addWidget(_proc_box)
        _rlay.addStretch(1)
        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setWidget(_right)
        _split.addWidget(_scroll)
        _split.setStretchFactor(1, 1)
        _split.setSizes([200, 560])
        self._set_body(_split)
        self._load_cfg("", {})   # 기본값

        # ── 하단: 상태 + ▶ sample + 뷰어 ─────────────────────────────────────
        self._status = QLabel("")
        self._status.setStyleSheet("color: #888;")
        self._run_btn = QPushButton("▶ sample")
        self._run_btn.setToolTip("현재 설정으로 tasker 를 (재)빌드 — staged 정본에서 파생")
        self._run_btn.clicked.connect(self._on_run)
        self._view_btn = QPushButton("뷰어 열기")
        self._view_btn.setToolTip("선택 tasker 의 sample 트리·crop 미리보기")
        self._view_btn.clicked.connect(self._on_view)
        # 좌: 레시피(config) 불러오기/저장 + 산출물 내보내기
        self._save_btn = QPushButton("레시피 저장")
        self._save_btn.setToolTip("현재 설정을 tasker 레시피(yaml)로 저장 (재현용 config)")
        self._save_btn.clicked.connect(self._on_save_recipe)
        self._load_btn = QPushButton("레시피 불러오기")
        self._load_btn.setToolTip("tasker 레시피(yaml)를 폼에 싣는다 (config/sampler/*.yaml 등)")
        self._load_btn.clicked.connect(self._on_load_recipe)
        self._export_btn = QPushButton("내보내기")
        self._export_btn.setToolTip("빌드된 tasker 산출물(ImageFolder 트리)을 외부 경로로 복사")
        self._export_btn.clicked.connect(self._on_export)
        self._bottom_bar(left=[self._save_btn, self._load_btn, self._export_btn],
                         extra=[self._status, self._view_btn, self._run_btn],
                         on_reject=self.accept)

    @staticmethod
    def _ratio_spin() -> QDoubleSpinBox:
        _sp = QDoubleSpinBox()
        _sp.setRange(0.0, 1.0)
        _sp.setSingleStep(0.05)
        _sp.setDecimals(2)
        _sp.setFixedWidth(64)
        return _sp

    # ── 목록 ────────────────────────────────────────────────────────────────
    def reload_taskers(self, select: str | None = None) -> None:
        """``Pipeline.Taskers()`` 로 목록을 다시 채운다 (``select`` 있으면 그 tasker 선택)."""
        _pipe = self._get_pipeline()
        self._list.blockSignals(True)
        self._list.clear()
        if _pipe is not None:
            for _n in _pipe.List_taskers():        # 레시피 ∪ 실제 폴더 (orphan 폴더도 삭제 가능하게)
                self._list.addItem(_n)
        self._list.blockSignals(False)
        if select is not None:
            _items = self._list.findItems(select, Qt.MatchFlag.MatchExactly)
            if _items:
                self._list.setCurrentItem(_items[0])

    def _on_select(self, name: str) -> None:
        """목록 선택이 바뀌면 그 tasker 레시피를 폼에 싣는다."""
        _pipe = self._get_pipeline()
        if not name or _pipe is None:
            return
        self._load_cfg(name, _pipe.Taskers().get(name, {}))

    def _on_new(self) -> None:
        """폼을 비워 새 tasker 를 준비한다 (목록 선택 해제)."""
        self._list.clearSelection()
        self._list.setCurrentItem(None)
        self._load_cfg("", {})
        self._name.setFocus()

    def _on_delete(self) -> None:
        """선택 tasker 를 삭제한다 (폴더 + taskers.yaml)."""
        _pipe = self._get_pipeline()
        _it = self._list.currentItem()
        if _pipe is None or _it is None:
            return
        _name = _it.text()
        if QMessageBox.question(
                self, "tasker 삭제",
                f"tasker '{_name}' 의 폴더·레시피를 삭제합니다. 계속할까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        _pipe.Delete_tasker(_name)
        self.reload_taskers()
        self.built.emit("")

    # ── Processes 체인 (최소 1 step 강제 — 빈 체인 불가) ────────────────────────
    def _add_step(self, key: str | None = None) -> Process_step:
        """process step 하나를 체인에 추가한다 (Run 의 ``Process_step`` 재사용)."""
        _step = Process_step(key, show_outputs=True)
        _step.remove_requested.connect(self._remove_step)
        _step.move_requested.connect(self._move_step)
        self._steps.append(_step)
        reorder(self._steps_layout, self._steps)
        return _step

    def _remove_step(self, step: Process_step) -> None:
        if len(self._steps) <= 1:          # 최소 1 step — 빈 체인(껍데기 sample) 방지
            return
        self._steps.remove(step)
        drop(step)
        reorder(self._steps_layout, self._steps)

    def _move_step(self, step: Process_step, direction: int) -> None:
        _i = self._steps.index(step)
        _j = _i + direction
        if 0 <= _j < len(self._steps):
            self._steps[_i], self._steps[_j] = self._steps[_j], self._steps[_i]
            reorder(self._steps_layout, self._steps)

    # ── 폼 ↔ config ───────────────────────────────────────────────────────────
    def _load_cfg(self, name: str, cfg: dict) -> None:
        self._name.setText(name)
        self._task.setCurrentText(cfg.get("task", cfg.get("object_type", "classification")))
        self._unit.setCurrentText(cfg.get("unit", "object"))
        _r = cfg.get("ratios") or {"train": 0.8, "val": 0.1, "test": 0.1}
        self._tr.setValue(float(_r.get("train", 0.0)))
        self._va.setValue(float(_r.get("val", 0.0)))
        self._te.setValue(float(_r.get("test", 0.0)))
        self._salt.setText(str(cfg.get("salt", "")))
        for _s in list(self._steps):       # 체인 재구성
            self._steps.remove(_s)
            drop(_s)
        for _pmeta in cfg.get("processes", []) or []:
            _key = _pmeta.get("object_type", "") if isinstance(_pmeta, dict) else str(_pmeta)
            _step = self._add_step(_key)
            if isinstance(_pmeta, dict):
                _step.load(_key, {_k: _v for _k, _v in _pmeta.items() if _k != "object_type"})
        if not self._steps:                # 최소 1 step 보장 (빈 체인 불가)
            self._add_step()

    def _form_to_cfg(self) -> tuple[str, dict]:
        _cfg: dict = {
            "task": self._task.currentText(),
            "unit": self._unit.currentText(),
            "ratios": {"train": self._tr.value(), "val": self._va.value(), "test": self._te.value()},
            "salt": self._salt.text().strip(),
            "processes": [_s.to_config() for _s in self._steps],   # 실체화 체인 (최소 1)
        }
        return self._name.text().strip(), _cfg

    # ── 실행 (Pipeline.Sample 백그라운드) ──────────────────────────────────────
    def _on_run(self) -> None:
        if self._thread is not None:
            return
        _pipe = self._get_pipeline()
        if _pipe is None or not str(_pipe.root).strip():
            self._status.setText("dataset_root 미설정")
            return
        _name, _cfg = self._form_to_cfg()
        if not _name:
            self._status.setText("tasker 이름을 입력하세요")
            return
        if not _cfg.get("processes"):        # 빈 체인 = payload 없는 껍데기 sample → 거절
            self._status.setText("process 체인을 하나 이상 추가하세요 (실체화 없이 sample 불가)")
            return
        self._run_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._status.setText("빌드 중…")

        def _task(_progress) -> None:            # Sample 은 progress 콜백을 안 받는다 (무시)
            _pipe.Sample(_name, _cfg)

        # finished 는 bound method 로 연결한다 — lambda 로 붙이면 수신자 스레드가 불명이라
        # DirectConnection(워커 스레드서 실행)이 돼 _end 에서 자기 스레드를 wait → 크래시.
        # 추가 인자(name)는 self 에 실어 넘긴다(converter 다이얼로그와 같은 패턴).
        self._pending_name = _name
        self._thread = QThread()
        self._worker = Pipeline_worker(_pipe, _task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, ok: bool, info: str) -> None:
        self._status.setText("완료" if ok else f"실패: {info.splitlines()[-1]}")
        self._run_btn.setEnabled(True)
        self._export_btn.setEnabled(True)
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        if ok:
            self.reload_taskers(select=self._pending_name)
            self.built.emit(self._pending_name)

    # ── 레시피(config) 불러오기/저장 ────────────────────────────────────────────
    def _on_save_recipe(self) -> None:
        """현재 폼 설정을 tasker 레시피(yaml)로 저장한다 (재현용 config — 산출물과 분리)."""
        _name, _cfg = self._form_to_cfg()
        save_dict(self, f"{_name or 'tasker'}.yaml", _cfg)

    def _on_load_recipe(self) -> None:
        """tasker 레시피(yaml)를 골라 폼에 싣는다 (목록 선택은 해제 — 파일이 소스)."""
        _path, _d = load_dict(self)
        if _d is None:
            return
        self._list.clearSelection()
        self._list.setCurrentItem(None)
        self._load_cfg(self._name.text().strip() or _path.stem, _d)

    # ── 산출물 내보내기 (백그라운드 복사) ───────────────────────────────────────
    def _on_export(self) -> None:
        """빌드된 tasker 산출물을 외부 경로로 복사한다 (Pipeline.Export_tasker, 백그라운드)."""
        if self._thread is not None:
            return
        _pipe = self._get_pipeline()
        _it = self._list.currentItem()
        _name = _it.text() if _it is not None else self._name.text().strip()
        if _pipe is None or not _name:
            self._status.setText("내보낼 tasker 를 선택하세요")
            return
        _dest = QFileDialog.getExistingDirectory(self, "내보낼 위치 선택")
        if not _dest:
            return
        self._run_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._status.setText("내보내는 중…")

        def _task(_progress) -> None:
            _pipe.Export_tasker(_name, _dest)

        # bound method 로 연결 (lambda 는 DirectConnection→자기 스레드 wait 크래시). 인자는 self 로.
        self._pending_dest = _dest
        self._pending_name = _name
        self._thread = QThread()
        self._worker = Pipeline_worker(_pipe, _task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_export_done)
        self._thread.start()

    def _on_export_done(self, ok: bool, info: str) -> None:
        self._status.setText(f"내보냄: {self._pending_dest}/{self._pending_name}"
                             if ok else f"실패: {info.splitlines()[-1]}")
        self._run_btn.setEnabled(True)
        self._export_btn.setEnabled(True)
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None

    def _on_view(self) -> None:
        """선택(또는 폼) tasker 를 뷰어로 열어달라고 요청한다."""
        _it = self._list.currentItem()
        _name = _it.text() if _it is not None else self._name.text().strip()
        if _name:
            self.view_requested.emit(_name)
