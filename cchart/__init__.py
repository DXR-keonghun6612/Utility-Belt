"""CChart Core Pipeline.

C/C++ 정적 코드 분석기 파이프라인의 최상위 진입점(Facade)을 제공합니다.
compile_commands.json을 진입점으로 사용하며,
root_filter / namespace_filter로 분석 범위를 지정할 수 있습니다.
"""
from pathlib import Path

from cchart.parser.compile_db import Compile_DB
from cchart.parser.extractor import CXX_Analyzer
from cchart.parser.linker import CXX_Dependency_Resolver
from cchart.registry import SYMBOL_TABLE
from core.graph import Graph_Model


class CChart_Pipeline:
    """C/C++ 분석 전체 라이프사이클을 관리하는 컨트롤러.

    Args:
        compile_db_path: compile_commands.json 파일 경로.
        root_filter: 지정 시 해당 디렉토리 하위 파일만 분석 대상으로 제한.
        namespace_filter: 지정 시 해당 namespace에 속하는 심볼만 추출.
    """

    def __init__(
        self,
        compile_db_path: str | Path,
        root_filter: str | Path | None = None,
        namespace_filter: list[str] | None = None,
    ) -> None:
        self.compile_db = Compile_DB(
            compile_db_path,
            root_filter=root_filter,
            namespace_filter=namespace_filter,
        )
        self.analyzer = CXX_Analyzer(
            self.compile_db,
            project_root=root_filter,
            namespace_filter=namespace_filter,
        )
        SYMBOL_TABLE.Clear()

    def Run_by_directory(self) -> dict[str, Graph_Model]:
        """1-Pass 파싱 및 2-Pass 링킹을 수행하여 디렉토리별 분할 그래프를 반환합니다.

        Returns:
            dict[str, Graph_Model]: 디렉토리 경로를 키로, 해당 영역의 의존성 그래프를 값으로 가집니다.
        """
        # [Phase 1] 전체 파일 파싱
        for file_path in self.compile_db.Get_all_files():
            self.analyzer.Parse_file(file_path)

        _ir_data = SYMBOL_TABLE.Get_all()
        if not _ir_data:
            return {}

        # 디렉토리 경로 기반 그룹화
        _dir_map: dict[str, list[str]] = {}
        for file_key in _ir_data.keys():
            _parent = str(Path(file_key).parent)
            if _parent == ".":
                _parent = "root"
            _dir_map.setdefault(_parent, []).append(file_key)

        # [Phase 2] 디렉토리별 그래프 생성
        _result: dict[str, Graph_Model] = {}
        for dir_path, files in _dir_map.items():
            _linker = CXX_Dependency_Resolver()
            _result[dir_path] = _linker.Resolve_relationships(files)

        return _result
