"""Graph algorithms — 직접 구현 (외부 라이브러리 미사용).

plan/dependencies.md: networkx 등을 도입하지 않고 필요한 알고리즘만 자체 구현.
03_linker의 abstraction 보정과 04_layout의 계층 배치에서 공유 사용.
"""
from __future__ import annotations
from collections import defaultdict, deque
from typing import Iterable

from .graph import Edge_Info


# ─────────────────────────────────────────────────────────
# 인접 리스트 구축
# ─────────────────────────────────────────────────────────
def Build_adjacency(
    edges: Iterable[Edge_Info], reverse: bool = False
) -> dict[str, list[str]]:
    """엣지 컬렉션에서 인접 리스트 dict 생성.

    Args:
        edges: 엣지 컬렉션.
        reverse: ``True``면 target → source 방향으로 뒤집어 구성
            (조상 검색용).

    Returns:
        ``{node_id: [neighbor_id, ...]}``.
    """
    _adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if reverse:
            _adj[e.target_id].append(e.source_id)
        else:
            _adj[e.source_id].append(e.target_id)
    return dict(_adj)


# ─────────────────────────────────────────────────────────
# 위상 정렬
# ─────────────────────────────────────────────────────────
def Topological_sort(
    nodes: Iterable[str], edges: Iterable[Edge_Info]
) -> list[str]:
    """Kahn's algorithm으로 위상 정렬.

    사이클이 있으면 사이클에 속한 노드들은 결과에서 제외됨
    (도달 가능한 부분만 반환).
    """
    _edges = list(edges)
    _adj = Build_adjacency(_edges)
    _indeg: dict[str, int] = {n: 0 for n in nodes}
    for _src, _tgts in _adj.items():
        for _tgt in _tgts:
            _indeg[_tgt] = _indeg.get(_tgt, 0) + 1

    _queue = deque([n for n, d in _indeg.items() if d == 0])
    _result: list[str] = []
    while _queue:
        _n = _queue.popleft()
        _result.append(_n)
        for _next in _adj.get(_n, []):
            _indeg[_next] -= 1
            if _indeg[_next] == 0:
                _queue.append(_next)
    return _result


# ─────────────────────────────────────────────────────────
# 조상 / 후손 탐색
# ─────────────────────────────────────────────────────────
def Ancestors(
    node: str,
    edges: Iterable[Edge_Info],
    edge_filter: set[str] | None = None,
) -> set[str]:
    """노드의 모든 조상을 BFS로 수집 (자기 자신 제외).

    Args:
        node: 출발 노드 ID.
        edges: 엣지 컬렉션.
        edge_filter: 따를 ``edge_type`` 집합. ``None``이면 모두 따름.
            상속 체인 추적 시 ``{"inheritance", "realization"}``.
    """
    _filtered = (
        list(edges) if edge_filter is None
        else [e for e in edges if e.edge_type in edge_filter]
    )
    _rev = Build_adjacency(_filtered, reverse=True)

    _visited: set[str] = set()
    _queue = deque([node])
    while _queue:
        _n = _queue.popleft()
        for _p in _rev.get(_n, []):
            if _p not in _visited and _p != node:
                _visited.add(_p)
                _queue.append(_p)
    return _visited


def Descendants(
    node: str,
    edges: Iterable[Edge_Info],
    edge_filter: set[str] | None = None,
) -> set[str]:
    """노드의 모든 후손을 BFS로 수집 (자기 자신 제외)."""
    _filtered = (
        list(edges) if edge_filter is None
        else [e for e in edges if e.edge_type in edge_filter]
    )
    _adj = Build_adjacency(_filtered)

    _visited: set[str] = set()
    _queue = deque([node])
    while _queue:
        _n = _queue.popleft()
        for _c in _adj.get(_n, []):
            if _c not in _visited and _c != node:
                _visited.add(_c)
                _queue.append(_c)
    return _visited


# ─────────────────────────────────────────────────────────
# 사이클 감지
# ─────────────────────────────────────────────────────────
def Has_cycle(edges: Iterable[Edge_Info]) -> bool:
    """3-색 DFS로 사이클 존재 여부 판정.

    Notes:
        WHITE(미방문) → GRAY(방문 중) → BLACK(완료).
        GRAY 노드를 다시 만나면 사이클.
    """
    _adj = Build_adjacency(edges)
    _WHITE, _GRAY, _BLACK = 0, 1, 2
    _color: dict[str, int] = {}

    def _visit(n: str) -> bool:
        _color[n] = _GRAY
        for _next in _adj.get(n, []):
            _c = _color.get(_next, _WHITE)
            if _c == _GRAY:
                return True
            if _c == _WHITE and _visit(_next):
                return True
        _color[n] = _BLACK
        return False

    for _start in list(_adj.keys()):
        if _color.get(_start, _WHITE) == _WHITE:
            if _visit(_start):
                return True
    return False
