"""인스턴스 primitive — 이진 mask ↔ 인스턴스 라벨맵·bbox 목록.

연결 요소 분할(``Split_components``)·중심 기준 정렬(``Order_by_center``)의 순수 계산. 입출력은
배열과 박스 리스트뿐이라 저장 표현(``Data_Ref``)이나 store 를 모른다 — 객체 컨테이너 조립은 이 계산을
쓰는 ``stream/mask`` 유닛의 몫이다.

라벨맵 규약: ``(H, W)`` uint8, **픽셀값 = 인스턴스 인덱스 + 1**, ``0`` = 배경.
"""

from __future__ import annotations

import cv2
import numpy as np

from ...typing import GRAY_IMAGE
from ..cv.filter import Make_morph_kernel
from ..cv.geom import Box_center, Center_offset

BOX = list[float]


# ── 객체 id ↔ 라벨맵 픽셀값 규약 + 합성 (이 파일이 단일 소유) ─────────────────────
# 정본은 per-obj mask 를 안 들고 frame-level 라벨맵 **한 장**에 담으며, 그 픽셀값이 곧 ``id + 1`` 이다
# (0 = 배경). 즉 id 는 트리 key 이자 라벨맵 픽셀값이라 트리와 payload 가 공동소유한다. 이 변환과 그 위의
# 합성(gather/scatter)을 소비처마다 손으로 쓰면(``int(id)+1``) 흩어지므로 전부 여기서 소유한다 —
# gui·process·export(해체 후)가 이 함수들만 부르고, 라벨 산수를 다시 짓지 않는다.

def Obj_label(obj_id: str | int) -> int:
    """객체 id → 라벨맵 픽셀값 (``id + 1``; 0 은 배경). id 가 정수가 아니면 실패한다.

    id 가 정수인 것은 store(``Add_branch``)가 강제한다 — 라벨맵에 앉을 자리가 그 정수라, 정수가
    아니면 규약이 이미 깨진 것이다. 여기서 방어하지 않고 ``int`` 이 터지게 둔다(조용한 기본값 없음).
    """
    return int(obj_id) + 1


def Obj_id_of(label: int) -> str:
    """라벨맵 픽셀값 → 객체 id (``Obj_label`` 의 역). 배경(0) 여부는 호출 측이 거른다."""
    return str(int(label) - 1)


def Mask_of(segment: np.ndarray, obj_id: str | int) -> np.ndarray:
    """라벨맵에서 한 객체의 이진 mask ``(H, W) uint8`` 을 뽑는다 (gather 한 조각).

    정본은 per-obj mask 를 저장하지 않고 이 라벨맵 한 장에서 파생한다 — 픽셀값이 ``Obj_label(obj_id)``
    인 영역이 그 객체다. crop·export 가 이걸로 객체 픽셀을 얻는다.
    """
    return (segment == Obj_label(obj_id)).astype(np.uint8)


def Paint(segment: np.ndarray, obj_id: str | int, mask: np.ndarray) -> None:
    """객체의 mask 영역을 라벨맵에 그 객체의 라벨로 **제자리 도색**한다 (scatter 한 조각).

    호출 측이 든 배열을 그대로 고친다 — 편집 중 붓질처럼 디스크보다 새 상태라, 여기서 저장하지 않는다.
    """
    segment[mask > 0] = np.uint8(Obj_label(obj_id))


def Erase(segment: np.ndarray, obj_id: str | int) -> None:
    """라벨맵에서 한 객체의 라벨을 배경(0)으로 지운다 (제자리). 없는 라벨이면 무연산."""
    segment[segment == Obj_label(obj_id)] = 0


def Compose(shape: tuple[int, int], objects: dict[str, np.ndarray]) -> np.ndarray:
    """객체별 mask ``{id: mask}`` 를 인스턴스 라벨맵 한 장으로 합친다 (scatter 전체).

    ``shape`` = (H, W). 라벨맵은 픽셀당 라벨 하나라 배타적이므로 겹치면 나중 id 가 이긴다. 빈 dict 면 영배열.
    """
    _seg = np.zeros(shape, np.uint8)
    for _id, _m in objects.items():
        Paint(_seg, _id, _m)
    return _seg


