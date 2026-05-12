"""Interpreter (Resolver) Layer.

Phase 4: 2-Pass 참조 해석 및 프록시 링킹 구현.
전역 심볼 테이블을 활용하여 네임스페이스를 인식하고 외부 참조를 스터브로 병합함.
"""
import re
import importlib.util
from pathlib import Path
from typing import Any

from core.definition import Module_Info
from core.graph import Graph_Model, Edge_Info, EDGE_INHERITANCE, EDGE_DEPENDENCY
from pychart.registry import SYMBOL_TABLE
from pychart.parser.constants import (
    IGNORED_TYPES,
    STEREOTYPE_LOCAL,
    STEREOTYPE_EXTERNAL,
    PREFIX_STUB,
)


class Dependency_Resolver:
    """전역 심볼 테이블 기반 의존성 해석 및 링커."""

    def __init__(self) -> None:
        self.graph = Graph_Model()
        self._global_index: dict[str, str] = {}
        self._internal_modules = SYMBOL_TABLE.Get_all()
        self._Build_global_index()

    def _Build_global_index(self) -> None:
        """전체 모듈의 클래스 및 함수명 기반 인덱스 구축."""
        for mod_name, mod_info in self._internal_modules.items():
            for cls in mod_info.classes:
                self._global_index[cls.name] = mod_name
            for func in mod_info.functions:
                self._global_index[func.name] = mod_name

    def Resolve_relationships(
        self, target_modules: list[str] | None = None
    ) -> Graph_Model:
        """심볼 간의 상속 및 참조 관계를 분석하여 그래프 엣지 생성."""
        _scope = target_modules
        if not _scope:
            _scope = list(self._internal_modules.keys())

        for mod_name in _scope:
            _mod_info = self._internal_modules.get(mod_name)
            if not _mod_info:
                continue

            # 로컬 모듈 노드 명시적 등록 및 스테레오타입 할당
            _mod_info.stereotype = STEREOTYPE_LOCAL
            self.graph.nodes[mod_name] = _mod_info

            self._Process_classes(mod_name, _mod_info)
            self._Process_functions(mod_name, _mod_info)

        self._Filter_duplicate_edges()
        return self.graph

    def _Process_classes(self, mod_name: str, mod_info: Module_Info) -> None:
        """모듈 내 클래스의 의존성 처리."""
        for cls in mod_info.classes:
            _cls_id = f"{mod_name}.{cls.name}"
            self.graph.nodes[_cls_id] = cls
            
            # 소속 관계 (모듈 -> 클래스)
            _edge_containment = Edge_Info(mod_name, _cls_id, EDGE_DEPENDENCY)
            self.graph.edges.append(_edge_containment)
            
            # 상속 관계 (부모 -> 자식 방향)
            for base in cls.bases:
                _target_id = self._Resolve_symbol(base, mod_info)
                if _target_id:
                    _edge = Edge_Info(_target_id, _cls_id, EDGE_INHERITANCE)
                    self.graph.edges.append(_edge)

            # 속성 의존성
            for attr in cls.attributes:
                self._Process_type_dependency(_cls_id, attr.type_hint, mod_info)
                
            # 메서드 의존성
            for method in cls.methods:
                for arg in method.args:
                    self._Process_type_dependency(
                        _cls_id, arg.type_hint, mod_info
                    )
                self._Process_type_dependency(
                    _cls_id, method.return_type, mod_info
                )

    def _Process_functions(self, mod_name: str, mod_info: Module_Info) -> None:
        """모듈 내 전역 함수의 의존성 처리."""
        for func in mod_info.functions:
            _func_id = f"{mod_name}.{func.name}"
            self.graph.nodes[_func_id] = func
            
            # 소속 관계 (모듈 -> 전역 함수)
            _edge_containment = Edge_Info(mod_name, _func_id, EDGE_DEPENDENCY)
            self.graph.edges.append(_edge_containment)
            
            for arg in func.args:
                self._Process_type_dependency(_func_id, arg.type_hint, mod_info)
                
            self._Process_type_dependency(
                _func_id, func.return_type, mod_info
            )

    def _Resolve_symbol(
        self, symbol_name: str, context_mod: Module_Info
    ) -> str | None:
        """식별자 이름을 기반으로 실제 참조 대상을 특정함."""
        # 1. 로컬 모듈 내 클래스 검사
        for cls_info in context_mod.classes:
            if cls_info.name == symbol_name:
                return f"{context_mod.name}.{symbol_name}"

        # 2. 임포트된 식별자 검사 (from A import B 구조 처리)
        for mod_name, imported_list in context_mod.imported_symbols.items():
            if symbol_name in imported_list:
                return self._Get_or_create_stub(mod_name, symbol_name)

        # 3. 모듈 자체가 임포트된 경우 (import A 구조 처리)
        if symbol_name in context_mod.imported_symbols:
            return self._Get_or_create_stub(symbol_name)

        return None

    def _Get_or_create_stub(
        self, module_name: str, symbol_name: str | None = None
    ) -> str:
        """외부 모듈 및 심볼에 대한 프록시(Stub) 노드 생성."""
        _stub_id = f"{PREFIX_STUB}{module_name}"
        if symbol_name:
            _stub_id += f".{symbol_name}"
            
        if _stub_id not in self.graph.nodes:
            _source_path = None
            try:
                _spec = importlib.util.find_spec(module_name)
                if _spec and _spec.origin:
                    _source_path = str(Path(_spec.origin).resolve())
            except Exception:
                pass
                
            _display = module_name
            if symbol_name:
                _display = f"{module_name.split('.')[-1]}::{symbol_name}"
                
            # 외부 프록시 객체 명시적 등록
            _stub_info = Module_Info(
                name=_display, 
                stereotype=STEREOTYPE_EXTERNAL, 
                file_path=_source_path
            )
            self.graph.nodes[_stub_id] = _stub_info
            
        return _stub_id

    def _Process_type_dependency(
        self, source_id: str, type_str: str, mod_info: Module_Info
    ) -> None:
        """타입 힌트 문자열에서 식별자를 추출하여 의존성 엣지 생성."""
        _words = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', type_str)
        for word in _words:
            if word in IGNORED_TYPES:
                continue
                
            _target_id = self._Resolve_symbol(word, mod_info)
            if _target_id and _target_id != source_id:
                _edge = Edge_Info(_target_id, source_id, EDGE_DEPENDENCY)
                self.graph.edges.append(_edge)

    def _Filter_duplicate_edges(self) -> None:
        """중복된 연결선을 제거함."""
        _unique_edges = []
        _seen = set()
        
        for edge in self.graph.edges:
            _key = (edge.source_id, edge.target_id, edge.edge_type)
            if _key not in _seen:
                _seen.add(_key)
                _unique_edges.append(edge)
                
        self.graph.edges = _unique_edges