"""헤드리스 데이터셋 생성 진입점.

Usage:
    python capture_cli.py --render_cfg path/to/sim_config.json
"""

import sys
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication

from simulation.engine import Run_batch_capture

def _Build_arg_parser() -> argparse.ArgumentParser:
    _parser = argparse.ArgumentParser(
        description="FOCUS 헤드리스 렌더링 파이프라인"
    )
    _parser.add_argument(
        "--render_cfg", type=Path, default="result/render.json",
        help="Sim_Config JSON 파일 경로 (배치 캡처)"
    )
    return _parser

def cli_progress(current: int, total: int, message: str) -> None:
    print(f"[INFO] {message} ({current}/{total})")

if __name__ == "__main__":
    _args = _Build_arg_parser().parse_args()

    # EGL fallback might need QApplication
    _app = QApplication.instance() or QApplication(sys.argv)

    if _args.render_cfg:
        Run_batch_capture(_args.render_cfg, progress_callback=cli_progress)
    else:
        print("[ERROR] --render_cfg 옵션을 지정해야 함.")
        sys.exit(1)
