"""갇힌 영역 primitive — 장벽(edge)으로 mask 를 절단해 "경계에서 못 닿는" 영역을 찾는다.

윤곽 채움(``Fill_contours``)과 대비되는 접근이다. 채움은 닫힌 윤곽을 **그려서** 안을 메우므로 끊긴
슬릿에 약하고 표면 반사광 edge 가 가짜 윤곽을 만든다. 여기서는 mask 를 edge 로 **자른 뒤 연결성**을
보므로, (1) 얇은 슬릿도 장벽이 되고 (2) 영역을 가두지 못하는 표면 edge 는 몸통에 흡수돼 가짜 구멍이
생기지 않는다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ...typing import GRAY_IMAGE
from ..cv.filter import Make_morph_kernel


def Carve_enclosed(
    mask: GRAY_IMAGE, edge: GRAY_IMAGE, *,
    boundary_margin: int = 3, close_size: int = 5, min_area: int = 0,
) -> np.ndarray | None:
    """``edge`` 로 갇힌 구멍·슬릿을 ``mask`` 에서 도려낸다 (경계-재건).

    mask 를 ``boundary_margin`` 만큼 침식한 안쪽 edge 만 장벽으로 삼는다 — 바깥 띠는 외곽 실루엣이라
    장벽이 되면 몸통 전체가 갇혀버리고, 동시에 그 띠가 "몸통임"을 알리는 **재건 seed** 가 된다.
    장벽으로 자른 뒤 띠에 닿는 연결성분은 몸통, **닿지 못하는 성분이 구멍·슬릿**이다.
    다객체 프레임도 한 번에 처리된다(각 몸통이 자기 띠에 닿으므로).

    Args:
        mask: 이진 mask ``(H,W)`` — 구멍이 메워진 solid.
        edge: 이진 edge ``(H,W)`` — 장벽 후보.
        boundary_margin: 외곽 실루엣 edge 를 빼기 위한 침식 폭(px). ``0`` 이면 침식 없음.
            너무 크면 얇은 부품이 통째로 seed 가 되어 구멍을 못 뚫는다.
        close_size: 내부 edge 의 끊긴 틈을 잇는 CLOSE 커널(px). 틈이 남으면 flood 가 새어 못 뚫는다.
        min_area: 이보다 작은 갇힌 영역은 반사광 잡음으로 보고 되메운다 (``0`` = 끄기).

    Returns:
        구멍이 뚫린 ``(H,W)`` uint8 0/255 mask. 남는 전경이 없으면 None.
    """
    _m = mask > 0
    _interior = (cv2.erode(_m.astype(np.uint8), Make_morph_kernel(boundary_margin)) > 0
                 if boundary_margin else _m)
    _barrier = cv2.morphologyEx(((edge > 0) & _interior).astype(np.uint8),
                                cv2.MORPH_CLOSE, Make_morph_kernel(close_size)) > 0
    _walk = _m & ~_barrier                                 # mask 를 edge 로 절단
    _band = _m & ~_interior                                # 경계 띠(재건 seed)

    _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(_walk.astype(np.uint8))
    _enclosed = np.ones(_n, dtype=bool)
    _enclosed[0] = False                                   # 배경 라벨
    _band_labels = np.unique(_lbl[_band])
    _enclosed[_band_labels[_band_labels > 0]] = False      # 띠에 닿는 성분 = 몸통
    if min_area:                                           # 작은 갇힘 = 반사광 → 되메움
        _enclosed &= _stats[:, cv2.CC_STAT_AREA] >= min_area

    _refined = _m & ~_enclosed[_lbl]
    return (_refined.astype(np.uint8) * 255) if _refined.any() else None
