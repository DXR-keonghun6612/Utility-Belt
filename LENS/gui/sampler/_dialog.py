"""Sampler 창 — tasker 목록 + 설정 + ``▶ sample`` 실행 (비모달).

정본(staged ``Dataset_Meta``)에서 **이름 붙은 tasker**(파생 학습셋)를 빌드한다 — Converter 창이
raw→meta 를 자체 실행하는 패턴과 대칭으로, 여기선 meta→sample 을 ``Pipeline.Sample(name, cfg)`` 로
백그라운드 실행한다(``Pipeline_worker``). tasker 는 ``{root}/sample/{name}`` 폴더 + ``taskers.yaml``
레시피로 영속되며, 목록은 ``Pipeline.Taskers()`` 가 소스. crop 토글은 ``processes:[frame_crop]`` 을 켜
crop 을 실체화한다. 뷰어(트리+crop 미리보기)는 [`_viewer`](_viewer.py) — ``open_viewer`` 로 연다.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui._worker import Pipeline_worker
from gui.widgets import Pop_dialog

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
        self._crop = QCheckBox("crop 실체화 (frame_crop — segment→obj 크롭 저장)")
        _form.addRow("name", self._name)
        _form.addRow("task", self._task)
        _form.addRow("unit", self._unit)
        _form.addRow("ratios", _rw)
        _form.addRow("salt", self._salt)
        _form.addRow("", self._crop)
        _split.addWidget(_box)
        _split.setStretchFactor(1, 1)
        _split.setSizes([220, 540])
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
        self._bottom_bar(extra=[self._status, self._view_btn, self._run_btn],
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
            for _n in sorted(_pipe.Taskers()):
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
        self._crop.setChecked(bool(cfg.get("processes")))

    def _form_to_cfg(self) -> tuple[str, dict]:
        _cfg: dict = {
            "task": self._task.currentText(),
            "unit": self._unit.currentText(),
            "ratios": {"train": self._tr.value(), "val": self._va.value(), "test": self._te.value()},
            "salt": self._salt.text().strip(),
        }
        if self._crop.isChecked():
            _cfg["processes"] = [{"object_type": "frame_crop"}]   # crop 실체화 체인
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
        self._run_btn.setEnabled(False)
        self._status.setText("빌드 중…")

        def _task(_progress) -> None:            # Sample 은 progress 콜백을 안 받는다 (무시)
            _pipe.Sample(_name, _cfg)

        self._thread = QThread()
        self._worker = Pipeline_worker(_pipe, _task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(lambda _ok, _info: self._on_finished(_ok, _info, _name))
        self._thread.start()

    def _on_finished(self, ok: bool, info: str, name: str) -> None:
        self._status.setText("완료" if ok else f"실패: {info.splitlines()[-1]}")
        self._run_btn.setEnabled(True)
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        if ok:
            self.reload_taskers(select=name)
            self.built.emit(name)

    def _on_view(self) -> None:
        """선택(또는 폼) tasker 를 뷰어로 열어달라고 요청한다."""
        _it = self._list.currentItem()
        _name = _it.text() if _it is not None else self._name.text().strip()
        if _name:
            self.view_requested.emit(_name)
