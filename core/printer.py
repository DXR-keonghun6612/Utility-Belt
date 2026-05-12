"""Core Printer.

Graph_Model 딕셔너리를 .drawio 파일로 렌더링하는 공통 로직을 제공합니다.
언어별 printer는 파이프라인 실행 후 이 함수를 호출합니다.
"""
import os
from pathlib import Path
from core.graph import Graph_Model
from core.form.drawio import Graph_Builder


def Render_graphs(
    graphs: dict[str, Graph_Model],
    output_dir: str,
    is_detailed: bool = False,
) -> None:
    """Graph_Model 딕셔너리를 .drawio 파일로 렌더링하여 저장합니다.

    Args:
        graphs: 패키지/디렉토리 경로를 키로, Graph_Model을 값으로 가지는 딕셔너리.
        output_dir: .drawio 파일을 저장할 출력 디렉토리 경로.
        is_detailed: 상세 모드 활성화 여부 (함수 인자 및 타입 힌트 표시).
    """
    _out_path = Path(output_dir)
    _out_path.mkdir(parents=True, exist_ok=True)
    _builder = Graph_Builder()

    for pkg_path, graph_data in graphs.items():
        _xml = _builder.Build_from_graph(graph_data, is_detailed, current_pkg=pkg_path)
        _safe_name = pkg_path.replace(os.sep, ".").replace("/", ".")
        _file_path = _out_path / f"{_safe_name}.drawio"

        with open(_file_path, "w", encoding="utf-8") as f:
            f.write(_xml)

    print(f"[{output_dir}] {len(graphs)}개의 다이어그램 생성 완료.")
