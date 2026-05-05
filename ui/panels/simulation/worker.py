"""비동기 시뮬레이션 워커 스레드 모듈."""
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from simulation.engine import Run_batch_capture


class Simulation_Worker(QThread):
    """백그라운드 스레드에서 렌더링 파이프라인을 비동기로 실행함."""
    
    progress = Signal(int, int, str)
    finished_sig = Signal(bool, str)

    def __init__(self, config_path: Path):
        """초기화 및 실행할 Config 경로 저장."""
        super().__init__()
        self.config_path = config_path

    def run(self):
        """시뮬레이션 배치 캡처 엔진 호출 및 예외 처리."""
        try:
            Run_batch_capture(self.config_path, progress_callback=self._emit_progress)
            self.finished_sig.emit(True, "시뮬레이션이 성공적으로 완료됨.")
        except Exception as e:
            err = traceback.format_exc()
            self.finished_sig.emit(False, f"{str(e)}\n\n{err}")

    def _emit_progress(self, current: int, total: int, message: str):
        """진행 상태 시그널 발송."""
        self.progress.emit(current, total, message)