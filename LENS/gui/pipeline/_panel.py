"""Pipeline 탭 — dataloader 구성 + process 시퀀스 빌더 + 저장/실행.

세 패널(dataloader | sequence | run)을 조립하고, 저장/실행 시 인메모리 구성을
config yaml 로 직렬화한 뒤 Session_config 를 만들어 실행한다(산출물: config 저장).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from python_toolbox.file import Write_to

from core.session.base import Session_config
from gui.pipeline._dataloader_panel import Dataloader_panel
from gui.pipeline._run_panel import Run_panel
from gui.pipeline._sequence_panel import Sequence_panel
from gui.pipeline._worker import Run_worker


class _Collapsible(QWidget):
    """헤더 버튼으로 body 위젯을 접고 펼치는 컨테이너."""

    def __init__(self, title: str, body: QWidget, parent=None) -> None:
        super().__init__(parent)
        self._title = title
        self._body  = body

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(2)

        self._btn = QToolButton()
        self._btn.setCheckable(True)
        self._btn.setChecked(True)
        self._btn.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; text-align: left; }")
        self._btn.clicked.connect(self._toggle)
        _lay.addWidget(self._btn)
        _lay.addWidget(body, stretch=1)
        self._sync()

    def _toggle(self) -> None:
        self._body.setVisible(self._btn.isChecked())
        self._sync()

    def _sync(self) -> None:
        _arrow = "▼" if self._btn.isChecked() else "▶"
        self._btn.setText(f"{_arrow}  {self._title}")


class PipelinePanel(QWidget):
    """파이프라인 저작 탭."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: Run_worker | None = None
        self._build()

    def _build(self) -> None:
        _root = QVBoxLayout(self)
        _root.setContentsMargins(4, 4, 4, 4)

        self._dataloaders = Dataloader_panel()
        self._sequence    = Sequence_panel()
        self._run         = Run_panel()

        self._run.save_requested.connect(self._on_save)
        self._run.run_requested.connect(self._on_run)

        # 상단: dataloader | process 시퀀스 (각각 접기 가능)
        _top = QSplitter(Qt.Orientation.Horizontal)
        _top.addWidget(_Collapsible("Dataloaders", self._dataloaders))
        _top.addWidget(_Collapsible("Process 시퀀스", self._sequence))
        _top.setSizes([420, 520])

        # 전체: 위(구성) / 아래(실행·로그) 세로 분할
        _main = QSplitter(Qt.Orientation.Vertical)
        _main.addWidget(_top)
        _main.addWidget(self._run)
        _main.setSizes([520, 320])
        _root.addWidget(_main)

    # ── config 직렬화 ─────────────────────────────────────────────────────────

    def _write_configs(self) -> Session_config:
        """인메모리 구성을 yaml 로 저장하고 Session_config 를 만든다."""
        _s = self._run.settings()
        _out = Path(_s["out_dir"])
        _out.mkdir(parents=True, exist_ok=True)

        _dl_paths: list[str] = []
        for _i, _meta in enumerate(self._dataloaders.configs()):
            _p = _out / f"dataloader_{_i}.yaml"
            Write_to(_p, _meta)
            _dl_paths.append(str(_p))

        _proc_paths: list[str] = []
        for _i, _meta in enumerate(self._sequence.configs()):
            _p = _out / f"process_{_i}.yaml"
            Write_to(_p, _meta)
            _proc_paths.append(str(_p))

        _config = Session_config(
            project_name=_s["project_name"],
            dataloaders=_dl_paths,
            processes=_proc_paths,
            checkpoint=_s["checkpoint"],
            debug=_s["debug"],
        )
        _config.Write_to("session_config.yaml", _out)
        return _config

    # ── 핸들러 ────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        try:
            _config = self._write_configs()
            self._run.log(f"[저장] {_config.Serialize()['project_name']} "
                          f"→ {self._run.settings()['out_dir']} "
                          f"(dataloader {len(_config.dataloaders)}, "
                          f"process {len(_config.processes)})")
        except Exception as _e:
            self._run.log(f"[저장 실패] {_e}")

    def _on_run(self) -> None:
        if self._thread is not None:
            self._run.log("[실행 중] 이미 실행 중입니다.")
            return
        try:
            _config = self._write_configs()
        except Exception as _e:
            self._run.log(f"[준비 실패] {_e}")
            return

        self._run.log("[실행] Session 시작…")
        self._thread = QThread()
        self._worker = Run_worker(_config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, ok: bool, info: str) -> None:
        if ok:
            self._run.log(f"[완료] workspace → {info}")
        else:
            self._run.log(f"[실패]\n{info}")
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
