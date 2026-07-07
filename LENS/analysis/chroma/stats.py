"""픽셀별/전역 robust 통계 + 분산 분해 (within/between)."""

from __future__ import annotations

import numpy as np

from core.pipeline.process.chroma.robust_stats import _robust_mean_std   # 파이프라인과 동일 추정기


def per_pixel_stats(
    hist: np.ndarray, window: int, circular: bool, row_chunk: int | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """픽셀별 (mean, std, n) 맵. n = 픽셀별 총 누산 표본 수(=배경 가시 빈도, 신뢰도).

    ``_robust_mean_std`` 가 leading shape 무관하게 ``(H,W,B)`` 를 한 번에 ``(H,W)`` 로 처리한다.
    800×600급 이미지는 그대로 전체 처리(기본). 풀해상도에서 float64 승격 메모리가 부담되면
    ``row_chunk`` 에 행 수를 줘 블록으로 나눠 계산한다 (None=전체).
    """
    _n = hist.sum(axis=-1).astype(np.float64)

    if row_chunk is None:
        _mean, _std = _robust_mean_std(hist, window, circular)
        return _mean, _std, _n

    _H, _W, _ = hist.shape
    _mean = np.empty((_H, _W), np.float32)
    _std  = np.empty((_H, _W), np.float32)
    for _y0 in range(0, _H, row_chunk):
        _y1 = min(_y0 + row_chunk, _H)
        _m, _sd = _robust_mean_std(hist[_y0:_y1], window, circular)
        _mean[_y0:_y1] = _m
        _std[_y0:_y1]  = _sd
    return _mean, _std, _n


def global_stats(hist: np.ndarray, window: int, circular: bool) -> tuple[float, float]:
    """공간축 합산 → 1-D 히스토그램 → 동일 추정기로 전역 (mean, std) 스칼라 (sample-weighted)."""
    _g = hist.sum(axis=(0, 1), dtype=np.int64)
    _m, _sd = _robust_mean_std(_g, window, circular)
    return float(_m), float(_sd)


def global_robust_from_pixels(
    mean_map: np.ndarray, valid: np.ndarray, window: int, circular: bool, bins: int,
) -> tuple[float, float]:
    """2중 robust(stage-2) — 픽셀별 대표색을 **픽셀당 1표**로 다시 robust 처리한 전역 대표색.

    stage-1(:func:`per_pixel_stats`)이 픽셀마다 시간축 robust mode 로 대표색 ``mean_map`` 을 내면,
    그 값들을 등가중 히스토그램(픽셀당 1표)으로 모아 같은 mode-window 추정기를 한 번 더 건다.

    sample-weighted 인 :func:`global_stats` 와의 차이가 핵심이다 — 고정 위치 객체가 덮은 픽셀은
    매 프레임 누산돼 ``n`` 이 크므로 합산 통계(global_stats)를 오염시키지만, 여기선 그 픽셀도
    **한 표**일 뿐이라 공간 다수(벨트)에 묻힌다. robustness 를 시간축→공간축으로 옮기는 것.

    Returns:
        ``(mean, std)`` — 오염에 강한 전역 대표색 채널값과 그 표준편차.
    """
    _mu = mean_map[valid]
    if _mu.size == 0:
        return 0.0, 0.0
    _votes = np.bincount(
        np.clip(np.round(_mu).astype(np.int64), 0, bins - 1), minlength=bins)
    _m, _sd = _robust_mean_std(_votes, window, circular)
    return float(_m), float(_sd)


def _circular_resultant(
    mean: np.ndarray, weight: np.ndarray, period: int
) -> tuple[float, float]:
    """가중 원형 평균/표준편차(원래 채널 단위). 반환 (circ_mean, circ_std)."""
    _theta = mean.astype(np.float64) * (2.0 * np.pi / period)
    _wsum  = weight.sum()
    if _wsum <= 0:
        return 0.0, 0.0
    _c = (weight * np.cos(_theta)).sum() / _wsum
    _s = (weight * np.sin(_theta)).sum() / _wsum
    _R = min(max(float(np.hypot(_c, _s)), 1e-12), 1.0)
    _mean = (np.arctan2(_s, _c) % (2.0 * np.pi)) * (period / (2.0 * np.pi))
    _std_rad = np.sqrt(-2.0 * np.log(_R))
    return _mean, float(_std_rad * (period / (2.0 * np.pi)))


def variance_partition(
    mean_map: np.ndarray, std_map: np.ndarray, n: np.ndarray,
    circular: bool, period: int, min_count: int,
) -> dict:
    """전체분산을 within(시간)·between(공간)으로 분해한다 (n 가중, 신뢰 픽셀만).

    within  = E[픽셀별 시간분산]  = Σ n·std²  / Σ n
    between = Var[픽셀별 평균]     = (순환 채널이면 원형분산)
    spatial_fraction = between / (within + between) ∈ [0, 1]
    """
    _sel = n >= max(min_count, 1)
    if not _sel.any():
        return {"valid_px": 0}
    _w   = n[_sel]
    _sd  = std_map[_sel].astype(np.float64)
    _mu  = mean_map[_sel].astype(np.float64)
    _wsum = _w.sum()

    _within = float((_w * _sd * _sd).sum() / _wsum)

    if circular:
        _gmean, _cstd = _circular_resultant(_mu, _w, period)
        _between = float(_cstd * _cstd)
        _mean_spread = _cstd
    else:
        _gmean   = float((_w * _mu).sum() / _wsum)
        _between = float((_w * (_mu - _gmean) ** 2).sum() / _wsum)
        _mean_spread = float(np.sqrt(_between))

    _total = _within + _between
    return {
        "valid_px":         int(_sel.sum()),
        "within_std":       float(np.sqrt(_within)),
        "between_std":      _mean_spread,
        "spatial_fraction": (_between / _total) if _total > 0 else 0.0,
        "weighted_mean":    _gmean,
        "median_pixel_std": float(np.median(std_map[_sel])),
    }
