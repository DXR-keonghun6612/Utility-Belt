"""PyTorch 기반 mask feature 추출.

제외 항목 (원본 feature_extract.py 유지 권장):
  - preprocess_mask       : binary_fill_holes + 최대 컴포넌트 (scipy)
  - convex_area / solidity: convex hull 연산 필요
  - find_contours         : marching-squares → 형태학적 경계 픽셀로 대체

feature 벡터: 355차원 (원본 357 - convex_area - solidity)
  scalar   [  0.. 38] :  39개
  radial   [ 39..294] : 256개  (PCA 정렬 경계 반경 프로파일)
  fft_mag  [295..314] :  20개
  phase_fd [315..354] :  40개  (위상 정규화 복소 푸리에 계수)

사용 예::

    from mask_features.feature_extract import preprocess_mask, FeatureOpts
    from mask_features.feature_extract_torch import extract_features_torch

    BW   = preprocess_mask(raw_mask, fill_holes=True, use_largest=True)
    result = extract_features_torch(BW, opts)
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from .feature_extract import FeatureOpts, FeatureResult, PCA_RELIABLE_RATIO


# ── Feature group 인덱스 (원본과 다름: convex_area·solidity 제거) ─────────────

_ROTATION_INVARIANT_COLS_T: list[int] = (
    [0, 1, 5, 6, 8, 10]            # area, perim, major, minor, axis_ratio, circularity
    + list(range(29, 39))           # radial stats
    + list(range(295, 315))         # fft_mag
)

_ROTATION_STABLE_COLS_T: list[int] = (
    [17, 18, 23, 24, 25, 26, 27, 28]  # pca_rl/ud, pca moments, pca_angle cos/sin
    + list(range(39, 295))             # radial profile
    + list(range(315, 355))            # phase_fd
)

_FEATURE_GROUPS_T: dict[str, tuple] = {
    "scalar":             (0,   39),
    "radial":             (39,  295),
    "fft_mag":            (295, 315),
    "phase_fd":           (315, 355),
    "rotation_invariant": _ROTATION_INVARIANT_COLS_T,
    "rotation_stable":    _ROTATION_STABLE_COLS_T,
}


# ── 공용 헬퍼 ─────────────────────────────────────────────────────────────────

def _signed_log_t(x: torch.Tensor) -> torch.Tensor:
    return x.sign() * torch.log1p(x.abs())


# ── Step 2: Region properties (convex_area / solidity 제외) ───────────────────

def _region_props_t(BW: torch.Tensor, px: float) -> dict:
    rows, cols = BW.nonzero(as_tuple=True)
    rows_d = rows.double()
    cols_d = cols.double()

    area = float(BW.sum()) * px ** 2

    cy_px = rows_d.mean()
    cx_px = cols_d.mean()
    cx = float(cx_px) * px
    cy = float(cy_px) * px

    r0, r1 = int(rows.min()), int(rows.max())
    c0, c1 = int(cols.min()), int(cols.max())
    bbox_w    = (c1 - c0 + 1) * px
    bbox_h    = (r1 - r0 + 1) * px
    bbox_area = bbox_w * bbox_h
    bbox_cx   = c0 * px + bbox_w / 2
    bbox_cy   = r0 * px + bbox_h / 2

    # ── Perimeter: 4-연결 전경-배경 인접 수 ──────────────────────────────────
    bw_f = BW.float().unsqueeze(0).unsqueeze(0)
    k4   = torch.tensor([[0., 1., 0.], [1., 0., 1.], [0., 1., 0.]],
                        dtype=torch.float32, device=BW.device).unsqueeze(0).unsqueeze(0)
    fg_neighbors = F.conv2d(bw_f, k4, padding=1).squeeze()
    perimeter = float((BW.float() * (4.0 - fg_neighbors).clamp(min=0)).sum()) * px

    # ── Major / minor axis: 2차 중심 모멘트 고유값 (skimage 공식) ─────────────
    m00 = float(BW.sum())
    dy_px = rows_d - cy_px
    dx_px = cols_d - cx_px
    mu20 = float((dy_px ** 2).sum())
    mu02 = float((dx_px ** 2).sum())
    mu11 = float((dx_px * dy_px).sum())

    tmp   = (4 * mu11 ** 2 + (mu20 - mu02) ** 2) ** 0.5
    lam1  = max((mu20 + mu02 + tmp) / 2, 0.0)
    lam2  = max((mu20 + mu02 - tmp) / 2, 0.0)
    major = 4.0 * (lam1 / max(m00, 1e-10)) ** 0.5 * px
    minor = 4.0 * (lam2 / max(m00, 1e-10)) ** 0.5 * px

    bbox_aspect = bbox_w / bbox_h     if bbox_h > 1e-10 else 0.0
    axis_ratio  = major / minor       if minor  > 1e-10 else 0.0
    extent      = area  / bbox_area   if bbox_area > 1e-10 else 0.0
    circularity = (4.0 * np.pi * area / perimeter ** 2) if perimeter > 1e-10 else 0.0

    return dict(
        area=area, perimeter=perimeter,
        cx=cx, cy=cy,
        bbox_w=bbox_w, bbox_h=bbox_h, bbox_area=bbox_area,
        bbox_cx=bbox_cx, bbox_cy=bbox_cy,
        major=major, minor=minor,
        bbox_aspect=bbox_aspect, axis_ratio=axis_ratio,
        extent=extent, circularity=circularity,
        centroid_dx=cx - bbox_cx,
        centroid_dy=cy - bbox_cy,
    )


# ── Step 3: Pixel coordinates ─────────────────────────────────────────────────

def _pixel_coords_t(
    BW: torch.Tensor, cx: float, cy: float, px: float
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    rows, cols = BW.nonzero(as_tuple=True)
    x  = cols.double() * px
    y  = rows.double() * px
    return x, y, x - cx, y - cy


# ── Step 4: Image-frame 비대칭 ────────────────────────────────────────────────

def _image_asymmetry_t(
    x: torch.Tensor, y: torch.Tensor,
    cx: float, cy: float,
    bbox_cx: float, bbox_cy: float,
    pixel_area: float,
) -> dict:
    def _diff(arr: torch.Tensor, thr: float) -> float:
        return float(((arr >= thr).sum() - (arr < thr).sum()).item()) * pixel_area
    return dict(
        img_rl_centroid=_diff(x, cx),
        img_ud_centroid=_diff(y, cy),
        img_rl_bbox    =_diff(x, bbox_cx),
        img_ud_bbox    =_diff(y, bbox_cy),
    )


# ── Step 5: PCA 좌표계 ────────────────────────────────────────────────────────

def _pca_frame_t(dx: torch.Tensor, dy: torch.Tensor) -> dict:
    XY = torch.stack([dx, dy], dim=1)           # (N, 2)
    C  = torch.cov(XY.T)                         # (2, 2)
    eigvals, V = torch.linalg.eigh(C)            # ascending

    e1 = V[:, -1].clone()
    i_dom = int(e1.abs().argmax())
    if e1[i_dom] < 0:
        e1 = -e1
    e2 = torch.stack([-e1[1], e1[0]])

    xp = XY @ e1
    yp = XY @ e2

    lam1, lam2 = eigvals[-1], eigvals[-2]
    eigenvalue_ratio = float(lam1 / lam2.clamp(min=1e-10))

    return dict(
        e1=e1, e2=e2,
        xp=xp, yp=yp,
        pca_angle=float(torch.atan2(e1[1], e1[0])),
        eigenvalue_ratio=eigenvalue_ratio,
        pca_reliable=eigenvalue_ratio >= PCA_RELIABLE_RATIO,
    )


def _pca_asymmetry_t(xp: torch.Tensor, yp: torch.Tensor, pixel_area: float) -> dict:
    def _diff(arr: torch.Tensor) -> float:
        return float(((arr >= 0).sum() - (arr < 0).sum()).item()) * pixel_area
    return dict(pca_rl=_diff(xp), pca_ud=_diff(yp))


# ── Step 6: Signed central moments ───────────────────────────────────────────

def _signed_moments_t(
    dx: torch.Tensor, dy: torch.Tensor,
    xp: torch.Tensor, yp: torch.Tensor,
    pixel_area: float,
) -> dict:
    def _moments(u: torch.Tensor, v: torch.Tensor) -> tuple:
        pa = pixel_area
        return (
            _signed_log_t((u ** 3).sum() * pa),
            _signed_log_t((v ** 3).sum() * pa),
            _signed_log_t((u ** 2 * v).sum() * pa),
            _signed_log_t((u * v ** 2).sum() * pa),
        )

    img = _moments(dx, dy)
    pca = _moments(xp, yp)
    keys = ('mu30', 'mu03', 'mu21', 'mu12')
    return {
        **{f'{k}_img': float(v) for k, v in zip(keys, img)},
        **{f'{k}_pca': float(v) for k, v in zip(keys, pca)},
    }


# ── Step 7: 경계 픽셀 추출 (find_contours 대체) ───────────────────────────────

def _boundary_pixels_t(
    BW: torch.Tensor, px: float
) -> tuple[torch.Tensor, torch.Tensor]:
    """8-연결 침식으로 내부 픽셀을 제거 → 나머지가 경계.

    find_contours(marching-squares) 대비 정수 정밀도.
    radial 스무딩 윈도우로 노이즈 보정 가능.
    """
    bw_f   = BW.float().unsqueeze(0).unsqueeze(0)
    k8     = torch.ones(1, 1, 3, 3, dtype=torch.float32, device=BW.device)
    eroded = F.conv2d(bw_f, k8, padding=1).squeeze() == 9.0
    boundary = BW & ~eroded

    row_b, col_b = boundary.nonzero(as_tuple=True)
    if row_b.numel() == 0:
        # 1×1 단일 픽셀 마스크 등 극단 케이스
        row_b, col_b = BW.nonzero(as_tuple=True)

    return col_b.double() * px, row_b.double() * px  # bx, by


# ── Step 8: Radial profile ────────────────────────────────────────────────────

def _radial_profile_t(
    bx: torch.Tensor, by: torch.Tensor,
    cx: float, cy: float,
    e1: torch.Tensor, e2: torch.Tensor,
    N: int,
) -> torch.Tensor:
    u = (bx - cx) * e1[0] + (by - cy) * e1[1]
    v = (bx - cx) * e2[0] + (by - cy) * e2[1]

    theta = torch.atan2(v, u)
    theta[theta < 0] += 2.0 * np.pi

    r    = torch.hypot(u, v)
    bins = (theta / (2.0 * np.pi) * N).floor().long().clamp(0, N - 1)

    profile = torch.full((N,), float('-inf'), dtype=torch.float64, device=bx.device)
    profile.scatter_reduce_(0, bins, r.double(), reduce='amax', include_self=True)
    profile[torch.isneginf(profile)] = float('nan')
    return profile


def _fill_circular_nan_t(x: torch.Tensor) -> torch.Tensor:
    N     = len(x)
    valid = ~torch.isnan(x)
    if valid.all():
        return x.clone()
    if not valid.any():
        raise ValueError("All radial bins are NaN.")

    vi = torch.where(valid)[0].double()
    vv = x[valid].double()

    ext_idx = torch.cat([vi - N, vi, vi + N])
    ext_val = vv.repeat(3)

    idx  = torch.arange(N, dtype=torch.float64, device=x.device)
    pos  = torch.searchsorted(ext_idx.contiguous(), idx.contiguous()).clamp(1, len(ext_idx) - 1)
    x0, x1 = ext_idx[pos - 1], ext_idx[pos]
    y0, y1 = ext_val[pos - 1], ext_val[pos]

    t      = ((idx - x0) / (x1 - x0).clamp(min=1e-10))
    result = (y0 + t * (y1 - y0))
    result[valid] = x[valid].double()
    return result


def _circular_moving_mean_t(x: torch.Tensor, win: int) -> torch.Tensor:
    win = max(1, int(round(win)))
    if win <= 1:
        return x.clone()
    N   = len(x)
    pad = win // 2
    x_pad  = torch.cat([x[-pad:], x, x[:pad]])
    kernel = torch.ones(1, 1, win, dtype=x.dtype, device=x.device) / win
    out    = F.conv1d(x_pad.view(1, 1, -1).float(), kernel.float()).squeeze().to(x.dtype)
    return out[:N]


# ── Step 9: Radial statistics ─────────────────────────────────────────────────

def _radial_stats_t(radial: torch.Tensor) -> dict:
    q = torch.quantile(radial.float(), torch.tensor([0.1, 0.25, 0.5, 0.75, 0.9]))
    return dict(
        mean =float(radial.mean()),
        std  =float(radial.std(correction=0)),
        min  =float(radial.min()),
        max  =float(radial.max()),
        range=float(radial.max() - radial.min()),
        p10=float(q[0]), p25=float(q[1]), p50=float(q[2]),
        p75=float(q[3]), p90=float(q[4]),
    )


# ── Step 10: Fourier features ─────────────────────────────────────────────────

def _fourier_features_t(
    radial: torch.Tensor,
    N: int, K: int,
    phase_ref_max_k: int,
    phase_ref_threshold: float,
) -> dict:
    R = torch.fft.fft(radial.double())
    K = min(K, N // 2 - 1)

    fft_mag    = R[1:K + 1].abs() / N
    ref_k      = min(phase_ref_max_k, K)
    energy_low = R[1:ref_k + 1].abs().sum()

    if R[1].abs() > phase_ref_threshold * max(float(energy_low), torch.finfo(torch.float64).eps):
        k0 = 1
    else:
        k0 = int(R[1:ref_k + 1].abs().argmax().item()) + 1

    phi0 = float(R[k0].angle()) / k0
    ks   = torch.arange(1, K + 1, dtype=torch.float64, device=radial.device)
    Zk   = R[1:K + 1] * torch.exp(-1j * ks * phi0) / N

    return dict(
        R=R, K=K,
        fft_mag=fft_mag,
        phase_real=Zk.real.clone(),
        phase_imag=Zk.imag.clone(),
        k0=k0, phi0=phi0,
    )


# ── Step 11: Bispectrum (optional) ────────────────────────────────────────────

def _bispectrum_features_t(
    R: torch.Tensor, N: int, K: int, order: int
) -> tuple[torch.Tensor, list[str]]:
    B_order = min(order, K // 2)
    vals:  list[torch.Tensor] = []
    names: list[str]          = []
    for p in range(1, B_order + 1):
        for q in range(1, B_order + 1):
            if p + q <= K:
                Bpq = R[p] * R[q] * R[p + q].conj() / (N ** 3)
                vals += [_signed_log_t(Bpq.real), _signed_log_t(Bpq.imag)]
                names += [f'bispec_real_log_p{p}_q{q}', f'bispec_imag_log_p{p}_q{q}']
    if vals:
        return torch.stack(vals).double(), names
    return torch.empty(0, dtype=torch.float64), []


# ── Step 12: Feature vector 조립 ─────────────────────────────────────────────

def _assemble_t(
    props: dict,
    img_asym: dict,
    pca_asym: dict,
    moments: dict,
    pca_angle: float,
    r_stats: dict,
    radial: torch.Tensor,
    fourier: dict,
    bispectrum: tuple[torch.Tensor, list[str]],
) -> tuple[torch.Tensor, list[str]]:
    N = len(radial)
    K = fourier['K']

    scalar_vals = [
        props['area'],        props['perimeter'],
        props['bbox_w'],      props['bbox_h'],      props['bbox_area'],
        props['major'],       props['minor'],
        props['bbox_aspect'], props['axis_ratio'],
        props['extent'],      props['circularity'],
        props['centroid_dx'], props['centroid_dy'],
        img_asym['img_rl_centroid'], img_asym['img_ud_centroid'],
        img_asym['img_rl_bbox'],     img_asym['img_ud_bbox'],
        pca_asym['pca_rl'],          pca_asym['pca_ud'],
        moments['mu30_img'], moments['mu03_img'],
        moments['mu21_img'], moments['mu12_img'],
        moments['mu30_pca'], moments['mu03_pca'],
        moments['mu21_pca'], moments['mu12_pca'],
        np.cos(pca_angle),   np.sin(pca_angle),
        r_stats['mean'], r_stats['std'],
        r_stats['min'],  r_stats['max'],  r_stats['range'],
        r_stats['p10'],  r_stats['p25'],  r_stats['p50'],
        r_stats['p75'],  r_stats['p90'],
    ]
    scalar_names = [
        'area', 'perimeter',
        'bbox_width', 'bbox_height', 'bbox_area',
        'major_axis_length', 'minor_axis_length',
        'bbox_aspect_w_over_h', 'axis_ratio_major_over_minor',
        'extent', 'circularity',
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

    phase_vals = torch.empty(2 * K, dtype=torch.float64)
    phase_vals[0::2] = fourier['phase_real']
    phase_vals[1::2] = fourier['phase_imag']
    phase_names = sum([[f'phase_real_k{k}', f'phase_imag_k{k}'] for k in range(1, K + 1)], [])

    bispec_vals, bispec_names = bispectrum

    vector = torch.cat([
        torch.tensor(scalar_vals, dtype=torch.float64),
        radial.double(),
        fourier['fft_mag'].double(),
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


# ── Main entry point ──────────────────────────────────────────────────────────

def extract_features_torch(
    BW: np.ndarray,
    opts: FeatureOpts | None = None,
    device: str | torch.device = 'cpu',
) -> FeatureResult:
    """전처리된 BW mask → FeatureResult.

    BW 는 preprocess_mask() 를 통과한 bool ndarray 여야 한다.
    """
    if opts is None:
        opts = FeatureOpts()
    px = opts.pixel_size

    mask = torch.as_tensor(BW, dtype=torch.bool, device=device)

    props      = _region_props_t(mask, px)
    cx, cy     = props['cx'], props['cy']
    pixel_area = px ** 2

    x, y, dx, dy = _pixel_coords_t(mask, cx, cy, px)
    img_asym     = _image_asymmetry_t(x, y, cx, cy, props['bbox_cx'], props['bbox_cy'], pixel_area)
    pca          = _pca_frame_t(dx, dy)
    pca_asym     = _pca_asymmetry_t(pca['xp'], pca['yp'], pixel_area)
    moms         = _signed_moments_t(dx, dy, pca['xp'], pca['yp'], pixel_area)

    bx, by  = _boundary_pixels_t(mask, px)
    profile = _radial_profile_t(bx, by, cx, cy, pca['e1'], pca['e2'], opts.num_angles)
    profile = _fill_circular_nan_t(profile)
    if opts.radial_smooth_window > 1:
        profile = _circular_moving_mean_t(profile, opts.radial_smooth_window)

    r_stats = _radial_stats_t(profile)
    fourier = _fourier_features_t(
        profile, opts.num_angles, opts.num_fourier,
        opts.phase_ref_max_harmonic, opts.phase_ref_threshold,
    )

    bispec = (
        _bispectrum_features_t(fourier['R'], opts.num_angles, fourier['K'], opts.bispectrum_order)
        if opts.include_bispectrum
        else (torch.empty(0, dtype=torch.float64), [])
    )

    vector, names = _assemble_t(
        props, img_asym, pca_asym, moms, pca['pca_angle'],
        r_stats, profile, fourier, bispec,
    )

    debug = dict(
        BW=BW,
        centroid=(cx, cy),
        bbox=(props['bbox_cx'] - props['bbox_w'] / 2,
              props['bbox_cy'] - props['bbox_h'] / 2,
              props['bbox_w'], props['bbox_h']),
        pca_e1=pca['e1'].cpu().numpy(),
        pca_e2=pca['e2'].cpu().numpy(),
        pca_angle=pca['pca_angle'],
        eigenvalue_ratio=pca['eigenvalue_ratio'],
        pca_reliable=pca['pca_reliable'],
        boundary_x=bx.cpu().numpy(),
        boundary_y=by.cpu().numpy(),
        radial_profile=profile.cpu().numpy(),
        fft_R=fourier['R'].cpu().numpy(),
        phase_ref_k=fourier['k0'],
        phase_ref_angle=fourier['phi0'],
    )
    return FeatureResult(vector=vector.cpu().numpy(), names=names, debug=debug)
