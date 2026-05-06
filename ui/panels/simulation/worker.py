"""비동기 시뮬레이션 워커 스레드 모듈."""
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CAPTURE_CLI = _PROJECT_ROOT / "capture_cli.py"


class Simulation_Worker(QThread):
    """capture_cli.py를 subprocess로 실행하여 렌더링 파이프라인을 비동기로 구동함."""

    progress = Signal(int, int, str)
    finished_sig = Signal(bool, str)

    def __init__(self, config_path: Path):
        super().__init__()
        self.config_path = config_path

    def run(self):
        _env = os.environ.copy()
        _existing = _env.get("PYTHONPATH", "")
        _env["PYTHONPATH"] = str(_PROJECT_ROOT) + (os.pathsep + _existing if _existing else "")

        try:
            _proc = subprocess.Popen(
                [sys.executable, str(_CAPTURE_CLI), "--render_cfg", str(self.config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=_env,
            )

            for _line in _proc.stdout:
                _line = _line.strip()
                if not _line:
                    continue
                try:
                    _data = json.loads(_line)
                    self.progress.emit(_data["c"], _data["t"], _data["m"])
                except (json.JSONDecodeError, KeyError):
                    pass

            _proc.wait()
            if _proc.returncode == 0:
                self.finished_sig.emit(True, "시뮬레이션이 성공적으로 완료됨.")
            else:
                _err = _proc.stderr.read()
                self.finished_sig.emit(False, _err or f"프로세스 종료 코드: {_proc.returncode}")

        except Exception as e:
            self.finished_sig.emit(False, f"{str(e)}\n\n{traceback.format_exc()}")

    def _emit_progress(self, current: int, total: int, message: str) -> None:
        self.progress.emit(current, total, message)
