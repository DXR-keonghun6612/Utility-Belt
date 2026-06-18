"""Session 실행 워커 — QThread 에서 Session(config).Run() 을 돌린다."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal

from core.session.base import Session, Session_config


class Run_worker(QObject):
    """Session_config 를 받아 백그라운드에서 실행한다."""

    finished = Signal(bool, str)   # (성공 여부, workspace 경로 또는 traceback)

    def __init__(self, config: Session_config) -> None:
        super().__init__()
        self._config = config

    def run(self) -> None:
        try:
            _session = Session(self._config)
            _session.Run()
            self.finished.emit(True, str(_session.workspace))
        except Exception:
            self.finished.emit(False, traceback.format_exc())
