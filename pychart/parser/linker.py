"""Interpreter (Resolver) Layer.

IR 데이터를 바탕으로 전체 프로젝트 맥락에서의 관계(Graph)를 완성함.
"""
import re
from dataclasses import dataclass, field

from pychart.definition import Class_Info

from .parsing_type import NODE

@dataclass
class Edge_Info:
    """노드 간의 연결선 정보 모델.
    
    Attributes:
        source_name: 시작 노드 심볼명.
        target_name: 끝 노드 심볼명.
        edge_type: 연결 종류 ("inheritance" 또는 "dependency").
    """
    source_name: str
    target_name: str
    edge_type: str


@dataclass
class Graph_Model:
    """노드와 엣지로 이루어진 최종 그래프 데이터 구조.
    
    Attributes:
        nodes: 심볼명을 키로 가지는 노드 맵.
        edges: 노드 간의 관계 리스트.
    """
    nodes: dict[str, NODE] = field(default_factory=dict)
    edges: list[Edge_Info] = field(default_factory=list)


class Dependency_Resolver:
    """관계 발견 및 필터링을 수행하는 인터프리터."""
    
    def __init__(self) -> None:
        """초기화."""
        self.graph = Graph_Model()

    def Resolve_relationships(self, ir_data: dict[str, NODE]) -> Graph_Model:
        """IR 데이터를 분석하여 상속 및 의존성 관계를 추출하고 그래프를 완성함.

        Args:
            ir_data: Parser 계층에서 수집된 IR 데이터 맵.

        Returns:
            Graph_Model: 관계 정보가 추가된 그래프 모델.
        """
        self.graph.nodes = ir_data.copy()
        
        for _name, _obj in ir_data.items():
            if isinstance(_obj, Class_Info):
                self._Extract_class_relationships(_name, _obj, ir_data)
                            
        # 중복 엣지 제거 (동일한 관계가 여러 번 탐지된 경우)
        self._Filter_duplicate_edges()

        return self.graph

    def _Extract_class_relationships(
        self, name: str, obj: Class_Info, ir_data: dict[str, NODE]
    ) -> None:
        """특정 클래스의 상속 및 의존성 관계를 추출함.

        Args:
            name: 클래스 심볼명.
            obj: 클래스 정보 객체.
            ir_data: 전체 IR 데이터 (대상 존재 여부 확인용).
        """
        # 1. 상속(Inheritance) 관계 추출
        for _base in obj.bases:
            if _base in ir_data:
                self.graph.edges.append(
                    Edge_Info(
                        source_name=name,
                        target_name=_base,
                        edge_type="inheritance"
                    )
                )

        # 2. 의존성(Dependency/Composition) 관계 추출
        for _attr in obj.attributes:
            # 타입 힌트 내의 모든 단어 추출 (제네릭 포함)
            _words = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', _attr.type_hint)
            for _word in _words:
                if _word != name and _word in ir_data:
                    self.graph.edges.append(
                        Edge_Info(
                            source_name=name,
                            target_name=_word,
                            edge_type="dependency"
                        )
                    )

    def _Filter_duplicate_edges(self) -> None:
        """중복된 엣지 정보를 제거하여 그래프를 최적화함."""
        _unique_edges: list[Edge_Info] = []
        _seen: set[tuple[str, str, str]] = set()
        
        for _edge in self.graph.edges:
            _key = (_edge.source_name, _edge.target_name, _edge.edge_type)
            if _key not in _seen:
                _seen.add(_key)
                _unique_edges.append(_edge)
                
        self.graph.edges = _unique_edges
