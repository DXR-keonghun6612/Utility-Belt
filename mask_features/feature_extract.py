"""단일 mask → feature vector 추출.

extractSideMirrorMaskFeatures.m 의 Python 포팅.
mask 한 장 → FeatureResult(vector, names, debug).

기본 설정 (num_angles=256, num_fourier=20): 357차원
  41 scalar + 256 radial + 20 fft_mag + 40 phase_fd
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from scipy.ndimage import binary_fill_holes, label, uniform_filter1d
from skimage.measure import find_contours, regionprops


# ── Global constants ─────────────────────────────────────────────────────────────

PCA_RELIABLE_RATIO: float = 1.3

_ROTATION_INVARIANT_COLS: list[int] = (
    [0, 1, 5, 6, 7, 9, 11, 12]
    + list(range(31, 41))
    + list(range(297, 317))
)

_ROTATION_STABLE_COLS: list[int] = (
    [19, 20, 25, 26, 27, 28, 29, 30]
    + list(range(41, 297))
    + list(range(317, 357))
)

_FEATURE_GROUPS: dict[str, tuple | list] = {
    "scalar":             (0,   41),
    "radial":             (41,  297),
    "fft_mag":            (297, 317),
    "phase_fd":           (317, 357),
    "rotation_invariant": _ROTATION_INVARIANT_COLS,
    "rotation_stable":    _ROTATION_STABLE_COLS,
}


# ── Options / Result ─────────────────────────────────────────────────────────────

@dataclass
class FeatureOpts:
    pixel_size: float = 1.0
    num_angles: int = 256
    num_fourier: int = 20
    fill_holes: bool = True
    use_largest_component: bool = True
    radial_smooth_window: int = 3
    phase_ref_max_harmonic: int = 8
    phase_ref_threshold: float = 1e-3
    include_bispectrum: bool = False
    bispectrum_order: int = 6


class FeatureResult(NamedTuple):
    vector: np.ndarray
    names: list[str]
    debug: dict


# ── Step 1: Mask preprocessing ────────────────────────────────────────────────────

def preprocess_mask(BW: np.ndarray, fill_holes: bool, use_largest: bool) -> np.ndarray:
    BW = BW > 0
    if fill_holes:
        BW = binary_fill_holes(BW)
    if use_largest:
        labeled, n = label(BW)
        if n == 0:
            raise ValueError("Input BW mask is empty after filling holes.")
        sizes = [np.sum(labeled == i) for i in range(1, n + 1)]
        BW = labeled == (np.argmax(sizes) + 1)
    if not BW.any():
        raise ValueError("Input BW mask is empty.")
    return BW.astype(bool)


# ── Step 2: Basic region properties ──────────────────────────────────────────────

def compute_region_props(BW: np.ndarray, px: float) -> dict:
    props = regionprops(BW.astype(np.uint8))[0]

    area      = props.area * px ** 2
    perimeter = props.perimeter * px

    cy_px, cx_px = props.centroid
    cx = cx_px * px
    cy = cy_px * px

    r0, c0, r1, c1 = props.bbox
    bbox_x = c0 * px
    bbox_y = r0 * px
    bbox_w = (c1 - c0) * px
    bbox_h = (r1 - r0) * px
    bbox_area = bbox_w * bbox_h
    bbox_cx = bbox_x + bbox_w / 2
    bbox_cy = bbox_y + bbox_h / 2

    major       = props.axis_major_length * px
    minor       = props.axis_minor_length * px
    convex_area = props.area_convex * px ** 2

    bbox_aspect = _safe_div(bbox_w, bbox_h)
    axis_ratio  = _safe_div(major, minor)
    extent      = _safe_div(area, bbox_area)
    solidity    = _safe_div(area, convex_area)
    circularity = _safe_div(4 * np.pi * area, perimeter ** 2)

    return dict(
        area=area, perimeter=perimeter,
        cx=cx, cy=cy,
        bbox_x=bbox_x, bbox_y=bbox_y, bbox_w=bbox_w, bbox_h=bbox_h,
        bbox_area=bbox_area, bbox_cx=bbox_cx, bbox_cy=bbox_cy,
        major=major, minor=minor, convex_area=convex_area,
        bbox_aspect=bbox_aspect, axis_ratio=axis_ratio,
        extent=extent, solidity=solidity, circularity=circularity,
        centroid_dx=cx - bbox_cx,
        centroid_dy=cy - bbox_cy,
    )


# ── Step 3: Pixel coordinates ─────────────────────────────────────────────────────

def compute_pixel_coords(
    BW: np.ndarray, cx: float, cy: float, px: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows, cols = np.where(BW)
    x  = cols.astype(np.float64) * px
    y  = rows.astype(np.float64) * px
    return x, y, x - cx, y - cy


# ── Step 4: Image-frame signed asymmetry ──────────────────────────────────────────

def compute_image_asymmetry(
    x: np.ndarray, y: np.ndarray,
    cx: float, cy: float,
    bbox_cx: float, bbox_cy: float,
    pixel_area: float,
) -> dict:
    return dict(
        img_rl_centroid=(np.sum(x >= cx)      - np.sum(x <  cx))      * pixel_area,
        img_ud_centroid=(np.sum(y >= cy)      - np.sum(y <  cy))      * pixel_area,
        img_rl_bbox    =(np.sum(x >= bbox_cx) - np.sum(x < bbox_cx))  * pixel_area,
        img_ud_bbox    =(np.sum(y >= bbox_cy) - np.sum(y < bbox_cy))  * pixel_area,
    )


# ── Step 5: PCA frame ─────────────────────────────────────────────────────────────

def compute_pca_frame(dx: np.ndarray, dy: np.ndarray) -> dict:
    """픽셀 오프셋의 PCA 좌표계.

    부호 규약: 절댓값이 큰 성분으로 부호 결정.
    eigenvalue_ratio < PCA_RELIABLE_RATIO → 주축 방향 신뢰 불가.
    """
    XY = np.column_stack([dx, dy])
    C  = np.cov(XY.T)
    eigvals, V = np.linalg.eigh(C)

    e1 = V[:, -1].copy()
    i_dom = int(np.argmax(np.abs(e1)))
    if e1[i_dom] < 0:
        e1 = -e1
    e2 = np.array([-e1[1], e1[0]])

    xp = XY @ e1
    yp = XY @ e2

    lam1, lam2 = eigvals[-1], eigvals[-2]
    eigenvalue_ratio = lam1 / max(lam2, 1e-10)

    return dict(
        e1=e1, e2=e2,
        xp=xp, yp=yp,
        pca_angle=np.arctan2(e1[1], e1[0]),
        eigenvalue_ratio=float(eigenvalue_ratio),
        pca_reliable=eigenvalue_ratio >= PCA_RELIABLE_RATIO,
    )


def compute_pca_asymmetry(xp: np.ndarray, yp: np.ndarray, pixel_area: float) -> dict:
    return dict(
        pca_rl=(np.sum(xp >= 0) - np.sum(xp < 0)) * pixel_area,
        pca_ud=(np.sum(yp >= 0) - np.sum(yp < 0)) * pixel_area,
    )


# ── Step 6: Signed central moments ───────────────────────────────────────────────

def compute_signed_moments(
    dx: np.ndarray, dy: np.ndarray,
    xp: np.ndarray, yp: np.ndarray,
    pixel_area: float,
) -> dict:
    def _moments(u: np.ndarray, v: np.ndarray) -> tuple:
        pa = pixel_area
        return (
            _signed_log(np.sum(u ** 3)     * pa),
            _signed_log(np.sum(v ** 3)     * pa),
            _signed_log(np.sum(u ** 2 * v) * pa),
            _signed_log(np.sum(u * v ** 2) * pa),
        )

    img = _moments(dx, dy)
    pca = _moments(xp, yp)

    keys = ('mu30', 'mu03', 'mu21', 'mu12')
    return {
        **{f'{k}_img': v for k, v in zip(keys, img)},
        **{f'{k}_pca': v for k, v in zip(keys, pca)},
    }


# ── Step 7: Boundary extraction ───────────────────────────────────────────────────

def extract_longest_boundary(BW: np.ndarray, px: float) -> tuple[np.ndarray, np.ndarray]:
    contours = find_contours(BW.astype(np.float32), level=0.5)
    if not contours:
        raise ValueError("No boundary found from BW mask.")
    boundary = max(contours, key=len)
    return boundary[:, 1] * px, boundary[:, 0] * px


# ── Step 8: Radial profile ────────────────────────────────────────────────────────

def compute_radial_profile(
    bx: np.ndarray, by: np.ndarray,
    cx: float, cy: float,
    e1: np.ndarray, e2: np.ndarray,
    N: int,
) -> np.ndarray:
    u = (bx - cx) * e1[0] + (by - cy) * e1[1]
    v = (bx - cx) * e2[0] + (by - cy) * e2[1]

    theta = np.arctan2(v, u)
    theta[theta < 0] += 2 * np.pi

    r    = np.hypot(u, v)
    bins = np.floor(theta / (2 * np.pi) * N).astype(int)
    bins = np.clip(bins, 0, N - 1)

    profile = np.full(N, -np.inf)
    np.maximum.at(profile, bins, r)
    profile[np.isneginf(profile)] = np.nan
    return profile


def fill_circular_nan(x: np.ndarray) -> np.ndarray:
    N     = len(x)
    idx   = np.arange(N)
    valid = ~np.isnan(x)
    if valid.all():
        return x.copy()
    if not valid.any():
        raise ValueError("All radial bins are NaN.")
    vi = idx[valid]
    vv = x[valid]
    ext_idx = np.concatenate([vi - N, vi, vi + N])
    ext_val = np.tile(vv, 3)
    return np.interp(idx, ext_idx, ext_val)


def circular_moving_mean(x: np.ndarray, win: int) -> np.ndarray:
    win = max(1, int(round(win)))
    if win <= 1:
        return x.copy()
    N   = len(x)
    pad = win // 2
    x_pad = np.concatenate([x[-pad:], x, x[:pad]])
    y_pad = uniform_filter1d(x_pad.astype(np.float64), size=win, mode='nearest')
    return y_pad[pad:pad + N]


# ── Step 9: Radial statistics ─────────────────────────────────────────────────────

def compute_radial_stats(radial: np.ndarray) -> dict:
    q = np.percentile(radial, [10, 25, 50, 75, 90], method='linear')
    return dict(
        mean=float(np.mean(radial)),
        std =float(np.std(radial, ddof=0)),
        min =float(np.min(radial)),
        max =float(np.max(radial)),
        range=float(np.max(radial) - np.min(radial)),
        p10=float(q[0]), p25=float(q[1]), p50=float(q[2]),
        p75=float(q[3]), p90=float(q[4]),
    )


# ── Step 10: Fourier features ─────────────────────────────────────────────────────

def compute_fourier_features(
    radial: np.ndarray,
    N: int,
    K: int,
    phase_ref_max_k: int,
    phase_ref_threshold: float,
) -> dict:
    R = np.fft.fft(radial.astype(np.float64))
    K = min(K, N // 2 - 1)

    fft_mag = np.abs(R[1:K + 1]) / N

    ref_k      = min(phase_ref_max_k, K)
    energy_low = np.sum(np.abs(R[1:ref_k + 1]))

    if np.abs(R[1]) > phase_ref_threshold * max(energy_low, np.finfo(float).eps):
        k0 = 1
    else:
        k0 = int(np.argmax(np.abs(R[1:ref_k + 1]))) + 1

    phi0 = np.angle(R[k0]) / k0

    ks   = np.arange(1, K + 1, dtype=np.float64)
    Zk   = R[1:K + 1] * np.exp(-1j * ks * phi0) / N

    return dict(
        R=R, K=K,
        fft_mag=fft_mag,
        phase_real=Zk.real.copy(),
        phase_imag=Zk.imag.copy(),
        k0=k0, phi0=phi0,
    )


# ── Step 11: Bispectrum (optional) ────────────────────────────────────────────────

def compute_bispectrum_features(
    R: np.ndarray, N: int, K: int, order: int
) -> tuple[np.ndarray, list[str]]:
    B_order = min(order, K // 2)
    vals: list[float] = []
    names: list[str]  = []
    for p in range(1, B_order + 1):
        for q in range(1, B_order + 1):
            if p + q <= K:
                Bpq = R[p] * R[q] * np.conj(R[p + q]) / (N ** 3)
                vals += [_signed_log(Bpq.real), _signed_log(Bpq.imag)]
                names += [f'bispec_real_log_p{p}_q{q}', f'bispec_imag_log_p{p}_q{q}']
    return np.array(vals, dtype=np.float64), names


# ── Step 12: Assemble feature vector ─────────────────────────────────────────────

def assemble_feature_vector(
    props: dict,
    img_asym: dict,
    pca_asym: dict,
    moments: dict,
    pca_angle: float,
    radial_stats: dict,
    radial_profile: np.ndarray,
    fourier: dict,
    bispectrum: tuple[np.ndarray, list[str]],
) -> tuple[np.ndarray, list[str]]:
    N = len(radial_profile)
    K = fourier['K']

    scalar_vals = [
        props['area'],         props['perimeter'],
        props['bbox_w'],       props['bbox_h'],        props['bbox_area'],
        props['major'],        props['minor'],          props['convex_area'],
        props['bbox_aspect'],  props['axis_ratio'],
        props['extent'],       props['solidity'],       props['circularity'],
        props['centroid_dx'],  props['centroid_dy'],
        img_asym['img_rl_centroid'], img_asym['img_ud_centroid'],
        img_asym['img_rl_bbox'],     img_asym['img_ud_bbox'],
        pca_asym['pca_rl'],          pca_asym['pca_ud'],
        moments['mu30_img'], moments['mu03_img'],
        moments['mu21_img'], moments['mu12_img'],
        moments['mu30_pca'], moments['mu03_pca'],
        moments['mu21_pca'], moments['mu12_pca'],
        np.cos(pca_angle),   np.sin(pca_angle),
        radial_stats['mean'], radial_stats['std'],
        radial_stats['min'],  radial_stats['max'],  radial_stats['range'],
        radial_stats['p10'],  radial_stats['p25'],  radial_stats['p50'],
        radial_stats['p75'],  radial_stats['p90'],
    ]
    scalar_names = [
        'area', 'perimeter',
        'bbox_width', 'bbox_height', 'bbox_area',
        'major_axis_length', 'minor_axis_length', 'convex_area',
        'bbox_aspect_w_over_h', 'axis_ratio_major_over_minor',
        'extent', 'solidity', 'circularity',
        'centroid_dx_from_bbox', 'centroid_dy_from_bbox',
        'img_area_rl_centroid', 'img_area_ud_centroid',
        'img_area_rl_bbox',     'img_area_ud_bbox',
        'pca_area_rl',          'pca_area_ud',
        'mu30_img_log', 'mu03_img_log', 'mu21_img_log', 'mu12_img_log',
        'mu30_pca_log', 'mu03_pca_log', 'mu21_pca_log', 'mu12_pca_log',
        'pca_angle_cos', 'pca_angle_sin',
        'radial_mean', 'radial_std', 'radial_min', 'radial_max', 'radial_range',
        'radial_p10', 'radial_p25', 'radial_p50', 'radial_p75', 'radial_p90',
    ]

    phase_vals = np.empty(2 * K, dtype=np.float64)
    phase_vals[0::2] = fourier['phase_real']
    phase_vals[1::2] = fourier['phase_imag']
    phase_names = sum(
        [[f'phase_real_k{k}', f'phase_imag_k{k}'] for k in range(1, K + 1)], []
    )

    bispec_vals, bispec_names = bispectrum

    vector = np.concatenate([
        np.array(scalar_vals, dtype=np.float64),
        radial_profile.astype(np.float64),
        fourier['fft_mag'].astype(np.float64),
        phase_vals,
        bispec_vals,
    ])
    names = (
        scalar_names
        + [f'radial_pca_{i:03d}' for i in range(N)]
        + [f'fft_mag_k{k}' for k in range(1, K + 1)]
        + phase_names
        + bispec_names
    )
    return vector, names


# ── Main single-mask entry point ──────────────────────────────────────────────────

def extract_features(BW: np.ndarray, opts: FeatureOpts | None = None) -> FeatureResult:
    """mask 한 장 → FeatureResult(vector, names, debug)."""
    if opts is None:
        opts = FeatureOpts()
    px = opts.pixel_size

    BW = preprocess_mask(BW, opts.fill_holes, opts.use_largest_component)

    props   = compute_region_props(BW, px)
    cx, cy  = props['cx'], props['cy']
    x, y, dx, dy = compute_pixel_coords(BW, cx, cy, px)
    pixel_area   = px ** 2

    img_asym = compute_image_asymmetry(x, y, cx, cy, props['bbox_cx'], props['bbox_cy'], pixel_area)
    pca      = compute_pca_frame(dx, dy)
    pca_asym = compute_pca_asymmetry(pca['xp'], pca['yp'], pixel_area)
    moms     = compute_signed_moments(dx, dy, pca['xp'], pca['yp'], pixel_area)

    bx, by  = extract_longest_boundary(BW, px)
    profile = compute_radial_profile(bx, by, cx, cy, pca['e1'], pca['e2'], opts.num_angles)
    profile = fill_circular_nan(profile)
    if opts.radial_smooth_window > 1:
        profile = circular_moving_mean(profile, opts.radial_smooth_window)

    r_stats = compute_radial_stats(profile)
    fourier = compute_fourier_features(
        profile, opts.num_angles, opts.num_fourier,
        opts.phase_ref_max_harmonic, opts.phase_ref_threshold,
    )

    bispec = (
        compute_bispectrum_features(fourier['R'], opts.num_angles, fourier['K'], opts.bispectrum_order)
        if opts.include_bispectrum
        else (np.empty(0, dtype=np.float64), [])
    )

    vector, names = assemble_feature_vector(
        props, img_asym, pca_asym, moms, pca['pca_angle'],
        r_stats, profile, fourier, bispec,
    )

    debug = dict(
        BW=BW,
        centroid=(cx, cy),
        bbox=(props['bbox_x'], props['bbox_y'], props['bbox_w'], props['bbox_h']),
        pca_e1=pca['e1'], pca_e2=pca['e2'], pca_angle=pca['pca_angle'],
        eigenvalue_ratio=pca['eigenvalue_ratio'],
        pca_reliable=pca['pca_reliable'],
        boundary_x=bx, boundary_y=by,
        radial_profile=profile,
        fft_R=fourier['R'],
        phase_ref_k=fourier['k0'], phase_ref_angle=fourier['phi0'],
    )
    return FeatureResult(vector=vector, names=names, debug=debug)


# ── Private helpers ───────────────────────────────────────────────────────────────

def _safe_div(a: float, b: float) -> float:
    return 0.0 if abs(b) < np.finfo(float).eps else a / b


def _signed_log(x: float | np.ndarray) -> float | np.ndarray:
    return np.sign(x) * np.log1p(np.abs(x))
