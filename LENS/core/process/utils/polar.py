"""(r, θ) 극좌표 변환 primitive — mask 를 centroid 기준 radial profile 로.

``analysis/mask/shape/polar.py`` 에서 core 로 옮긴 연산(analysis 도 연산이라 core/process 로 흡수 중).
설계 의도: 원점 기준 각 (h,w) 픽셀의 (r, θ-bin) 을 **사전계산한 LUT** 로 두고, mask 는 centroid 가
캔버스 중심에 오도록 정수 시프트만 한 뒤 LUT 로 매핑한다. 매 mask 마다 hypot/atan2 를 다시 돌리지
않으니(같은 크기 캔버스면 LUT 재사용) 직관적이고 빠르다. resolution(θ bin 수)이 유일한 핵심 인자.

한 θ 에 경계가 여러 번 걸리는 경우(도넛형·centroid 가 빈 공간)를 위해 **최외각 r_outer 와 최내각
r_inner 두 프로파일**을 낸다:
  - 솔리드·star-convex: r_inner ≈ 0 (사실상 한 겹)
  - 도넛/centroid 가 구멍 안: r_inner = 구멍 반경, r_outer = 바깥 반경
두께 t = r_outer - r_inner 가 곧 그 방향의 재료 두께라, 외곽 실루엣이 같아도 중심에 구멍 뚫린 걸
구분한다.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .._base import GRAY_IMAGE


@lru_cache(maxsize=16)
def polar_lut(h: int, w: int, resolution: int) -> tuple[np.ndarray, np.ndarray]:
    """캔버스 ``(h, w)`` 중심을 원점으로 한 픽셀별 ``(r, θ-bin)`` LUT (크기·resolution 별 캐시).

    Returns:
        ``(r, tbin)`` — ``r`` 은 중심으로부터 거리 ``(h,w) float32``, ``tbin`` 은 ``[0, resolution)``
        의 각도 bin ``(h,w) int32`` (θ = atan2(dy, dx), -π 기준 0번 bin).
    """
    _cy, _cx = (h - 1) / 2.0, (w - 1) / 2.0
    _yy, _xx = np.indices((h, w))
    _dy = _yy - _cy
    _dx = _xx - _cx
    _r = np.hypot(_dx, _dy).astype(np.float32)
    _tbin = np.floor((np.arctan2(_dy, _dx) + np.pi) / (2.0 * np.pi) * resolution).astype(np.int32)
    np.clip(_tbin, 0, resolution - 1, out=_tbin)
    return _r, _tbin


def _recenter_to_centroid(mask: np.ndarray) -> np.ndarray:
    """mask 의 centroid 가 캔버스 기하중심에 오도록 정수 시프트(클리핑)한 같은 크기 mask."""
    _ys, _xs = np.nonzero(mask)
    if _ys.size == 0:
        raise ValueError("빈 mask")
    _H, _W = mask.shape
    _sy = int(round((_H - 1) / 2.0 - _ys.mean()))
    _sx = int(round((_W - 1) / 2.0 - _xs.mean()))

    _ny = np.clip(_ys + _sy, 0, _H - 1)
    _nx = np.clip(_xs + _sx, 0, _W - 1)
    _out = np.zeros_like(mask)
    _out[_ny, _nx] = True
    return _out


def mask_to_polar(
    mask: GRAY_IMAGE, resolution: int, fill_gaps: bool = True
) -> tuple[np.ndarray, np.ndarray]:
    """mask → centroid 기준 ``(r_outer, r_inner)`` radial profile, 각 길이 ``resolution``.

    centroid 를 캔버스 중심에 맞춘 뒤 사전계산 LUT(:func:`polar_lut`) 로 각 θ-bin 의 최대/최소 r 을
    모은다. 픽셀이 없는 θ-bin 은 ``NaN`` 이며, ``fill_gaps`` 면 원형 선형보간으로 메운다.

    Args:
        mask: 이진 mask (0/비0).
        resolution: θ bin 수 (각도 해상도).
        fill_gaps: 빈 bin 을 원형 보간으로 채울지.

    Returns:
        ``(r_outer, r_inner)`` — 각각 ``(resolution,) float32``.
    """
    _m = _recenter_to_centroid(mask > 0)
    _r, _tbin = polar_lut(_m.shape[0], _m.shape[1], resolution)

    _sel = _m.ravel()
    _rv = _r.ravel()[_sel]
    _tv = _tbin.ravel()[_sel]

    _omax = np.full(resolution, -np.inf, np.float64)
    _imin = np.full(resolution,  np.inf, np.float64)
    np.maximum.at(_omax, _tv, _rv)
    np.minimum.at(_imin, _tv, _rv)

    _valid = np.isfinite(_omax)
    _outer = np.where(_valid, _omax, np.nan).astype(np.float32)
    _inner = np.where(_valid, _imin, np.nan).astype(np.float32)

    if fill_gaps:
        _outer = fill_circular_nan(_outer)
        _inner = fill_circular_nan(_inner)
    return _outer, _inner


def fill_circular_nan(profile: np.ndarray) -> np.ndarray:
    """원형(주기) 신호의 NaN bin 을 양끝 wrap 선형보간으로 채운다."""
    _p = profile.astype(np.float32).copy()
    _n = _p.size
    _valid = ~np.isnan(_p)
    if _valid.all():
        return _p
    if not _valid.any():
        raise ValueError("모든 θ-bin 이 비어 있음 (NaN)")

    _idx = np.arange(_n)
    _vi = _idx[_valid]
    _vv = _p[_valid]
    # 주기 보간: 유효 인덱스를 앞뒤로 한 주기씩 확장해 wrap 경계를 잇는다
    _ext_i = np.concatenate([_vi - _n, _vi, _vi + _n])
    _ext_v = np.concatenate([_vv, _vv, _vv])
    _p[~_valid] = np.interp(_idx[~_valid], _ext_i, _ext_v)
    return _p
