"""LoG edge + color floodFill primitive — 몸통색과 크게 다른 관통부(구멍/슬릿)를 찾는다.

``gui/viewer/_fill.py`` 의 magic-wand 와 **같은 메커니즘**(``cv2.floodFill`` FIXED_RANGE + LoG edge
벽)을 core 로 올린 것(core 는 gui 의존 못 함 — gui 쪽 fill 은 여기 ``log_edges`` 를 재사용). 편집기에서
"몸통과 색이 확 다른 구멍을 눈으로 보고 클릭" 하는 걸 자동화한다.

seed 는 세 기준을 모두 통과해야 한다 — 역할이 서로 다르다:

1. **평균 특이치** (``dev > mean(dev) + k·std(dev)``) — 몸통 평균색 μ_obj 에서 통계적으로 벗어난
   픽셀. 고정 임계는 부품 밝기마다 잡히는 비율이 흔들려 쓰지 않는다(측정: 고정 40 은 5.6~12.4%,
   ``k=2`` 는 3.2~4.4%).
2. **국소 배경색 근접** (``|px - bg_ref| <= bg_tol``) — 특이치 중 *반사광* 을 뺀다. 구멍은 배경이
   비치는 곳이라 배경색과 같고, 정반사는 그렇지 않다. 절대 밝기 임계는 부품 색에 종속돼(흰 부품에서
   붕괴) 쓰지 않고, 채도도 구멍·반사광이 겹쳐 못 가른다. ``bg_ref`` 는 호출 측이 객체 바깥 링에서
   구해 넘긴다 — 부품 색과 무관.
3. **LoG 벽 아님** — 경계 픽셀은 seed 로 삼지 않는다.

flood 는 ``FLOODFILL_FIXED_RANGE`` (seed 색 고정 비교). 몸통의 그림자 그래디언트를 타고 번지면 안 되기
때문 — 반대로 ``mask/flood.py`` 는 배경의 조명 그래디언트를 건너야 해서 floating range 를 쓴다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ....typing import GRAY_IMAGE
from ..cv.filter import log_edges


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


def background_ref(frame_bgr: np.ndarray, mask255: GRAY_IMAGE, ring: int = 25) -> np.ndarray | None:
    """객체 바깥 링의 중앙값 = **국소 배경색**. 구멍은 이 색이 비치는 곳이다.

    mask 를 ``ring`` px 팽창해 얻은 띠에서 median 을 취한다(중앙값이라 띠에 걸린 이웃 객체·그림자에
    끌리지 않는다). 부품 색과 무관한 참조라 흰 부품에서도 성립한다 — 절대 밝기 임계의 대체.

    Args:
        frame_bgr: 프레임 BGR ``(H,W,3)``.
        mask255: 대상 객체 mask (0/비0).
        ring: mask 바깥으로 이만큼 팽창한 띠를 배경 표본으로 쓴다 (px).

    Returns:
        ``(3,)`` float 배경 기준색. 띠가 비면 ``None``.
    """
    _m = mask255 > 0
    _k = 2 * ring + 1
    _band = (cv2.dilate(_m.astype(np.uint8),
                        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_k, _k))) > 0) & ~_m
    if not _band.any():
        return None
    return np.median(frame_bgr[_band].reshape(-1, frame_bgr.shape[2]), axis=0)


def color_holes(frame_bgr: np.ndarray, mask255: GRAY_IMAGE, *,
                bg_ref: np.ndarray, k: float = 2.0, bg_tol: int = 50,
                tolerance: int = 20, sigma: float = 1.2, factor: float = 1.0,
                walls: np.ndarray | None = None, open_size: int = 5,
                grow: int = 2, min_area: int = 50, max_seeds: int = 32) -> GRAY_IMAGE:
    """mask 안에서 **평균 특이치이면서 국소 배경색이고 LoG 벽에 갇힌** 관통부를 구멍(0/255)으로 낸다.

    seed = ``(dev > mean(dev) + k·std(dev))`` ∧ ``(|px - bg_ref| <= bg_tol)`` ∧ ``¬wall``.
    앞 조건이 "몸통과 다른 것"을 뽑고, 뒤 조건이 그중 반사광을 뺀다(모듈 docstring 참조). LoG edge 와
    mask 바깥을 벽으로 심어 부품 밖·이웃 객체로 못 샌다. 남은 작은 flood 는 morphology open 으로 턴다.

    Args:
        frame_bgr: 프레임 BGR ``(H,W,3)``.
        mask255: 대상 객체 mask (0/비0). **단일 객체** — 라벨맵이면 호출 측이 라벨별로 나눠 부른다.
        bg_ref: 국소 배경 기준색 ``(3,)`` (``background_ref``).
        k: 평균 특이치 배수 — 임계 = ``mean(dev) + k·std(dev)``.
        bg_tol: 배경색 근접 허용 (채널 최대차). 이보다 멀면 반사광으로 보고 seed 에서 뺀다.
        tolerance: floodFill 색 허용 (seed 색 대비 ±, FIXED_RANGE).
        sigma: LoG 블러 시그마 (``walls`` 를 주면 안 씀).
        factor: LoG edge 임계 배수 (``walls`` 를 주면 안 씀).
        walls: 미리 구한 LoG 벽 (``(H,W)`` bool). 프레임당 1회 계산해 라벨마다 재사용.
        open_size: morphology OPEN 커널(px) — 작은 flood 제거 (1=끔).
        grow: LoG 벽에 먹힌 경계 밴드 회복(px) — 배경색 픽셀에서만 팽창.
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
    _thr = float(_dev[_m].mean() + k * _dev[_m].std())                          # 평균 특이치 기준치
    _bg  = np.abs(frame_bgr.astype(np.float32) - bg_ref).max(axis=2) <= bg_tol  # 국소 배경색 근접
    _walls = log_edges(frame_bgr, sigma=sigma, factor=factor) if walls is None else walls
    _ys, _xs = np.where(_m & (_dev > _thr) & _bg & ~_walls)
    if _xs.size == 0:
        return _zero

    # floodFill 벽: LoG edge + mask 바깥 (부품 밖·이웃 객체로 못 새게). mask 는 (H+2,W+2) 규격.
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
    if grow > 0:                                                              # 벽에 먹힌 경계 밴드 회복(배경색에서만)
        _g = 2 * grow + 1
        _hole = (cv2.dilate(_hole.astype(np.uint8),
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_g, _g))) > 0) \
                & _m & _bg
    _hole = _drop_small(_hole, min_area)
    return _hole.astype(np.uint8) * np.uint8(255)


