"""헤드리스 데이터셋 생성 진입점.

Usage:
    python run_capture.py --render_cfg path/to/sim_config.json
"""
import argparse
import json
import sys
from pathlib import Path


def _build_arg_parser() -> argparse.ArgumentParser:
    _parser = argparse.ArgumentParser(description="FOCUS 헤드리스 렌더링 파이프라인")
    _parser.add_argument(
        "--render_cfg", type=Path, required=True,
        help="Sim_Config JSON 파일 경로",
    )
    return _parser


def _report(current: int, total: int, message: str) -> None:
    print(json.dumps({"c": current, "t": total, "m": message}), flush=True)


def main() -> None:
    _args = _build_arg_parser().parse_args()
    from simulation.engine import Run_batch_capture
    Run_batch_capture(_args.render_cfg, progress_callback=_report)


if __name__ == "__main__":
    main()
