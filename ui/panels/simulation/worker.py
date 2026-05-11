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

    def __init__(
        self,
        config_path: Path,
        profile: str = "blender",
        width: int = 640,
        height: int = 480,
        context_type: str = "auto",
        output_dir: Path | None = None,
        channels: list[str] | None = None,
    ):
        super().__init__()
        self.config_path = config_path
        self._profile = profile
        self._width = width
        self._height = height
        self._context_type = context_type
        self._output_dir = output_dir
        self._channels = channels
        self._proc: subprocess.Popen | None = None
        self._stop_requested: bool = False

    def Request_stop(self) -> None:
        """실행 중인 subprocess를 종료 요청함."""
        self._stop_requested = True
        if self._proc is not None:
            self._proc.terminate()

    def run(self):
        self._stop_requested = False
        _env = os.environ.copy()
        _existing = _env.get("PYTHONPATH", "")
        _env["PYTHONPATH"] = str(_PROJECT_ROOT) + (os.pathsep + _existing if _existing else "")

        _cmd = [
            sys.executable, str(_CAPTURE_CLI),
            "--render_cfg", str(self.config_path),
            "--profile", self._profile,
        ]
        if self._profile == "opengl":
            _cmd += [
                "--width", str(self._width),
                "--height", str(self._height),
                "--context", self._context_type,
            ]
        if self._output_dir is not None:
            _cmd += ["--output_dir", str(self._output_dir)]
        if self._channels:
            _cmd += ["--channels"] + self._channels

        try:
            self._proc = subprocess.Popen(
                _cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=_env,
            )
            assert self._proc.stdout is not None
            assert self._proc.stderr is not None

            for _line in self._proc.stdout:
                _line = _line.strip()
                if not _line:
                    continue
                try:
                    _data = json.loads(_line)
                    self.progress.emit(_data["c"], _data["t"], _data["m"])
                except (json.JSONDecodeError, KeyError):
                    pass

            self._proc.wait()
            _returncode = self._proc.returncode
            _err = self._proc.stderr.read()
            self._proc = None

            if self._stop_requested:
                self.finished_sig.emit(False, "사용자에 의해 중단됨.")
            elif _returncode == 0:
                self.finished_sig.emit(True, "시뮬레이션이 성공적으로 완료됨.")
            else:
                self.finished_sig.emit(False, _err or f"프로세스 종료 코드: {_returncode}")

        except Exception as e:
            self._proc = None
            self.finished_sig.emit(False, f"{str(e)}\n\n{traceback.format_exc()}")
