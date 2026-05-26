"""Graph Layer.

언어 무관 분석 그래프 데이터 모델 및 엣지 타입 상수 정의.

03_linker가 ``Graph_Model``을 생산, 04_layout이 좌표를 부여한
``Positioned_Graph``로 변환, Renderer가 백엔드별 출력을 생성한다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from python_toolbox import Data_Schema


# ─────────────────────────────────────────────────────────
# 엣지 타입 상수 — plan/linker.md
# ─────────────────────────────────────────────────────────
EDGE_INHERITANCE: Final[str] = "inheritance"   # 일반 상속 (base가 interface 아님)
EDGE_REALIZATION: Final[str] = "realization"   # 인터페이스 구현 (base의 abstraction == interface)
EDGE_COMPOSITION: Final[str] = "composition"   # 강한 소유 (value, unique_ptr, 컨테이너)
EDGE_AGGREGATION: Final[str] = "aggregation"   # 약한 소유 (shared_ptr)
EDGE_ASSOCIATION: Final[str] = "association"   # 참조 보유 (raw pointer, reference, weak_ptr)
EDGE_DEPENDENCY: Final[str] = "dependency"     # 일시적 사용 (메서드 시그니처 등장)
EDGE_INCLUDE: Final[str] = "include"           # #include (C/C++)


# ─────────────────────────────────────────────────────────
# 분류 어휘
# ─────────────────────────────────────────────────────────
Category = Literal["type", "callable", "data"]
Wing = Literal["left", "center", "right"]


# ─────────────────────────────────────────────────────────
# 데이터 모델
# ─────────────────────────────────────────────────────────
@dataclass
class Edge_Info(Data_Schema):
    """노드 간 연결선 정보."""
    source_id: str
    target_id: str
    edge_type: str
    label: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Node_Info(Data_Schema):
    """그래프 노드 래퍼 (03_linker 출력).

    Notes:
        IR 전체를 임베드하지 않고 분류 정보 + 참조 키만 보관.
        상세 정보는 ``ir_source``가 가리키는 02_classifier yaml에서 조회.

    Attributes:
        id: 노드 ID — IR과 동일.
        name: 표시명.
        category: ``type`` / ``callable`` / ``data``.
        abstraction: 보정된 최종 추상화 수준 (type 카테고리만 의미 있음).
        traits: 구조적 특성 집합.
        origin: ``internal`` / ``external``.
        ir_source: 상세 IR이 저장된 02 yaml의 파일명.
    """
    id: str
    name: str
    category: Category = "type"
    abstraction: str = "concrete"
    traits: set[str] = field(default_factory=set)
    origin: str = "internal"
    ir_source: str = ""


@dataclass
class Positioned_Node(Node_Info):
    """04_layout 출력에서 좌표가 부여된 노드.

    Attributes:
        layer: y축 추상화 수준 (0이 최상단).
        wing: x축 영역 (``left`` / ``center`` / ``right``).
        col: wing 내 가로 순서.
        namespace_group: 소속 namespace 그룹 키.
    """
    layer: int = 0
    wing: Wing = "center"
    col: int = 0
    namespace_group: str = ""


@dataclass
class Graph_Model(Data_Schema):
    """03_linker 출력 — 분류된 노드 + 관계 그래프.

    Attributes:
        nodes: ``{node_id: Node_Info}``.
        edges: 엣지 리스트.
        namespaces: ``{namespace_path: [node_id, ...]}``.
        entry_points: 분석 시작 노드 ID 리스트.
    """
    nodes: dict[str, Any] = field(default_factory=dict)
    edges: list[Edge_Info] = field(default_factory=list)
    namespaces: dict[str, list[str]] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)


@dataclass
class Positioned_Graph(Data_Schema):
    """04_layout 출력 — 좌표가 부여된 그래프.

    Attributes:
        nodes: ``{node_id: Positioned_Node}``.
        edges: 엣지 리스트 (라우팅 정보는 renderer가 담당).
        namespace_groups: namespace별 노드 ID 그룹 정보.
    """
    nodes: dict[str, Any] = field(default_factory=dict)
    edges: list[Edge_Info] = field(default_factory=list)
    namespace_groups: dict[str, list[str]] = field(default_factory=dict)
