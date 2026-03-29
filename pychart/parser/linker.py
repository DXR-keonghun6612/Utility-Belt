"""Interpreter (Resolver) Layer.

Phase 4: 2-Pass 참조 해석 및 프록시 링킹 구현.
전역 심볼 테이블을 활용하여 네임스페이스를 인식하고 외부 참조를 스터브로 병합합니다.
"""
import re
import importlib.util
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from pychart.definition import Module_Info
from .registry import SYMBOL_TABLE
from .constants import IGNORED_TYPES


@dataclass
class Edge_Info:
    """노드 간의 연결선 정보 모델."""
    source_id: str
    target_id: str
    edge_type: str


@dataclass
class Graph_Model:
    """노드와 엣지로 이루어진 최종 그래프 데이터 구조."""
    nodes: dict[str, Any] = field(default_factory=dict)
    edges: list[Edge_Info] = field(default_factory=list)


class Dependency_Resolver:
    """전역 심볼 테이블을 기반으로 관계를 해석하고 스터브를 생성하는 링커."""

    def __init__(self) -> None:
        self.graph = Graph_Model()
        self._global_index: dict[str, str] = {}
        self._internal_modules = SYMBOL_TABLE.Get_all()
        self._Build_global_index()

    def _Build_global_index(self) -> None:
        for mod_name, mod_info in self._internal_modules.items():
            for cls in mod_info.classes:
                self._global_index[cls.name] = mod_name
            for func in mod_info.functions:
                self._global_index[func.name] = mod_name

    def Resolve_relationships(self, target_modules: list[str] | None = None) -> Graph_Model:
        scope = target_modules if target_modules else list(self._internal_modules.keys())

        for mod_name in scope:
            mod_info = self._internal_modules.get(mod_name)
            if not mod_info: continue
            # 모듈 자체는 노드로 등록하지 않음 (멤버들만 등록)

            for cls in mod_info.classes:
                cls_id = f"{mod_name}.{cls.name}"
                self.graph.nodes[cls_id] = cls
                
                # 상속 관계 (사용자 요청: 부모 -> 자식 방향으로 흐름 구성)
                for base in cls.bases:
                    target_id = self._Resolve_symbol(base, mod_info)
                    if target_id:
                        self.graph.edges.append(Edge_Info(target_id, cls_id, "inheritance"))

                # 속성/메서드 의존성 (사용자 요청: 부품 -> 조립체 방향으로 흐름 구성)
                for attr in cls.attributes:
                    self._Process_type_dependency(cls_id, attr.type_hint, mod_info)
                for method in cls.methods:
                    for arg in method.args:
                        self._Process_type_dependency(cls_id, arg.type_hint, mod_info)
                    self._Process_type_dependency(cls_id, method.return_type, mod_info)

            for func in mod_info.functions:
                func_id = f"{mod_name}.{func.name}"
                self.graph.nodes[func_id] = func
                for arg in func.args:
                    self._Process_type_dependency(func_id, arg.type_hint, mod_info)
                self._Process_type_dependency(func_id, func.return_type, mod_info)

        self._Filter_duplicate_edges()
        return self.graph

    def _Resolve_symbol(self, symbol_name: str, context_mod: Module_Info) -> str | None:
        if any(c.name == symbol_name for c in context_mod.classes):
            return f"{context_mod.name}.{symbol_name}"
        if symbol_name in self._global_index:
            target_mod_name = self._global_index[symbol_name]
            if target_mod_name in context_mod.imported_symbols:
                return self._Get_or_create_stub(target_mod_name, symbol_name)
        if symbol_name in context_mod.imported_symbols:
            return self._Get_or_create_stub(symbol_name)
        return None

    def _Get_or_create_stub(self, module_name: str, symbol_name: str | None = None) -> str:
        stub_id = f"stub:{module_name}"
        if symbol_name: stub_id += f".{symbol_name}"
        if stub_id not in self.graph.nodes:
            _source_path = None
            try:
                spec = importlib.util.find_spec(module_name)
                if spec and spec.origin: _source_path = str(Path(spec.origin).resolve())
            except: pass
            display_name = f"{module_name.split('.')[-1]}::{symbol_name}" if symbol_name else module_name
            self.graph.nodes[stub_id] = Module_Info(name=display_name, stereotype="«external»", file_path=_source_path)
        return stub_id

    def _Process_type_dependency(self, source_id: str, type_str: str, mod_info: Module_Info) -> None:
        words = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', type_str)
        for word in words:
            if word in IGNORED_TYPES: continue
            target_id = self._Resolve_symbol(word, mod_info)
            if target_id and target_id != source_id:
                # 사용자 요청: 부품(target) -> 조립체(source) 방향으로 Edge 생성
                self.graph.edges.append(Edge_Info(target_id, source_id, "dependency"))

    def _Filter_duplicate_edges(self) -> None:
        unique_edges, seen = [], set()
        for e in self.graph.edges:
            key = (e.source_id, e.target_id, e.edge_type)
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)
        self.graph.edges = unique_edges
