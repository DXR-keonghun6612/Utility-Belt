"""헤드리스 데이터셋 생성 진입점.

Usage:
    python run_capture.py --render_cfg path/to/sim_config.json
    python run_capture.py --render_cfg path/to/sim_config.json --profile opengl --context egl --width 1280 --height 720
"""
import argparse
import json
from pathlib import Path


def _build_arg_parser() -> argparse.ArgumentParser:
    _parser = argparse.ArgumentParser(description="FOCUS 헤드리스 렌더링 파이프라인")
    _parser.add_argument(
        "--render_cfg", type=Path, required=True,
        help="Sim_Config JSON 파일 경로",
    )
    _parser.add_argument(
        "--profile", choices=["blender", "opengl"], default="blender",
        help="렌더 백엔드 프로필 (기본값: blender)",
    )
    _parser.add_argument(
        "--context", choices=["auto", "egl", "embedded"], default="auto",
        dest="context_type",
        help="OpenGL 컨텍스트 경로 (opengl 프로필 전용, 기본값: auto)",
    )
    _parser.add_argument(
        "--width", type=int, default=640,
        help="렌더 출력 너비 픽셀 (opengl 프로필 전용)",
    )
    _parser.add_argument(
        "--height", type=int, default=480,
        help="렌더 출력 높이 픽셀 (opengl 프로필 전용)",
    )
    _parser.add_argument(
        "--output_dir", type=Path, default=None,
        help="결과 저장 폴더 (기본값: Config 파일명 기준 자동 생성)",
    )
    _parser.add_argument(
        "--channels", nargs="*",
        choices=["rgb", "depth", "normal", "segmentation"],
        default=None,
        help="렌더링할 패스 목록 (기본값: 전체)",
    )
    return _parser


def _report(current: int, total: int, message: str) -> None:
    print(json.dumps({"c": current, "t": total, "m": message}), flush=True)


def main() -> None:
    _args = _build_arg_parser().parse_args()
    from simulation.engine import Run_batch_capture
    Run_batch_capture(
        _args.render_cfg,
        profile=_args.profile,
        width=_args.width,
        height=_args.height,
        context_type=_args.context_type,
        output_dir=_args.output_dir,
        channels=_args.channels or None,
        progress_callback=_report,
    )


if __name__ == "__main__":
    main()
