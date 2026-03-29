"""printer.py: CHART 시스템의 메인 진입점 및 파이프라인 제어.

전체 분석 과정을 총괄하며 Parser, Resolver, Builder를 연결함.
"""
import argparse
import sys
from pathlib import Path

from .parser.extractor import Project_Analyzer
from .parser.linker import Dependency_Resolver
from .parser.registry import SYMBOL_TABLE
from .form.drawio import Graph_Builder


def Generate_Diagrams(
    target_dir: str, output_dir: str, is_detailed: bool
) -> None:
    """순수 비즈니스 로직: 파서, 해석기, 렌더러를 연결하여 패키지별 다이어그램을 생성함.

    Args:
        target_dir: 분석할 소스 코드 프로젝트 루트 디렉토리.
        output_dir: 다이어그램 파일들을 저장할 출력 디렉토리.
        is_detailed: 상세 정보 표시 여부.
    """
    # 0. 전역 상태 초기화
    SYMBOL_TABLE._module_dict.clear()

    # 1. 파싱 계층 (Collector): 전역 인덱스 구축 (1-Pass)
    analyzer = Project_Analyzer(project_root=target_dir)
    ir_data = analyzer.Analyze_from_roots([target_dir])
    
    if not ir_data:
        print("[알림] 분석된 파이썬 모듈이 없습니다.")
        return

    # 출력 디렉토리 준비
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 2. 패키지 단위 그룹화 (Group modules by their parent package)
    package_map: dict[str, list[str]] = {}
    for mod_name in ir_data.keys():
        # 'pychart.parser.extractor' -> 'pychart.parser'
        # 'printer' -> '' (루트 모듈)
        parent_pkg = mod_name.rpartition('.')[0]
        if parent_pkg not in package_map:
            package_map[parent_pkg] = []
        package_map[parent_pkg].append(mod_name)

    # 3. 패키지별 렌더링 파이프라인
    for pkg_name, modules in package_map.items():
        # 각 패키지마다 독립적인 그래프 모델을 위해 루프 내에서 생성
        resolver = Dependency_Resolver()
        
        # 해당 패키지 내의 모든 모듈을 주인공으로 관계 해석 (2-Pass)
        graph_data = resolver.Resolve_relationships(target_modules=modules)

        # 프레젠테이션 계층: 그래프 데이터를 XML로 렌더링
        builder = Graph_Builder()
        xml_output = builder.Build_from_graph(graph_data, is_detailed, current_pkg=pkg_name)

        # 4. 디스크 쓰기 (파일명은 패키지명 사용, 루트는 'root'로 명명)
        display_name = pkg_name if pkg_name else "root_modules"
        file_path = out_path / f"{display_name}.drawio"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(xml_output)
            
    print(f"[{output_dir}] 디렉토리 내에 {len(package_map)}개의 패키지 다이어그램 생성 완료.")


def Cli_Main() -> None:
    """CLI 환경 진입점. 명령행 인자를 파싱하고 다이어그램 생성을 트리거함."""
    _parser = argparse.ArgumentParser(
        description="CHART: Python 프로젝트 구조 분석 및 Draw.io 생성기 (Drill-down 지원)"
    )
    _parser.add_argument(
        "target_dir", type=str, help="분석할 프로젝트 루트 디렉토리")
    _parser.add_argument(
        "-o", "--output", type=str, default="diagrams",
        help="출력 디렉토리명 (각 모듈별로 .drawio 파일이 생성됨)"
    )
    _parser.add_argument(
        "-d", "--detail", 
        action="store_true", 
        help="상세 모드 활성화 (함수 인자 및 변수 타입 힌트 모두 표시)"
    )
    
    args = _parser.parse_args()
    
    try:
        Generate_Diagrams(args.target_dir, args.output, args.detail)
    except Exception as e:
        print(f"[오류 발생] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    Cli_Main()