def Merge_into(segment: np.ndarray, into: str | int, others: list[str]) -> None:
    """``others`` 의 라벨을 ``into`` 의 라벨로 **제자리 재도색**한다 (합치기 = 라벨 재도색).

    라벨맵은 픽셀당 라벨 하나라 배타적이라, 재도색이 곧 mask 합집합이다(겹침이 없다). ``into`` 자신은
    그대로 둔다. bbox 합집합·컨테이너 정리는 이 함수가 아니라 store 몫(라벨맵 밖 데이터).
    """
    _dst = np.uint8(Obj_label(into))
    for _o in others:
        segment[segment == Obj_label(_o)] = _dst


def Box_center_distance(a: BOX, b: BOX) -> float:
    """두 bbox(XYXY) 중심점 사이 유클리드 거리."""
    _ax, _ay = Box_center(a)
    _bx, _by = Box_center(b)
    return ((_ax - _bx) ** 2 + (_ay - _by) ** 2) ** 0.5


def Scale_box(box: BOX, ratio: float, w: int, h: int) -> BOX:
    """bbox 를 ``ratio`` 비율로 확대/축소하고 이미지 범위 ``[0,w]×[0,h]`` 로 클램프한다.

    Args:
        box: ``[x0, y0, x1, y1]`` (XYXY).
        ratio: 원본 대비 비율. ``0.1`` = 10% 확대, ``-0.1`` = 축소, ``0`` = 무연산.
        w: 이미지 너비 (클램프 상한).
        h: 이미지 높이 (클램프 상한).

    Returns:
        클램프된 ``[x0, y0, x1, y1]`` float 리스트.
    """
    _x0, _y0, _x1, _y1 = box
    if ratio:
        _dx = (_x1 - _x0) * ratio / 2.0
        _dy = (_y1 - _y0) * ratio / 2.0
        _x0, _x1 = _x0 - _dx, _x1 + _dx
        _y0, _y1 = _y0 - _dy, _y1 + _dy
    return [float(min(max(_x0, 0.0), w)), float(min(max(_y0, 0.0), h)),
            float(min(max(_x1, 0.0), w)), float(min(max(_y1, 0.0), h))]


def Cluster_by_center(boxes: list[BOX], gap: float) -> list[list[int]]:
    """중심점 거리가 ``gap`` 이하인 bbox 끼리 union-find 로 묶어 인덱스 그룹을 만든다.

    끊어진 조각(같은 부품의 분리된 컴포넌트)을 한 인스턴스로 되붙이는 자리다. 조각의 **형태는 건드리지
    않고** 소속만 합치므로, 라벨맵에는 같은 id 가, bbox 에는 합집합이 남는다.

    Args:
        boxes: bbox 리스트 (XYXY).
        gap: 병합 임계 거리(px). ``0`` 이하면 병합하지 않는다(각자 단독 그룹).

    Returns:
        인덱스 그룹 리스트. 병합이 없으면 각 원소가 단일 인덱스 그룹.
    """
    _parent = list(range(len(boxes)))

    def _find(_x: int) -> int:
        while _parent[_x] != _x:
            _parent[_x] = _parent[_parent[_x]]
            _x = _parent[_x]
        return _x

    if gap > 0:
        for _i in range(len(boxes)):
            for _j in range(_i + 1, len(boxes)):
                if Box_center_distance(boxes[_i], boxes[_j]) <= gap:
                    _parent[_find(_i)] = _find(_j)

    _groups: dict[int, list[int]] = {}
    for _i in range(len(boxes)):
        _groups.setdefault(_find(_i), []).append(_i)
    return list(_groups.values())


