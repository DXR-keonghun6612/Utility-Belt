"""printer.py (Main Entry Point)"""
import argparse
import sys

from pychart.parser import Project_Analyzer
from pychart.form.draw_io import Drawio_Graph_Builder

def generate_diagram(target_dir: str, output_file: str) -> None:
    """순수 비즈니스 로직: 파서와 렌더러를 연결하는 파이프라인."""
    
    # 1. 파싱 계층: 디렉토리 분석 및 IR 추출
    analyzer = Project_Analyzer()
    ir_data = analyzer.Analyze_directory(target_dir)

    # 2. 프레젠테이션 계층: IR 데이터를 XML로 렌더링
    builder = Drawio_Graph_Builder()
    xml_output = builder.Build_from_ir(ir_data)

    # 3. 디스크 쓰기
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_output)
        
    print(f"[{output_file}] 생성 완료. (분석된 클래스 수: {len(ir_data)})")


def cli_main() -> None:
    """CLI 환경 진입점."""
    parser = argparse.ArgumentParser(
        description="CHART: Python 프로젝트 구조 분석 및 Draw.io 생성기"
    )
    parser.add_argument(
        "target_dir", type=str, help="분석할 프로젝트 루트 디렉토리")
    parser.add_argument(
        "-o", "--output", type=str, default="chart_output.drawio",
        help="출력 파일명"
    )
    
    args = parser.parse_args()
    
    try:
        generate_diagram(args.target_dir, args.output)
    except Exception as e:
        print(f"[오류 발생] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    cli_main()