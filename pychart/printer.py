"""pychart printer: CLI 진입점 및 파이프라인 연결."""
import sys
import argparse

from pychart.parser import PyChart_Pipeline
from core.printer import Render_graphs


def Generate_Diagrams(
    root: str,
    output_dir: str,
    is_detailed: bool,
    namespace_filter: list[str] | None = None,
) -> None:
    _pipeline = PyChart_Pipeline(
        target_roots=[root],
        namespace_filter=namespace_filter,
    )
    _graphs = _pipeline.Run_by_package()

    if not _graphs:
        print("[알림] 분석된 파이썬 모듈이 없습니다.")
        return

    Render_graphs(_graphs, output_dir, is_detailed)


def Cli_Main() -> None:
    _parser = argparse.ArgumentParser(
        description="CHART: Python 프로젝트 구조 분석 및 Draw.io 생성기"
    )
    _parser.add_argument(
        "-r", "--root", type=str, required=True, metavar="DIR",
        help="분석할 루트 디렉토리",
    )
    _parser.add_argument(
        "-o", "--output", type=str, default="diagrams",
        help="출력 디렉토리명 (기본값: diagrams)",
    )
    _parser.add_argument(
        "-d", "--detail", action="store_true",
        help="상세 모드 활성화 (함수 인자 및 타입 힌트 표시)",
    )
    _parser.add_argument(
        "-n", "--namespace", type=str, nargs="+", metavar="PKG",
        help="분석 대상 패키지 경로 필터 (예: -n myapp.services myapp.models)",
    )

    args = _parser.parse_args()

    try:
        Generate_Diagrams(args.root, args.output, args.detail, args.namespace)
    except Exception as e:
        print(f"[오류 발생] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    Cli_Main()
