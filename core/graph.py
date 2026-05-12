"""Graph Layer.

언어 무관 분석 그래프 데이터 모델 및 엣지 타입 상수 정의.
"""
from dataclasses import dataclass, field
from typing import Any, Final

# 엣지 타입 상수
EDGE_INHERITANCE: Final[str] = "inheritance"   # 일반 상속
EDGE_REALIZATION: Final[str] = "realization"   # 추상/인터페이스 구현
EDGE_COMPOSITION: Final[str] = "composition"   # 강한 포함 (라이프사이클 공유)
EDGE_DEPENDENCY: Final[str] = "dependency"     # 단순 타입 참조
EDGE_CALL: Final[str] = "call"                 # 함수 호출
EDGE_INCLUDE: Final[str] = "include"           # #include (C/C++)
EDGE_FRIEND: Final[str] = "friend"             # friend 접근 (C/C++)


@dataclass
class Edge_Info:
    """노드 간 연결선 정보 모델."""
    source_id: str
    target_id: str
    edge_type: str
    label: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Graph_Model:
    """노드와 엣지로 구성된 분석 그래프."""
    nodes: dict[str, Any] = field(default_factory=dict)
    edges: list[Edge_Info] = field(default_factory=list)
    namespaces: dict[str, list[str]] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
