"""LoG edge + color floodFill primitive — 몸통색과 크게 다른 관통부(구멍/슬릿)를 찾는다.

``gui/verify/_fill.py`` 의 magic-wand 와 **같은 메커니즘**(``cv2.floodFill`` FIXED_RANGE + LoG edge
벽)을 core 로 올린 것(core 는 gui 의존 못 함 — gui 쪽 fill 은 여기 ``log_edges`` 를 재사용). 편집기에서
"몸통과 색이 확 다른 구멍을 눈으로 보고 클릭" 하는 걸 자동화한다: **mask 영역 평균색 μ_obj 에서 크게
벗어난** 픽셀을 seed 로 ``cv2.floodFill`` 하고, 반사광처럼 작게 채워진 것은 morphology 로 턴다.
LoG 는 벽(경계), color 는 flood 기준.
"""

from __future__ import annotations

import cv2
import numpy as np

from .._base import GRAY_IMAGE


def log_edges(image: np.ndarray, *, sigma: float = 1.2, factor: float = 1.0) -> np.ndarray:
    """이미지 → LoG(Laplacian of Gaussian) edge 벽 (bool).

    가우시안 블러 후 Laplacian, ``|응답|`` 이 큰 곳 = 경계. 임계는 이미지마다 다르므로 LoG 표준편차에
    비례해 적응적으로 잡는다(``factor``). fill 의 색 유사 성분이 이 벽을 못 넘게 막는 데 쓴다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)``.
        sigma: 가우시안 블러 시그마.
        factor: edge 임계 = ``factor × LoG 표준편차`` (클수록 벽이 성김).

    Returns:
        ``(H,W)`` bool — True = LoG edge(벽).
    """
    _gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    _blur = cv2.GaussianBlur(_gray, (0, 0), sigma)
    _log  = cv2.Laplacian(_blur.astype(np.float32), cv2.CV_32F, ksize=3)
    _thr  = max(1.0, factor * float(np.std(_log)))
    return np.abs(_log) > _thr


def _drop_small(mask_bool: np.ndarray, min_area: int) -> np.ndarray:
    """``min_area`` 미만 연결성분을 제거한다 (0=무시)."""
    if min_area <= 0:
        return mask_bool
    _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(mask_bool.astype(np.uint8))
    _keep = np.zeros(mask_bool.shape, bool)
    for _i in range(1, _n):
        if int(_stats[_i, cv2.CC_STAT_AREA]) >= min_area:
            _keep |= _lbl == _i
    return _keep


def color_holes(frame_bgr: np.ndarray, mask255: GRAY_IMAGE, *,
                dev_thr: int = 40, tolerance: int = 20,
                sigma: float = 1.2, factor: float = 1.0,
                highlight_thr: float = 0.0, open_size: int = 5,
                grow: int = 2, min_area: int = 50, max_seeds: int = 32) -> GRAY_IMAGE:
    """mask 안에서 **몸통 평균색과 크게 다르고 LoG 벽에 갇힌** 관통부를 구멍(0/255)으로 낸다.

    편집기 fill 과 같은 ``cv2.floodFill``(FIXED_RANGE + LoG 벽). 기준색은 mask 영역 평균 μ_obj —
    거기서 ``dev_thr`` 이상 벗어난 mask 내부 픽셀(색이 확 다른 = 구멍/반사 후보)을 seed 로 floodFill
    한다("몸통과 색이 다른 구멍을 눈으로 보고 클릭" 의 자동판). 반사광은 (1) RGB 평균이
    ``highlight_thr`` 이상이면 seed 에서 제외하고, (2) 그래도 남으면 floodFill 영역이 작으므로
    morphology open(``open_size``)으로 턴다. LoG edge·mask 바깥을 벽으로 심어 부품 밖으로 못 샌다.

    Args:
        frame_bgr: 프레임 BGR ``(H,W,3)``.
        mask255: 대상 mask (0/비0).
        dev_thr: seed 판정 — 몸통 평균색에서 이보다 크게 벗어난 픽셀만 seed (채널 최대차).
        tolerance: floodFill 색 허용 (seed 색 대비 ±).
        sigma: LoG 블러 시그마.
        factor: LoG edge 임계 배수.
        highlight_thr: 반사광 필터 — RGB 평균이 이 값 이상인 픽셀을 seed 에서 제외 (0=끔).
        open_size: morphology OPEN 커널(px) — 작은 flood(반사광 등) 제거 (1=끔).
        grow: LoG 벽에 먹힌 경계 밴드 회복(px) — 몸통색 밖에서만 팽창.
        min_area: 이보다 작은 구멍 조각 제거.
        max_seeds: floodFill seed 표본 상한(고르게 표본).

    Returns:
        ``(H,W)`` uint8 (0/255) 구멍 mask.
    """
    _zero = np.zeros(mask255.shape[:2], np.uint8)
    _m = mask255 > 0
    if not _m.any():
        return _zero
    _h, _w = _m.shape

    _mu  = frame_bgr[_m].reshape(-1, frame_bgr.shape[2]).mean(axis=0)           # 몸통 평균색 μ_obj
    _dev = np.abs(frame_bgr.astype(np.float32) - _mu).max(axis=2)               # μ_obj 편차(채널 최대)
    _walls = log_edges(frame_bgr, sigma=sigma, factor=factor)
    _seedable = _m & (_dev > dev_thr) & ~_walls                                # 몸통색과 확 다름 + 벽 아님
    if highlight_thr > 0:                                                       # 반사광 제거: RGB 평균 밝기 임계 이상 제외
        _bright = frame_bgr.astype(np.float32).mean(axis=2)
        _seedable &= _bright < highlight_thr
    _ys, _xs = np.where(_seedable)
    if _xs.size == 0:
        return _zero

    # floodFill 벽: LoG edge + mask 바깥 (부품 밖·경계 너머로 못 새게). mask 는 (H+2,W+2) 규격.
    _barrier = np.zeros((_h + 2, _w + 2), np.uint8)
    _barrier[1:-1, 1:-1] = (_walls | ~_m).astype(np.uint8)
    _img   = frame_bgr.copy()                                                   # MASK_ONLY 라 안 바뀌지만 방어적 사본
    _lo    = (float(tolerance),) * 3
    _flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    _idx   = np.linspace(0, _xs.size - 1, min(int(max_seeds), _xs.size)).astype(int)
    for _i in _idx:                                                            # 편집기와 같은 cv2.floodFill
        _x, _y = int(_xs[_i]), int(_ys[_i])
        if _barrier[_y + 1, _x + 1] != 0:                                     # 이미 채워졌거나 벽 → 스킵
            continue
        cv2.floodFill(_img, _barrier, (_x, _y), 0, _lo, _lo, _flags)

    _hole = (_barrier[1:-1, 1:-1] == 255) & _m                                  # 채워진 곳 = 구멍
    if open_size > 1:                                                          # 작은 flood(반사광 등) 제거
        _hole = cv2.morphologyEx(_hole.astype(np.uint8), cv2.MORPH_OPEN,
                                 np.ones((open_size, open_size), np.uint8)) > 0
    if grow > 0:                                                              # 벽에 먹힌 경계 밴드 회복(몸통 밖에서만)
        _k = 2 * grow + 1
        _hole = (cv2.dilate(_hole.astype(np.uint8),
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_k, _k))) > 0) \
                & (_m & (_dev > tolerance))
    _hole = _drop_small(_hole, min_area)
    return _hole.astype(np.uint8) * np.uint8(255)
