"""배경 flood primitive — 배경을 채우고 반전해 객체 mask 를 얻는다.

메커니즘은 LoG 벽 + ``cv2.floodFill`` — *맨 프레임*의 배경을 채운 뒤 반전해 객체를 얻는다. Canny 윤곽을
이어 닫아 채우는 경로와 달리 **edge 를 닫을 필요가 없다** — 배경 쪽에서 흐르다 막히는 곳이 곧 객체
경계이기 때문이다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ...typing import GRAY_IMAGE
from ..cv.filter import Filter_by_area, Make_morph_kernel, log_edges


def Flood_background(
    image: np.ndarray, region: np.ndarray | None = None, *,
    belt_dev: int = 60, tolerance: int = 4, seeds: int = 64,
    log_sigma: float = 1.2, log_factor: float = 1.0, roi_margin: int = 0,
    open_size: int = 1, shrink: int = 0, min_area: int = 0,
) -> GRAY_IMAGE | None:
    """``region`` 안의 배경을 color floodFill 로 채우고 반전해 객체 raw mask 를 만든다.

    기준색은 ``region`` 픽셀의 **중앙값** — 객체는 소수라 median 이 곧 배경색이 된다. 거기서
    ``belt_dev`` 이내이면서 벽이 아닌 픽셀을 seed 로 flood 하고, LoG edge 와 ``region`` 바깥을 벽으로
    심어 객체 안·영역 밖으로 못 새게 한다. 채워지지 않고 남은 곳이 객체다(내부 구멍은 flood 가 닿지
    못해 메워진 solid 로 나온다).

    floodFill 은 **floating range**(이웃 대비)다 — 배경 조명 그래디언트는 이웃 간 차이가 완만해 따라
    흐르고, 객체 경계의 급격한 색 점프에서 멈춘다. seed 색과의 고정 비교(FIXED_RANGE)는 그래디언트
    끝을 못 넘어 배경을 다 못 채운다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)`` (gray 는 BGR 로 승격).
        region: 배경을 찾을 영역 bool ``(H,W)``. None 이면 프레임 전체.
        belt_dev: 기준색 편차(채널 최대) 이내인 픽셀만 seed. 객체는 색이 멀어 제외된다.
        tolerance: floodFill 색 허용치(이웃 대비 ±).
        seeds: ``region`` 에서 고르게 뽑을 seed 표본 수.
        log_sigma: LoG 벽 블러 σ.
        log_factor: LoG edge 임계 배수(클수록 벽이 성겨 더 넓게 채워진다).
        roi_margin: ``region`` 침식 폭(px). 손으로 그린 영역 경계에 걸친 레일·프레임 edge 가 벽이 되어
            테두리를 따라 **가짜 객체 띠**를 만드는 것을 막는다.
        open_size: morphology OPEN 커널(px). 배경에 남은 벽 조각을 털어낸다. ``1`` 이하면 생략.
        shrink: 침식 폭(px). 객체 실루엣의 LoG 벽은 flood 를 못 받아 mask 에 남으므로 그 두께만큼 되돌린다.
        min_area: 이보다 작은 조각은 버린다 (``0`` = 끄기).

    Returns:
        ``(H,W)`` uint8 0/255 객체 mask. 영역·seed·결과가 비면 None.
    """
    _h, _w = image.shape[:2]
    _img = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    _region = np.ones((_h, _w), bool) if region is None else (region > 0)
    if roi_margin:
        _region = cv2.erode(_region.astype(np.uint8), Make_morph_kernel(roi_margin)) > 0
    if not _region.any():
        return None

    _walls = log_edges(_img, sigma=log_sigma, factor=log_factor)
    _ref   = np.median(_img[_region].reshape(-1, 3), axis=0)     # 배경 기준색 (객체는 소수)
    _dev   = np.abs(_img.astype(np.float32) - _ref).max(axis=2)  # 기준색 편차(채널 최대)
    _ys, _xs = np.where(_region & ~_walls & (_dev <= belt_dev))
    if _xs.size == 0:
        return None

    _barrier = np.zeros((_h + 2, _w + 2), np.uint8)              # floodFill mask 규격 (H+2,W+2)
    _barrier[1:-1, 1:-1] = (_walls | ~_region).astype(np.uint8)  # LoG 벽 + 영역 밖 = 못 넘는 경계
    _fill  = _img.copy()                                         # MASK_ONLY 라 안 바뀌지만 방어적 사본
    _lo    = (float(tolerance),) * 3
    _flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
    _idx   = np.linspace(0, _xs.size - 1, min(int(seeds), _xs.size)).astype(int)
    for _i in _idx:
        _x, _y = int(_xs[_i]), int(_ys[_i])
        if _barrier[_y + 1, _x + 1] != 0:                        # 이미 채워졌거나 벽 → 스킵
            continue
        cv2.floodFill(_fill, _barrier, (_x, _y), 0, _lo, _lo, _flags)

    _obj = _region & (_barrier[1:-1, 1:-1] != 255)               # 영역 안에서 안 채워진 곳 = 객체(+벽)
    if open_size > 1:
        _obj = cv2.morphologyEx(_obj.astype(np.uint8), cv2.MORPH_OPEN,
                                Make_morph_kernel(open_size)) > 0
    if shrink:
        _obj = cv2.erode(_obj.astype(np.uint8), Make_morph_kernel(shrink)) > 0
    _out = Filter_by_area(_obj.astype(np.uint8) * np.uint8(255), min_area=min_area)
    return _out if _out.any() else None
