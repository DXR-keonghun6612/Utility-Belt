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


class Load_worker(QObject):
    """dataset_root 로 ``Pipeline`` 을 **백그라운드에서 생성**하는 워커 (초 단위 meta 로드용).

    ``Pipeline_worker`` 는 이미 있는 pipeline 위에 단계를 돌리지만, 로드는 그 pipeline 을 **만드는** 일이라
    (수만 사이드카 복원) 여기서 따로 든다. pipeline 은 평범한 파이썬 객체라 워커 스레드에서 만들어
    메인으로 넘겨도 스레드 친화성 문제가 없다.

    Attributes:
        finished: ``(pipeline | None, "" | traceback)`` — 실패면 pipeline None + traceback.
        progress: ``(done, total, label)`` — meta 복원 진행.
    """

    finished = Signal(object, str)
    progress = Signal(int, int, str)

    def __init__(self, build: Callable[[Callable[[int, int], None]], object]) -> None:
        """Args:
        build: ``progress(done, total)`` 콜백을 받아 ``Pipeline`` 을 만들어 돌려주는 클로저.
        """
        super().__init__()
        self._build = build

    def run(self) -> None:
        """pipeline 을 만들고 결과를 ``finished`` 로 알린다 (진행은 ``progress`` 로 중계)."""
        try:
            _pipe = self._build(lambda _i, _total: self.progress.emit(_i, _total, "불러오는 중"))
            self.finished.emit(_pipe, "")
        except Exception:
            self.finished.emit(None, traceback.format_exc())
