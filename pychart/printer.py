"""printer.py (Main Entry Point)"""
import argparse
import sys

from pychart.parser import Project_Analyzer
from pychart.form.drawio import Graph_Builder

def generate_diagram(
    target_dir: str, output_file: str, is_detailed: bool
) -> None:
    """순수 비즈니스 로직: 파서와 렌더러를 연결하는 파이프라인."""
    
    # 1. 파싱 계층: 디렉토리 분석 및 IR 추출
    analyzer = Project_Analyzer()
    ir_data = analyzer.Analyze_directory(target_dir)

    # 2. 프레젠테이션 계층: IR 데이터를 XML로 렌더링
    builder = Graph_Builder()
    xml_output = builder.Build_from_ir(ir_data, is_detailed)

    # 3. 디스크 쓰기
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_output)
        
    print(f"[{output_file}] 생성 완료. (분석된 클래스 수: {len(ir_data)})")


def cli_main() -> None:
    """CLI 환경 진입점."""
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
        generate_diagram(args.target_dir, args.output, args.detail)
    except Exception as e:
        print(f"[오류 발생] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    cli_main()