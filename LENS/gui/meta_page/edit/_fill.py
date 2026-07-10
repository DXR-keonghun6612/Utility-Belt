"""magic-wand 채우기 — 색 유사 flood fill + LoG(Laplacian of Gaussian) edge 경계.

클릭 seed 에서 색이 비슷한 인접 영역을 채우되, LoG 로 검출한 edge 를 **벽**으로 삼아 경계를
또렷하게 막는다(색 허용오차만으로는 번지는 곳을 edge 가 잘라준다). ``cv2.floodFill`` 의 mask
인자에 LoG edge 를 미리 심어 두 기준(색 유사 + edge)을 한 번에 적용한다.

순수 함수(Qt 비의존) — editor 가 base 이미지·seed·허용오차를 넘긴다.
"""

from __future__ import annotations

import cv2
import numpy as np

from core.process.func.cv.filter import log_edges


def magic_wand(
    image: np.ndarray,
    seed: tuple[int, int],
    tolerance: int,
    radius: int,
    *,
    log_sigma: float = 1.2,
    log_factor: float = 1.0,
    grow: int = 2,
) -> np.ndarray | None:
    """seed 중심 ``radius`` 원 안에서 색 유사 + LoG edge 경계까지 채운 이진 영역을 만든다.

    채우기 범위는 **클릭점 중심 ``radius`` 원(ROI)** 으로 제한한다(원 밖은 벽). 그 안에서 색 기준은
    seed 픽셀 값 대비 ±``tolerance``(고정 범위)이고, LoG edge 픽셀을 벽으로 더해 경계를 넘지 못하게
    한다. LoG 임계는 이미지마다 다르므로 LoG 표준편차에 비례해 적응적으로 잡는다(``log_factor``).

    Args:
        image: base BGR 이미지 ``(H, W, 3)`` uint8.
        seed: 시작점(원 중심) ``(x, y)`` 원본 픽셀.
        tolerance: 색 허용오차 (seed 색 기준 채널별 ±). 클수록 넓게 번진다.
        radius: 채우기 원형 ROI 반지름(px) — 편집기 '굵기' 값. 원 밖은 채우지 않는다.
        log_sigma: LoG 가우시안 시그마 (블러 정도).
        log_factor: LoG edge 임계 = ``log_factor × LoG 표준편차`` (클수록 벽이 성겨 더 넓게 채움).
        grow: 채운 뒤 팽창할 px (0=끔). LoG edge 는 경계에 '띠'로 잡혀 채움이 그 안쪽에서 멈추므로,
            띠 폭 절반만큼 되찾아 경계에 붙인다. ROI 원 밖으론 넘지 않게 클램프한다.

    Returns:
        ``(H, W)`` uint8 (0/1) 채운 영역. seed 가 범위 밖이거나 채운 게 없으면 ``None``.
    """
    _h, _w = image.shape[:2]
    _x, _y = int(seed[0]), int(seed[1])
    if not (0 <= _x < _w and 0 <= _y < _h):
        return None

    # LoG edge: 가우시안 블러 후 라플라시안, |응답| 이 큰 곳 = 경계 (적응적 임계; core util 공용).
    _edges = log_edges(image, sigma=log_sigma, factor=log_factor).astype(np.uint8)   # 1 = LoG edge (벽)

    # 원형 ROI: 클릭점 중심 radius 원 밖은 벽으로 심어 채우기를 그 원 안으로 가둔다.
    _roi = np.zeros((_h, _w), np.uint8)
    cv2.circle(_roi, (_x, _y), max(1, int(radius)), 1, -1)
    _edges = np.where(_roi > 0, _edges, np.uint8(1))      # 원 밖 = 벽

    # floodFill mask 는 (H+2, W+2) — 미리 벽(edge+원밖)을 심고, seed 는 해제(edge 위 클릭 대비).
    _mask = np.zeros((_h + 2, _w + 2), np.uint8)
    _mask[1:-1, 1:-1] = _edges
    _mask[_y + 1, _x + 1] = 0

    _t = int(tolerance)
    _flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    # MASK_ONLY 라 이미지는 안 바뀌지만, 단일 base 는 캐시 배열이라 방어적으로 사본을 넘긴다.
    cv2.floodFill(image.copy(), _mask, (_x, _y), 0, (_t, _t, _t), (_t, _t, _t), _flags)

    _filled = (_mask[1:-1, 1:-1] == 255).astype(np.uint8)
    if not _filled.any():
        return None
    if grow > 0:
        # LoG edge 띠 안쪽에서 멈춘 채움을 띠 폭 절반만큼 팽창해 경계에 붙인다 (원 밖은 자름).
        _kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1))
        _filled = cv2.dilate(_filled, _kernel) & _roi
    return _filled if _filled.any() else None
