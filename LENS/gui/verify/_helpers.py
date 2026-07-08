"""verify 공용 헬퍼 — 색 아이콘 + bbox 기하.

다이얼로그·패널·세그먼트 저장이 공유하는 순수 함수만 둔다 (Qt 상태 없음).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPixmap

from core.data.handler import Data_Ref


def _color_icon(color: tuple[int, int, int]) -> QIcon:
    """BGR 색을 12px 정사각 아이콘으로 만든다."""
    _b, _g, _r = color
    _pix = QPixmap(12, 12)
    _pix.fill(QColor(_r, _g, _b))
    return QIcon(_pix)


def _bbox_of(obj: Data_Ref) -> list | None:
    """object(컨테이너) 의 ``info["bbox"]`` 인라인 값(``[x0,y0,x1,y1]``)을 꺼낸다 (없으면 None)."""
    _ref = obj.info.get("bbox")
    if _ref is None:
        return None
    _val = _ref.info.get("value")
    if isinstance(_val, (list, tuple)) and len(_val) == 4:
        return list(_val)
    return None


def _rect_from(a: tuple[int, int], b: tuple[int, int]) -> list[int]:
    """두 점을 좌상단·우하단으로 정규화한 bbox 를 만든다.

    Args:
        a: 한쪽 점 ``(x, y)``.
        b: 반대쪽 점 ``(x, y)``.

    Returns:
        ``[x0, y0, x1, y1]`` (x0<x1, y0<y1).
    """
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]


def _corners(bbox) -> list[tuple[int, int]]:
    """bbox 의 네 코너를 시계방향으로 돌려준다.

    Args:
        bbox: ``[x0, y0, x1, y1]``.

    Returns:
        ``[(x0,y0), (x1,y0), (x1,y1), (x0,y1)]``.
    """
    _x0, _y0, _x1, _y1 = bbox
    return [(_x0, _y0), (_x1, _y0), (_x1, _y1), (_x0, _y1)]


def _edge_midpoints(bbox) -> list[tuple[int, int, str]]:
    """bbox 네 변의 중점을 ``(x, y, edge)`` 로 돌려준다 (edge = top/right/bottom/left).

    코너(양축 리사이즈)와 달리 변 중점은 한 축으로만 움직인다 — top/bottom 은 수직(y0/y1),
    left/right 은 수평(x0/x1)만 옮긴다.

    Args:
        bbox: ``[x0, y0, x1, y1]``.

    Returns:
        ``[(cx,y0,"top"), (x1,cy,"right"), (cx,y1,"bottom"), (x0,cy,"left")]``.
    """
    _x0, _y0, _x1, _y1 = bbox
    _cx, _cy = (_x0 + _x1) / 2, (_y0 + _y1) / 2
    return [
        (int(_cx), int(_y0), "top"),
        (int(_x1), int(_cy), "right"),
        (int(_cx), int(_y1), "bottom"),
        (int(_x0), int(_cy), "left"),
    ]
