"""실행 패널 — 세션 전역 설정 + config 저장 / Session 실행."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Run_panel(QWidget):
    """프로젝트 설정과 저장·실행 버튼."""

    save_requested = Signal()
    run_requested  = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        _root = QVBoxLayout(self)

        _form = QFormLayout()
        self._project = QLineEdit("segment_labeling")
        _form.addRow("project", self._project)

        self._debug = QCheckBox("batch 프레임별 처리 로그 출력")
        _form.addRow("debug", self._debug)

        self._checkpoint = QCheckBox("batch process 결과 체크포인트 저장")
        _form.addRow("checkpoint", self._checkpoint)

        _out_row = QHBoxLayout()
        self._out_dir = QLineEdit("./config")
        _out_row.addWidget(self._out_dir, stretch=1)
        _browse = QPushButton("…")
        _browse.setFixedWidth(28)
        _browse.clicked.connect(self._pick_out_dir)
        _out_row.addWidget(_browse)
        _form.addRow("config 저장 위치", _out_row)

        _root.addLayout(_form)

        _btns = QHBoxLayout()
        _save = QPushButton("Config 저장")
        _save.clicked.connect(self.save_requested)
        _run = QPushButton("실행 ▶")
        _run.clicked.connect(self.run_requested)
        _btns.addWidget(_save)
        _btns.addWidget(_run)
        _root.addLayout(_btns)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("실행 로그")
        _root.addWidget(self._log, stretch=1)

    def _pick_out_dir(self) -> None:
        _d = QFileDialog.getExistingDirectory(self, "config 저장 위치")
        if _d:
            self._out_dir.setText(_d)

    def log(self, text: str) -> None:
        self._log.appendPlainText(text)

    def settings(self) -> dict:
        return {
            "project_name": self._project.text().strip() or "segment_labeling",
            "debug":        self._debug.isChecked(),
            "checkpoint":   self._checkpoint.isChecked(),
            "out_dir":      self._out_dir.text().strip() or "./config",
        }
