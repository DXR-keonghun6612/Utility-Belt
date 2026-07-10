"""per-sample mask → (r, θ) geometry feature vector.

DataLoader worker(CPU)에서 샘플 단위로 실행되는 추출기. **정렬된 mask**(dataloader의
``_prepare_mask``: PCA 주축 수평화 + 좌우질량 180° 모호성 정리, **회전만**)를 전제로, centroid
극좌표 ``(r, θ)`` 프로파일에서 특징을 뽑는다. 정렬로 지워지지 않는 상하 비대칭이 좌우/카이랄
신호로 보존된다.

극좌표 변환은 사전계산 LUT(:func:`_polar_lut`) 기반이다 — mask 를 centroid 가 캔버스 중심에
오도록 정수 시프트한 뒤 픽셀별 ``(r, θ-bin)`` 을 LUT 로 매핑, θ-bin 마다 최외곽/최내곽 r 을 모아
``r_outer``/``r_inner`` 두 프로파일을 낸다(도넛/중공 형상까지 구분). 같은 캔버스면 LUT 재사용.

기본 설정 (num_angles=256, num_fourier=20): 426차원

특징 그룹 및 정규화 전략:
    size            (  7) log1p  — 절대 크기(면적·둘레·주부축·convex·bbox). 스케일 보존.
    ratio           (  5) raw    — 무차원 비율. 이미 [0, ∞).
    position        (  2) slog   — bbox 중심 대비 무게중심 오프셋(부호 있는 물리량).
    chirality       (  2) slog   — 정렬 프레임 좌우/상하 질량 불균형(상하=카이랄 신호).
    moments         (  4) slog*  — 정렬 프레임 3차 central moment (*추출 시 이미 적용).
    radial_outer    (256) log1p  — θ별 최외곽 경계 거리 r_outer(θ) (절대 크기 보존).
    outer_stats     ( 10) log1p  — r_outer 분포 통계.
    outer_fourier_m ( 20) log1p  — r_outer FFT 진폭.
    outer_fourier_p ( 40) raw    — r_outer 위상보정 복소 계수 (실수/허수 인터리브).
    inner_stats     ( 10) log1p  — θ별 최내곽 r_inner(θ) 통계 (중공/도넛 감지).
    inner_fourier_m ( 20) log1p  — r_inner FFT 진폭.
    inner_fourier_p ( 40) raw    — r_inner 위상보정 복소 계수.
    thickness_stats ( 10) log1p  — (r_outer - r_inner) 두께 프로파일 통계.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple

import numpy as np
from scipy.ndimage import binary_fill_holes, label, uniform_filter1d
from skimage.measure import regionprops


# ── 상수 ──────────────────────────────────────────────────────────────────────

FEAT_DIM = 426

# (start, end) — 기본 설정(num_angles=256, num_fourier=20) 고정 슬라이스
FEAT_GROUPS: dict[str, tuple[int, int]] = {
    "size":            (0,   7),
    "ratio":           (7,   12),
    "position":        (12,  14),
    "chirality":       (14,  16),
    "moments":         (16,  20),
    "radial_outer":    (20,  276),
    "outer_stats":     (276, 286),
    "outer_fft_mag":   (286, 306),
    "outer_fft_phase": (306, 346),
    "inner_stats":     (346, 356),
    "inner_fft_mag":   (356, 376),
    "inner_fft_phase": (376, 416),
    "thickness_stats": (416, 426),
}


@dataclass
class ExtractOpts:
    pixel_size:            float = 1.0
    num_angles:            int   = 256
    num_fourier:           int   = 20
    fill_holes:            bool  = True
    use_largest_component: bool  = True
    smooth_window:         int   = 3
    phase_ref_max_k:       int   = 8
    phase_ref_threshold:   float = 1e-3


class SampleFeature(NamedTuple):
    vector: np.ndarray   # (FEAT_DIM,) float64
    names:  list[str]


# ── 정규화 헬퍼 ───────────────────────────────────────────────────────────────

def _slog(x: float | np.ndarray) -> float | np.ndarray:
    """signed log1p: 부호 보존, 동적 범위 압축."""
    return np.sign(x) * np.log1p(np.abs(x))


# ── 전처리 ────────────────────────────────────────────────────────────────────

def _preprocess(mask: np.ndarray, fill_holes: bool, use_largest: bool) -> np.ndarray:
    bw = mask > 0
    if fill_holes:
        bw = binary_fill_holes(bw)
    if use_largest:
        labeled, n = label(bw)
        if n == 0:
            raise ValueError("mask가 비어 있음.")
        sizes = [(labeled == i).sum() for i in range(1, n + 1)]
        bw = labeled == (np.argmax(sizes) + 1)
    if not bw.any():
        raise ValueError("mask가 비어 있음.")
    return bw.astype(bool)


# ── (r, θ) 극좌표 LUT ─────────────────────────────────────────────────────────

@lru_cache(maxsize=16)
def _polar_lut(h: int, w: int, resolution: int) -> tuple[np.ndarray, np.ndarray]:
    """캔버스 ``(h, w)`` 중심 기준 픽셀별 ``(r, θ-bin)`` LUT (크기·resolution 별 캐시)."""
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    yy, xx = np.indices((h, w))
    dy, dx = yy - cy, xx - cx
    r    = np.hypot(dx, dy).astype(np.float32)
    tbin = np.floor((np.arctan2(dy, dx) + np.pi) / (2.0 * np.pi) * resolution).astype(np.int32)
    np.clip(tbin, 0, resolution - 1, out=tbin)
    return r, tbin


def _recenter_to_centroid(bw: np.ndarray) -> np.ndarray:
    """centroid 가 캔버스 기하중심에 오도록 정수 시프트(클리핑)한 같은 크기 mask."""
    ys, xs = np.nonzero(bw)
    if ys.size == 0:
        raise ValueError("mask가 비어 있음.")
    H, W = bw.shape
    sy = int(round((H - 1) / 2.0 - ys.mean()))
    sx = int(round((W - 1) / 2.0 - xs.mean()))
    ny = np.clip(ys + sy, 0, H - 1)
    nx = np.clip(xs + sx, 0, W - 1)
    out = np.zeros_like(bw)
    out[ny, nx] = True
    return out


def _fill_circular_nan(profile: np.ndarray) -> np.ndarray:
    """원형(주기) 신호의 NaN bin 을 양끝 wrap 선형보간으로 채운다."""
    p = profile.astype(np.float64).copy()
    n = p.size
    valid = ~np.isnan(p)
    if valid.all():
        return p
    if not valid.any():
        raise ValueError("모든 θ-bin 이 비어 있음 (NaN).")
    idx = np.arange(n)
    vi, vv = idx[valid], p[valid]
    ext_i = np.concatenate([vi - n, vi, vi + n])
    ext_v = np.tile(vv, 3)
    p[~valid] = np.interp(idx[~valid], ext_i, ext_v)
    return p


def _mask_to_polar(bw: np.ndarray, resolution: int, px: float) -> tuple[np.ndarray, np.ndarray]:
    """정렬된 mask → centroid 기준 ``(r_outer, r_inner)`` radial profile (각 resolution 길이, px 단위)."""
    m = _recenter_to_centroid(bw)
    r, tbin = _polar_lut(m.shape[0], m.shape[1], resolution)

    sel = m.ravel()
    rv  = r.ravel()[sel]
    tv  = tbin.ravel()[sel]

    omax = np.full(resolution, -np.inf, np.float64)
    imin = np.full(resolution,  np.inf, np.float64)
    np.maximum.at(omax, tv, rv)
    np.minimum.at(imin, tv, rv)

    valid = np.isfinite(omax)
    outer = np.where(valid, omax, np.nan)
    inner = np.where(valid, imin, np.nan)
    return _fill_circular_nan(outer) * px, _fill_circular_nan(inner) * px


# ── region props (크기·비율 스칼라) ───────────────────────────────────────────

def _region_scalars(bw: np.ndarray, px: float) -> dict:
    p            = regionprops(bw.astype(np.uint8))[0]
    area         = p.area * px ** 2
    perimeter    = p.perimeter * px
    cy_px, cx_px = p.centroid
    r0, c0, r1, c1 = p.bbox
    bbox_w       = (c1 - c0) * px
    bbox_h       = (r1 - r0) * px
    bbox_area    = bbox_w * bbox_h
    bbox_cx      = (c0 + (c1 - c0) / 2.0) * px
    bbox_cy      = (r0 + (r1 - r0) / 2.0) * px
    major        = p.axis_major_length * px
    minor        = p.axis_minor_length * px
    convex_area  = p.area_convex * px ** 2

    def _d(a, b): return 0.0 if abs(b) < np.finfo(float).eps else a / b

    return dict(
        area=area, perimeter=perimeter,
        cx=cx_px * px, cy=cy_px * px,
        bbox_w=bbox_w, bbox_h=bbox_h, major=major, minor=minor, convex_area=convex_area,
        bbox_aspect=_d(bbox_w, bbox_h),
        axis_ratio=_d(major, minor),
        extent=_d(area, bbox_area),
        solidity=_d(area, convex_area),
        circularity=_d(4 * np.pi * area, perimeter ** 2),
        centroid_dx=(cx_px * px) - bbox_cx,
        centroid_dy=(cy_px * px) - bbox_cy,
    )


# ── 정렬 프레임 비대칭·모멘트 ─────────────────────────────────────────────────
# 정렬된 mask 이므로 image frame == PCA(정렬) frame. centroid 기준 부호로 산출한다.

def _chirality(bw: np.ndarray, cx: float, cy: float, px: float, pa: float) -> tuple[float, float]:
    """정렬 프레임 좌우/상하 질량 불균형 ``(lr, ud)`` — 상하가 카이랄(거울상 부호 반전) 신호."""
    rows, cols = np.nonzero(bw)
    x = cols.astype(np.float64) * px
    y = rows.astype(np.float64) * px
    lr = (np.sum(x >= cx) - np.sum(x < cx)) * pa
    ud = (np.sum(y >= cy) - np.sum(y < cy)) * pa
    return float(lr), float(ud)


def _signed_moments(bw: np.ndarray, cx: float, cy: float, px: float, pa: float) -> tuple:
    """정렬 프레임 3차 central moment ``(mu30, mu03, mu21, mu12)`` — slog 기적용."""
    rows, cols = np.nonzero(bw)
    dx = cols.astype(np.float64) * px - cx
    dy = rows.astype(np.float64) * px - cy
    return tuple(_slog(np.sum(arr) * pa) for arr in (dx**3, dy**3, dx**2 * dy, dx * dy**2))


# ── 프로파일 통계 · 평활 ──────────────────────────────────────────────────────

def _smooth(x: np.ndarray, win: int) -> np.ndarray:
    win = max(1, int(round(win)))
    if win <= 1:
        return x.copy()
    pad = win // 2
    return uniform_filter1d(
        np.concatenate([x[-pad:], x, x[:pad]]), size=win, mode='nearest'
    )[pad:pad + len(x)]


def _profile_stats(r: np.ndarray) -> tuple:
    """mean/std/min/max/range + 백분위(10·25·50·75·90)."""
    q = np.percentile(r, [10, 25, 50, 75, 90], method='linear')
    return (float(r.mean()), float(r.std()),
            float(r.min()),  float(r.max()),  float(r.max() - r.min()),
            float(q[0]), float(q[1]), float(q[2]), float(q[3]), float(q[4]))


def _stat_names(prefix: str) -> list[str]:
    return [f"{prefix}_{s}" for s in
            ("mean", "std", "min", "max", "range", "p10", "p25", "p50", "p75", "p90")]


# ── Fourier (위상 정규화) ──────────────────────────────────────────────────────

def _fourier(profile, N, K, ref_max_k, ref_thr) -> tuple[np.ndarray, np.ndarray, int]:
    """주기 프로파일 → magnitude + 위상보정 복소 계수(실/허 인터리브).

    저차 harmonic 중 dominant 한 ``k0`` 의 위상으로 기준각을 잡아 모든 harmonic 을
    ``exp(-i·k·phi0)`` 회전 → 잔여 circular shift(회전)에 불변. magnitude 는 위상 무관이라 그대로.
    """
    R   = np.fft.fft(profile.astype(np.float64))
    K   = min(K, N // 2 - 1)
    mag = np.abs(R[1:K + 1]) / N
    ref_k   = min(ref_max_k, K)
    eng_low = np.sum(np.abs(R[1:ref_k + 1]))
    k0  = 1 if np.abs(R[1]) > ref_thr * max(eng_low, np.finfo(float).eps) \
        else int(np.argmax(np.abs(R[1:ref_k + 1]))) + 1
    phi0  = np.angle(R[k0]) / k0
    ks    = np.arange(1, K + 1, dtype=np.float64)
    Zk    = R[1:K + 1] * np.exp(-1j * ks * phi0) / N
    phase = np.empty(2 * K, dtype=np.float64)
    phase[0::2] = Zk.real
    phase[1::2] = Zk.imag
    return mag, phase, K


# ── 그룹별 조립 ───────────────────────────────────────────────────────────────

def _assemble(
    props, chirality, moments, outer,
    outer_stats, inner_stats, thick_stats,
    o_mag, o_phase, i_mag, i_phase, N, K,
) -> tuple[np.ndarray, list[str]]:
    # radial_outer 만 raw 프로파일로 싣는다(inner 는 대부분 0 → stats/fourier 로만 표현).
    lr, ud                     = chirality
    mu30, mu03, mu21, mu12     = moments   # slog 이미 적용됨

    vec = np.concatenate([
        # size (0:7) — log1p
        np.log1p([props['area'],    props['perimeter'],
                  props['major'],   props['minor'],   props['convex_area'],
                  props['bbox_w'],  props['bbox_h']]),
        # ratio (7:12) — raw
        [props['bbox_aspect'], props['axis_ratio'],
         props['extent'],      props['solidity'],  props['circularity']],
        # position (12:14) — slog
        [_slog(props['centroid_dx']), _slog(props['centroid_dy'])],
        # chirality (14:16) — slog
        [_slog(lr), _slog(ud)],
        # moments (16:20) — slog 기적용
        [mu30, mu03, mu21, mu12],
        # radial_outer (20:276) — log1p
        np.log1p(outer),
        # outer_stats (276:286) — log1p
        np.log1p(list(outer_stats)),
        # outer_fft_mag (286:306) — log1p
        np.log1p(o_mag),
        # outer_fft_phase (306:346) — raw
        o_phase,
        # inner_stats (346:356) — log1p
        np.log1p(list(inner_stats)),
        # inner_fft_mag (356:376) — log1p
        np.log1p(i_mag),
        # inner_fft_phase (376:416) — raw
        i_phase,
        # thickness_stats (416:426) — log1p
        np.log1p(list(thick_stats)),
    ], dtype=np.float64)

    names = (
        ['area', 'perimeter', 'major', 'minor', 'convex_area', 'bbox_w', 'bbox_h']
        + ['bbox_aspect', 'axis_ratio', 'extent', 'solidity', 'circularity']
        + ['centroid_dx', 'centroid_dy']
        + ['chirality_lr', 'chirality_ud']
        + [f'mu{s}' for s in ['30', '03', '21', '12']]
        + [f'radial_outer_{i:03d}' for i in range(N)]
        + _stat_names('r_outer')
        + [f'outer_fft_mag_k{k}' for k in range(1, K + 1)]
        + [f'outer_phase_{"re" if i % 2 == 0 else "im"}_k{i // 2 + 1}' for i in range(2 * K)]
        + _stat_names('r_inner')
        + [f'inner_fft_mag_k{k}' for k in range(1, K + 1)]
        + [f'inner_phase_{"re" if i % 2 == 0 else "im"}_k{i // 2 + 1}' for i in range(2 * K)]
        + _stat_names('thickness')
    )
    return vec, names


# ── 진입점 ────────────────────────────────────────────────────────────────────

def extract_sample_features(
    mask: np.ndarray,
    opts: ExtractOpts | None = None,
    preprocess: bool = True,
) -> SampleFeature:
    """단일 (정렬된) mask → (426,) feature vector.

    Args:
        mask:       (H, W) bool/uint8 binary mask. **정렬된 정준 자세**를 전제로 한다.
        opts:       추출 옵션. None이면 기본값 사용.
        preprocess: False이면 fill_holes/largest_component 건너뜀.
                    dataloader에서 ``_prepare_mask()`` (정렬 포함) 완료 후 호출 시 False 권장.
    """
    if opts is None:
        opts = ExtractOpts()
    px = opts.pixel_size
    pa = px ** 2

    bw = _preprocess(mask, opts.fill_holes, opts.use_largest_component) \
         if preprocess else (mask > 0).astype(bool)

    props     = _region_scalars(bw, px)
    chirality = _chirality(bw, props['cx'], props['cy'], px, pa)
    moments   = _signed_moments(bw, props['cx'], props['cy'], px, pa)

    outer, inner = _mask_to_polar(bw, opts.num_angles, px)
    if opts.smooth_window > 1:
        outer = _smooth(outer, opts.smooth_window)
        inner = _smooth(inner, opts.smooth_window)
    thickness = outer - inner

    outer_stats = _profile_stats(outer)
    inner_stats = _profile_stats(inner)
    thick_stats = _profile_stats(thickness)

    o_mag, o_phase, K = _fourier(outer, opts.num_angles, opts.num_fourier,
                                 opts.phase_ref_max_k, opts.phase_ref_threshold)
    i_mag, i_phase, _ = _fourier(inner, opts.num_angles, opts.num_fourier,
                                 opts.phase_ref_max_k, opts.phase_ref_threshold)

    vec, names = _assemble(
        props, chirality, moments, outer,
        outer_stats, inner_stats, thick_stats,
        o_mag, o_phase, i_mag, i_phase, opts.num_angles, K,
    )
    return SampleFeature(vector=vec, names=names)
