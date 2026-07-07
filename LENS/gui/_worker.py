"""보유 ``Pipeline`` 의 한 단계(Convert/Run)를 백그라운드 스레드에서 실행하는 공용 워커.

무엇을 돌릴지는 ``task`` 콜러블이 정한다 (편집한 config 섹션을 클로저로 싸 주입).
"""

from __future__ import annotations

import traceback
from typing import Callable

from PySide6.QtCore import QObject, Signal

Progress = Callable[[str, int, int], None]   # 진행 콜백 (label, done, total)


class Pipeline_worker(QObject):
    """보유 ``Pipeline`` 의 한 단계를 백그라운드에서 실행하는 공용 워커.

    Attributes:
        finished: ``(성공 여부, root 경로 또는 traceback)`` emit.
        progress: ``(done, total, label)`` emit.
    """

    finished = Signal(bool, str)
    progress = Signal(int, int, str)

    def __init__(self, pipeline, task: Callable[[Progress], None]) -> None:
        """Args:
        pipeline: 단계를 돌릴 보유 ``Pipeline``.
        task:     ``progress`` 콜백을 받아 Pipeline 메서드를 부르는 단계 (config 는 클로저로 주입).
        """
        super().__init__()
        self._pipeline = pipeline
        self._task     = task

    def run(self) -> None:
        """단계를 실행하고 결과를 ``finished`` 로 알린다 (진행은 ``progress`` 로 중계)."""
        try:
            self._task(lambda _name, _i, _total: self.progress.emit(_i, _total, _name))
            self.finished.emit(True, str(self._pipeline.root))
        except Exception:
            self.finished.emit(False, traceback.format_exc())
