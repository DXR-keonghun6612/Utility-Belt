"""printer.py: CHART 시스템의 메인 진입점 및 파이프라인 제어.

전체 분석 과정을 총괄하며 Parser, Resolver, Builder를 연결함.
"""
import argparse
import sys

from pychart.parser.extractor import Project_Analyzer
from pychart.parser.linker import Dependency_Resolver
from pychart.form.drawio import Graph_Builder


def Generate_Diagram(
    target_dir: str, output_file: str, is_detailed: bool
) -> None:
    """순수 비즈니스 로직: 파서, 해석기, 렌더러를 연결하는 파이프라인.

    Args:
        target_dir: 분석할 소스 코드 디렉토리 경로.
        output_file: 저장할 결과 파일명 (.drawio).
        is_detailed: 상세 정보 표시 여부.
    """
    # 1. 파싱 계층 (Collector): 디렉토리 분석 및 IR 추출
    analyzer = Project_Analyzer()
    ir_data = analyzer.Analyze_directory(target_dir)

    # 2. 해석 계층 (Interpreter): IR 데이터에서 관계 추출 및 그래프 모델링
    resolver = Dependency_Resolver()
    graph_data = resolver.Resolve_relationships(ir_data)

    # 3. 프레젠테이션 계층 (Presenter): 그래프 데이터를 XML로 렌더링
    builder = Graph_Builder()
    xml_output = builder.Build_from_graph(graph_data, is_detailed)

    # 4. 디스크 쓰기
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_output)
        
    print(f"[{output_file}] 생성 완료. (분석된 심볼 수: {len(ir_data)})")


def Cli_Main() -> None:
    """CLI 환경 진입점. 명령행 인자를 파싱하고 다이어그램 생성을 트리거함."""
    _parser = argparse.ArgumentParser(
        description="CHART: Python 프로젝트 구조 분석 및 Draw.io 생성기"
    )
    _parser.add_argument(
        "target_dir", type=str, help="분석할 프로젝트 루트 디렉토리")
    _parser.add_argument(
        "-o", "--output", type=str, default="chart_output.drawio",
        help="출력 파일명"
    )
    _parser.add_argument(
        "-d", "--detail", 
        action="store_true", 
        help="상세 모드 활성화 (함수 인자 및 변수 타입 힌트 모두 표시)"
    )
    
    args = _parser.parse_args()
    
    try:
        Generate_Diagram(args.target_dir, args.output, args.detail)
    except Exception as e:
        print(f"[오류 발생] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    Cli_Main()