def Split_components(
    mask: GRAY_IMAGE, *, min_area: int = 0, merge_gap: float = 0.0, bbox_gap: float = 0.0,
    cut: np.ndarray | None = None, cut_grow: int = 1,
) -> tuple[np.ndarray, list[BOX]]:
    """이진 mask 를 연결 요소로 쪼개 ``(인스턴스 라벨맵, bbox 목록)`` 을 만든다.

    ``connectedComponents`` 한 패스로 라벨맵과 요소별 bbox 를 함께 얻는다 — 객체별 mask 를 따로 들지
    않으므로 인스턴스 수에 비례한 배열 복제가 없다. ``merge_gap`` 병합은 라벨맵 픽셀을 재칠하지 않고
    같은 id 를 부여하는 방식이라 조각 형태가 보존된다.

    ``cut`` 을 주면 그 edge 를 mask 에서 빼고 나서 연결 요소를 센다 — 경계로 닿아 한 덩어리로 붙어
    나온 객체를 그 사이 edge(Canny 등)를 따라 갈라낸다. edge 는 한 픽셀 선이라 목을 못 끊을 수 있어
    ``cut_grow`` 로 살짝 부풀린다. 산출물의 쓰임이 실루엣이 아니라 객체별 **bbox** 라면 이 얇은 절단
    틈은 무해하다(뒤 단계가 box 로 다시 그린다).

    Args:
        mask: 이진 mask ``(H, W)`` (0 = 배경).
        min_area: 이 면적(px²) 미만 컴포넌트는 잡음으로 버린다.
        merge_gap: bbox 중심 거리가 이 값 이하인 컴포넌트를 한 인스턴스로 묶는다(``0`` = 끄기).
        bbox_gap: 최종 bbox 확대/축소 비율 (``Scale_box``).
        cut: 붙은 객체를 가를 edge ``(H, W)`` (mask 에서 빼서 목을 끊는다). None 이면 절단 없음.
        cut_grow: ``cut`` 팽창 폭(px) — edge 선을 이만큼 부풀려 확실히 끊는다.

    Returns:
        ``(segment, boxes)`` — ``segment`` 는 ``(H, W)`` uint8 라벨맵(픽셀 = 인덱스+1, 0 = 배경),
        ``boxes`` 는 인스턴스별 XYXY bbox. 살아남은 컴포넌트가 없으면 ``(빈 라벨맵, [])``.
    """
    _bin = (mask > 0).astype(np.uint8)
    if cut is not None:                                     # edge 를 따라 붙은 객체 절단
        _edge = (cut > 0).astype(np.uint8)
        if cut_grow > 0:
            _edge = cv2.dilate(_edge, Make_morph_kernel(cut_grow))
        _bin = _bin & (_edge == 0)
    _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(_bin, connectivity=8)
    _ih, _iw = _lbl.shape[:2]

    _comps: list[tuple[int, BOX]] = []          # (라벨, bbox)
    for _i in range(1, _n):                     # 0 = 배경 라벨
        if int(_stats[_i, cv2.CC_STAT_AREA]) < min_area:
            continue
        _x = int(_stats[_i, cv2.CC_STAT_LEFT])
        _y = int(_stats[_i, cv2.CC_STAT_TOP])
        _w = int(_stats[_i, cv2.CC_STAT_WIDTH])
        _h = int(_stats[_i, cv2.CC_STAT_HEIGHT])
        _comps.append((_i, [float(_x), float(_y), float(_x + _w), float(_y + _h)]))

    _seg = np.zeros(_lbl.shape, dtype=np.uint8)
    if not _comps:
        return _seg, []

    _boxes: list[BOX] = []
    for _grp in Cluster_by_center([_b for _, _b in _comps], merge_gap):
        _idx    = len(_boxes)
        _labels = [_comps[_j][0] for _j in _grp]
        _seg[np.isin(_lbl, _labels)] = np.uint8(Obj_label(_idx))   # 묶인 조각 모두 같은 id
        _grouped = [_comps[_j][1] for _j in _grp]
        _boxes.append(Scale_box(
            [min(_b[0] for _b in _grouped), min(_b[1] for _b in _grouped),
             max(_b[2] for _b in _grouped), max(_b[3] for _b in _grouped)],   # 합집합 bbox
            bbox_gap, _iw, _ih))
    return _seg, _boxes


def Order_by_center(
    shape: tuple[int, int], centers: list[tuple[float, float] | None],
) -> list[int]:
    """인스턴스를 **이미지 중심에서 가까운 순**으로 정렬한 원본 인덱스를 돌려준다.

    순서는 각 인스턴스의 중심점과 이미지 중심 사이 거리(대각선 정규화 ``Center_offset``)로만 정한다 —
    라벨맵을 보지 않으므로 객체가 각자 mask 를 드는 계열에서도 쓴다. 중심점을 mask 무게중심으로 구했든
    bbox 중앙으로 구했든 이 함수는 **점만 본다**(그 판단은 호출 측 몫). ``None``(위치를 못 구한 것)은
    정렬 근거가 없어 드롭한다.

    Args:
        shape: ``(H, W)`` — 거리 기준인 이미지 중심을 얻을 프레임 크기.
        centers: 인스턴스별 중심점 ``(cx, cy)`` (``None`` 이면 드롭).

    Returns:
        가까운 순으로 정렬된 **원본 인덱스** 리스트 (위치 없는 것 제외).
    """
    _ranked = [_i for _i, _c in enumerate(centers) if _c is not None]
    _ranked.sort(key=lambda _i: Center_offset(shape, centers[_i]))
    return _ranked
