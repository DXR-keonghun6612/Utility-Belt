"""PyChart Core Pipeline.

정적 코드 분석기 파이프라인의 최상위 진입점(Facade)을 제공합니다.
target_roots / namespace_filter로 분석 범위를 지정할 수 있습니다.
"""
import os
from pathlib import Path

from pychart.parser.extractor import Project_Analyzer
from pychart.parser.linker import Dependency_Resolver, Graph_Model
from pychart.registry import SYMBOL_TABLE


class PyChart_Pipeline:
    """분석 전체 라이프사이클 및 패키지 그룹화를 관리하는 컨트롤러.

    Args:
        target_roots: 분석할 루트 경로 리스트 (파일 또는 디렉토리).
        namespace_filter: 지정 시 해당 Python 패키지 경로에 속하는 파일만 분석.
                          예: ["myapp.services", "myapp.models"]
                          → myapp/services/, myapp/models/ 하위만 포함.
    """

    def __init__(
        self,
        target_roots: list[str],
        namespace_filter: list[str] | None = None,
    ) -> None:
        self.target_roots = target_roots
        # Python 패키지 경로(dot 구분) → 디렉토리 경로(OS 구분자)로 변환
        self._ns_dirs = [
            ns.replace(".", os.sep) for ns in (namespace_filter or [])
        ]
        self.analyzer = Project_Analyzer()
        SYMBOL_TABLE.Clear()

    def _passes_namespace_filter(self, file_path: Path) -> bool:
        """namespace_filter가 없으면 전부 통과, 있으면 경로 포함 여부로 판별."""
        if not self._ns_dirs:
            return True
        _path_str = str(file_path)
        return any(ns_dir in _path_str for ns_dir in self._ns_dirs)

    def _Scan_files(self) -> list[Path]:
        """지정된 루트 경로에서 대상 파이썬 파일 목록을 추출함."""
        _target_files = []
        for root in self.target_roots:
            _root_path = Path(root).resolve()
            if not _root_path.exists():
                continue

            if _root_path.is_file():
                if self._passes_namespace_filter(_root_path):
                    _target_files.append(_root_path)
                continue

            for dirpath, dirnames, filenames in os.walk(_root_path):
                dirnames[:] = [
                    d for d in dirnames
                    if d != "venv" and not d.startswith(".")
                ]
                for filename in filenames:
                    if filename.endswith(".py"):
                        _full_path = Path(dirpath) / filename
                        if self._passes_namespace_filter(_full_path):
                            _target_files.append(_full_path)
        return _target_files

    def Run_by_package(self) -> dict[str, Graph_Model]:
        """1-Pass 및 2-Pass를 수행하여 패키지별 분할 그래프를 반환함.

        Returns:
            dict[str, Graph_Model]: 패키지명을 키로, 해당 패키지의 의존성 그래프를 값으로 가짐.
        """
        # [Phase 1] 파일 스캔 및 파싱
        for file_path in self._Scan_files():
            self.analyzer.Parse_file(file_path)

        _ir_data = SYMBOL_TABLE.Get_all()
        if not _ir_data:
            return {}

        # 디렉토리 경로 기반 그룹화
        _package_map: dict[str, list[str]] = {}
        for file_key in _ir_data.keys():
            _parent_dir = str(Path(file_key).parent)
            if _parent_dir == ".":
                _parent_dir = "root"
            _package_map.setdefault(_parent_dir, []).append(file_key)

        # [Phase 2] 패키지별 그래프 생성
        _result_graphs: dict[str, Graph_Model] = {}
        for pkg_path, modules in _package_map.items():
            _linker = Dependency_Resolver()
            _result_graphs[pkg_path] = _linker.Resolve_relationships(modules)

        return _result_graphs
