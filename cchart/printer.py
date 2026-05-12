"""cchart printer: CLI 진입점 및 파이프라인 연결."""
import sys
import argparse

from cchart import CChart_Pipeline
from core.printer import Render_graphs


def Generate_Diagrams(
    compile_db_path: str,
    output_dir: str,
    is_detailed: bool,
    root_filter: str | None = None,
    namespace_filter: list[str] | None = None,
) -> None:
    _pipeline = CChart_Pipeline(
        compile_db_path,
        root_filter=root_filter,
        namespace_filter=namespace_filter,
    )
    _graphs = _pipeline.Run_by_directory()

    if not _graphs:
        print("[알림] 분석된 C/C++ 파일이 없습니다.")
        return

    Render_graphs(_graphs, output_dir, is_detailed)


def Cli_Main() -> None:
    _parser = argparse.ArgumentParser(
        description="CHART: C/C++ 프로젝트 구조 분석 및 Draw.io 생성기"
    )
    _parser.add_argument(
        "compile_db", type=str,
        help="compile_commands.json 파일 경로",
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
        "-r", "--root", type=str, default=None, metavar="DIR",
        help="분석 대상 루트 디렉토리 필터 (해당 디렉토리 하위 파일만 분석)",
    )
    _parser.add_argument(
        "-n", "--namespace", type=str, nargs="+", metavar="NS",
        help="분석 대상 namespace 필터 (예: -n mylib::core mylib::utils)",
    )

    args = _parser.parse_args()

    try:
        Generate_Diagrams(
            args.compile_db, args.output, args.detail,
            root_filter=args.root,
            namespace_filter=args.namespace,
        )
    except Exception as e:
        print(f"[오류 발생] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    Cli_Main()
