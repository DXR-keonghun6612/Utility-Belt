"""bbox 기하 — 핸들 위치와 히트 판정 (그리기·편집이 같은 정의를 쓴다).

핸들을 **그리는 쪽**과 **잡는 쪽**이 좌표를 따로 계산하면 보이는 곳과 잡히는 곳이 어긋난다. 그래서
코너·변 중점의 정의는 여기 한 곳에 둔다.
"""
from __future__ import annotations


def rect_from(a: tuple[int, int], b: tuple[int, int]) -> list[int]:
    """두 점을 정규화된 ``[x0, y0, x1, y1]`` 로 (어느 방향으로 끌든 x0<x1, y0<y1)."""
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]


def corners(bbox) -> list[tuple[int, int]]:
    """네 코너 — 좌상·우상·우하·좌하 (**시계방향** — 반대 코너 = ``(i+2) % 4``)."""
    _x0, _y0, _x1, _y1 = (int(round(float(_v))) for _v in bbox)
    return [(_x0, _y0), (_x1, _y0), (_x1, _y1), (_x0, _y1)]


def edge_midpoints(bbox) -> list[tuple[int, int, str]]:
    """네 변의 중점 ``(x, y, 변 이름)`` — 한 축만 움직이는 핸들."""
    _x0, _y0, _x1, _y1 = (int(round(float(_v))) for _v in bbox)
    _cx, _cy = (_x0 + _x1) // 2, (_y0 + _y1) // 2
    return [(_cx, _y0, "top"), (_x1, _cy, "right"),
            (_cx, _y1, "bottom"), (_x0, _cy, "left")]


def edge_resize(bbox, edge: str, x: int, y: int) -> list[int]:
    """변 중점 드래그 — 잡은 변의 좌표만 커서로 옮긴 새 bbox (나머지 셋은 고정).

    ``top``/``bottom`` 은 y 만, ``left``/``right`` 는 x 만 움직인다. 반대 변을 넘겨도
    ``rect_from`` 이 정규화하므로 뒤집힌 상자가 안 나온다.
    """
    _x0, _y0, _x1, _y1 = (int(round(float(_v))) for _v in bbox)
    if edge == "top":
        _y0 = y
    elif edge == "bottom":
        _y1 = y
    elif edge == "left":
        _x0 = x
    elif edge == "right":
        _x1 = x
    return rect_from((_x0, _y0), (_x1, _y1))


def hit_corner(bbox, x: int, y: int, tolerance: float) -> int | None:
    """허용 반경 안에서 가장 가까운 코너의 인덱스 (없으면 None)."""
    _best, _dist = None, tolerance
    for _i, (_cx, _cy) in enumerate(corners(bbox)):
        _d = ((_cx - x) ** 2 + (_cy - y) ** 2) ** 0.5
        if _d <= _dist:
            _best, _dist = _i, _d
    return _best


def hit_edge(bbox, x: int, y: int, tolerance: float) -> str | None:
    """허용 반경 안에서 가장 가까운 변 중점의 이름 (없으면 None)."""
    _best, _dist = None, tolerance
    for _mx, _my, _edge in edge_midpoints(bbox):
        _d = ((_mx - x) ** 2 + (_my - y) ** 2) ** 0.5
        if _d <= _dist:
            _best, _dist = _edge, _d
    return _best


def inside(bbox, x: int, y: int) -> bool:
    """점이 상자 안에 있나 (캔버스 클릭으로 객체를 고를 때)."""
    if not bbox or len(bbox) != 4:
        return False
    _x0, _y0, _x1, _y1 = (float(_v) for _v in bbox)
    return _x0 <= x <= _x1 and _y0 <= y <= _y1


def area(bbox) -> float:
    """상자 넓이 — 겹친 상자 중 **작은 것을 먼저** 고르기 위한 기준."""
    if not bbox or len(bbox) != 4:
        return 0.0
    _x0, _y0, _x1, _y1 = (float(_v) for _v in bbox)
    return max(0.0, _x1 - _x0) * max(0.0, _y1 - _y0)


def near(a: tuple[int, int], b: tuple[int, int], tolerance: float) -> bool:
    """두 점이 허용 반경 안에 붙어 있나 (다각형 닫기 판정)."""
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 <= tolerance