def Carve_holes_by_label(
    image: np.ndarray, segment: GRAY_IMAGE, *, walls: np.ndarray,
    k: float = 2.0, bg_tol: int = 50, ring: int = 25, tolerance: int = 20,
    open_size: int = 5, grow: int = 2, min_area: int = 0,
) -> GRAY_IMAGE | None:
    """인스턴스 라벨맵의 **각 라벨 안에서** 관통부(구멍·슬릿)를 빼낸다 (obj_id 보존).

    **라벨별로 도는 것이 핵심이다** — 객체마다 몸통색이 다르므로(같은 프레임에서 μ 가 ``[38,38,30]``
    vs ``[21,22,18]`` 로 관측) 라벨맵을 통째 이진화해 평균 하나로 처리하면 어느 객체에도 맞지 않는
    기준색이 나온다. 벽에 ``~mask_L`` 을 심어 flood 가 이웃 객체로 넘어가지 못하게 한다.

    라벨 바깥 링이 비어 국소 배경색을 못 재면(``background_ref`` → None) 그 라벨은 **carve 없이
    통과**시킨다 — 배경을 모르는 채로 파내면 몸통을 깎을 위험이 있다.

    Args:
        image: 원본 BGR 프레임 ``(H,W,3)``.
        segment: 인스턴스 라벨맵 ``(H,W)`` (픽셀 = obj_id+1, 0 = 배경).
        walls: LoG 벽 bool ``(H,W)``. 프레임당 1회 계산해 넘긴다(라벨마다 다시 구하지 않는다).
        k: 몸통 평균색 편차의 특이치 배수 — 임계 = ``mean(dev) + k·std(dev)``.
        bg_tol: 국소 배경색 근접 허용치. 반사광(배경색과 먼 밝은 점)을 seed 에서 뺀다.
        ring: 국소 배경색 표본으로 쓸 객체 바깥 링 폭(px).
        tolerance: floodFill 색 허용치.
        open_size: 작은 flood 잡티를 터는 OPEN 커널(px).
        grow: LoG 벽에 먹힌 경계 밴드 회복 폭(px).
        min_area: 이보다 작은 구멍 조각은 무시한다.

    Returns:
        구멍이 빠진 라벨맵 ``(H,W)``. 남는 전경이 없으면 None.
    """
    _seg = np.asarray(segment)
    _labels = [_l for _l in np.unique(_seg) if _l != 0]
    if not _labels:
        return None

    _out = np.zeros_like(_seg)
    for _l in _labels:
        _m255 = (_seg == _l).astype(np.uint8) * np.uint8(255)
        _bg = background_ref(image, _m255, ring=ring)
        if _bg is None:                                  # 링이 비면 carve 없이 통과
            _out[_seg == _l] = _l
            continue
        _hole = color_holes(
            image, _m255, bg_ref=_bg, k=k, bg_tol=bg_tol, tolerance=tolerance,
            walls=walls, open_size=open_size, grow=grow, min_area=min_area)
        _out[(_seg == _l) & (_hole == 0)] = _l           # mask_L & ~구멍
    return _out if _out.any() else None
