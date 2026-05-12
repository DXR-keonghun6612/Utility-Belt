"""Interpreter (Resolver) Layer (C/C++).

2-Pass: 전역 심볼 테이블 기반으로 #include / 상속 / 타입 참조 의존성을 해석합니다.
"""
import re
from pathlib import Path
from core.definition import Module_Info
from core.graph import (
    Graph_Model, Edge_Info,
    EDGE_INHERITANCE, EDGE_DEPENDENCY, EDGE_INCLUDE,
)
from cchart.registry import SYMBOL_TABLE
from cchart.parser.constants import (
    IGNORED_TYPES,
    STEREOTYPE_LOCAL, STEREOTYPE_EXTERNAL, STEREOTYPE_SYSTEM,
    PREFIX_STUB,
)
from cchart.parser.utils import Normalize_type, Is_system_header


class CXX_Dependency_Resolver:
    """C++ 번역 단위 간 의존성 해석 및 링커."""

    def __init__(self) -> None:
        self.graph = Graph_Model()
        self._internal_modules = SYMBOL_TABLE.Get_all()
        self._cls_index: dict[str, str] = {}
        self._build_class_index()

    def _build_class_index(self) -> None:
        """전체 클래스명 → 파일 키 인덱스 구축."""
        for file_key, tu_info in self._internal_modules.items():
            for cls in tu_info.classes:
                _qualified = (
                    f"{cls.namespace_path}::{cls.name}" if cls.namespace_path else cls.name
                )
                self._cls_index[cls.name] = file_key
                self._cls_index[_qualified] = file_key

    def Resolve_relationships(
        self, target_files: list[str] | None = None
    ) -> Graph_Model:
        """심볼 간 관계를 분석하여 그래프 엣지를 생성합니다."""
        _scope = target_files or list(self._internal_modules.keys())

        for file_key in _scope:
            _tu = self._internal_modules.get(file_key)
            if not _tu:
                continue

            _tu.stereotype = STEREOTYPE_LOCAL
            self.graph.nodes[file_key] = _tu

            self._process_includes(file_key, _tu)
            self._process_classes(file_key, _tu)
            self._process_functions(file_key, _tu)

        self._filter_duplicate_edges()
        return self.graph

    # =========================================================================

    def _process_includes(self, file_key: str, tu_info) -> None:
        """#include 관계를 EDGE_INCLUDE 엣지로 등록합니다."""
        for inc_path in tu_info.includes:
            _stub_id = f"{PREFIX_STUB}{inc_path}"
            if _stub_id not in self.graph.nodes:
                _stereotype = STEREOTYPE_SYSTEM if Is_system_header(inc_path) else STEREOTYPE_EXTERNAL
                self.graph.nodes[_stub_id] = Module_Info(
                    name=Path(inc_path).name,
                    stereotype=_stereotype,
                    file_path=inc_path,
                )
            self.graph.edges.append(Edge_Info(file_key, _stub_id, EDGE_INCLUDE))

    def _process_classes(self, file_key: str, tu_info) -> None:
        """클래스의 상속 / 속성 / 메서드 의존성을 처리합니다."""
        for cls in tu_info.classes:
            _cls_id = f"{file_key}::{cls.name}"
            self.graph.nodes[_cls_id] = cls

            # 소속 관계 (번역 단위 → 클래스)
            self.graph.edges.append(Edge_Info(file_key, _cls_id, EDGE_DEPENDENCY))

            # namespace 등록
            if cls.namespace_path:
                self.graph.namespaces.setdefault(cls.namespace_path, []).append(_cls_id)

            # 상속 관계
            for base in cls.bases:
                _target = self._resolve_class(base)
                if _target:
                    self.graph.edges.append(Edge_Info(_target, _cls_id, EDGE_INHERITANCE))

            # 속성 타입 의존성
            for attr in cls.attributes:
                self._process_type_dependency(_cls_id, attr.type_hint)

            # 메서드 타입 의존성
            for method in cls.methods:
                for arg in method.args:
                    self._process_type_dependency(_cls_id, arg.type_hint)
                self._process_type_dependency(_cls_id, method.return_type)

    def _process_functions(self, file_key: str, tu_info) -> None:
        """전역 함수의 타입 의존성을 처리합니다."""
        for func in tu_info.functions:
            _func_id = f"{file_key}::{func.name}"
            self.graph.nodes[_func_id] = func
            self.graph.edges.append(Edge_Info(file_key, _func_id, EDGE_DEPENDENCY))

            for arg in func.args:
                self._process_type_dependency(_func_id, arg.type_hint)
            self._process_type_dependency(_func_id, func.return_type)

    def _resolve_class(self, name: str) -> str | None:
        """클래스명으로 파일 키를 탐색하여 노드 ID를 반환합니다."""
        _clean = Normalize_type(name)
        _file_key = self._cls_index.get(_clean)
        if _file_key:
            return f"{_file_key}::{_clean.split('::')[-1]}"
        return None

    def _process_type_dependency(self, source_id: str, type_str: str) -> None:
        """타입 문자열에서 식별자를 추출하여 의존성 엣지를 생성합니다."""
        _words = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', Normalize_type(type_str))
        for word in _words:
            if word in IGNORED_TYPES:
                continue
            _target = self._resolve_class(word)
            if _target and _target != source_id:
                self.graph.edges.append(Edge_Info(_target, source_id, EDGE_DEPENDENCY))

    def _filter_duplicate_edges(self) -> None:
        _seen = set()
        _unique = []
        for edge in self.graph.edges:
            _key = (edge.source_id, edge.target_id, edge.edge_type)
            if _key not in _seen:
                _seen.add(_key)
                _unique.append(edge)
        self.graph.edges = _unique
