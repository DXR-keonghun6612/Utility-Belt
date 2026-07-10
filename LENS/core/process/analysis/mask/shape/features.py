"""mask.shape 형상 특징 — **정렬된 mask** 를 전제로 (r,θ) 프로파일에서 특징을 뽑는다.

입력 mask 는 ``mask.align.align_mask`` 로 정준 자세(주축 수평·무거운 질량 오른쪽, **회전만**)가 된
상태라고 가정한다. 상하 비대칭은 보존돼 거울상은 서로 다른 프로파일을 갖는다(좌우 구분). 그래서
θ=0 이 정준 주축에 대응해 프로파일이 인스턴스 간 거의 정합돼 있다.
**잔여 미세 정합은 별도 ICP 단계(예정)** 가 맡고, 여기 Fourier descriptor 의 phase 정규화는 그와
별개로 descriptor 를 회전에 견고하게 두기 위한 옵션이다 (ICP 정합 후엔 끄고 raw real/imag 사용 가능).

특징 구성:
  - ``r_outer``/``r_inner``/``thickness=outer-inner`` 프로파일 통계 (mean/std/percentile/range)
  - 각 프로파일의 **Fourier descriptor**: magnitude(|R_k|) + (옵션) phase 정규화 real/imag
  - 크기: raw 가 기본(고정 시점 → 1px=일정 물리크기). ``normalize=True`` 면 형상 프로파일을 유효
    반경(√(area/π))으로 나눠 scale-free 로 두되, 크기 스칼라(area·effective radius)는 항상 보존.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from ..area import area as _area
from .polar import mask_to_polar


class ShapeResult(NamedTuple):
    vector: np.ndarray          # 1-D 특징 벡터
    names:  list[str]           # 벡터와 같은 길이의 이름
    parts:  dict                # 중간 결과 (프로파일·fft 등, 디버그·시각화용)


# ── 프로파일 통계 ─────────────────────────────────────────────────────────────────

def profile_stats(profile: np.ndarray, prefix: str) -> tuple[list[float], list[str]]:
    """프로파일의 mean/std/min/max/range + 백분위(10·25·50·75·90)."""
    _q = np.percentile(profile, [10, 25, 50, 75, 90])
    _vals = [float(profile.mean()), float(profile.std()),
             float(profile.min()), float(profile.max()),
             float(profile.max() - profile.min()),
             *map(float, _q)]
    _names = [f"{prefix}_{_s}" for _s in
              ("mean", "std", "min", "max", "range", "p10", "p25", "p50", "p75", "p90")]
    return _vals, _names


# ── Fourier descriptor (IPA phase 정규화) ─────────────────────────────────────────

def fourier_descriptor(
    profile: np.ndarray, n_harmonics: int, prefix: str,
    phase_ref_max: int = 8,
) -> tuple[list[float], list[str], np.ndarray]:
    """주기 프로파일 → magnitude + phase 정규화 real/imag.

    IPA(잔여 회전 미세정합): 저차 harmonic 중 dominant 한 ``k0`` 의 위상으로 기준각 ``phi0`` 을
    잡아 모든 harmonic 을 ``exp(-i·k·phi0)`` 회전 → circular shift(=잔여 회전)에 불변. magnitude 는
    원래부터 위상 무관이라 그대로.
    """
    _N = profile.size
    _R = np.fft.rfft(profile)                       # R[0]=DC
    _K = int(min(n_harmonics, _R.size - 1))

    _mag = np.abs(_R[1:_K + 1]) / _N

    _refmax = max(1, min(phase_ref_max, _K))
    _k0 = 1 + int(np.argmax(np.abs(_R[1:_refmax + 1])))   # dominant 저차 harmonic
    _phi0 = np.angle(_R[_k0]) / _k0
    _k = np.arange(1, _K + 1)
    _Z = _R[1:_K + 1] * np.exp(-1j * _k * _phi0) / _N

    _vals = [*map(float, _mag)]
    _names = [f"{prefix}_fft_mag_k{_i}" for _i in _k]
    for _i in _k:
        _vals += [float(_Z[_i - 1].real), float(_Z[_i - 1].imag)]
        _names += [f"{prefix}_phase_real_k{_i}", f"{prefix}_phase_imag_k{_i}"]
    return _vals, _names, _R


# ── 진입점 ────────────────────────────────────────────────────────────────────────

def extract_shape_features(
    mask: np.ndarray, *,
    resolution: int = 256,
    n_harmonics: int = 20,
    normalize: bool = False,
) -> ShapeResult:
    """**정렬된** mask → 형상 특징 벡터.

    Args:
        mask: 정준 자세(``align_mask`` 결과)로 가정하는 이진 mask.
        resolution: θ bin 수(각도 해상도).
        n_harmonics: Fourier harmonic 수 K.
        normalize: True 면 형상 프로파일을 유효반경으로 정규화(scale-free). 크기 스칼라는 항상 유지.
    """
    _r_out, _r_in = mask_to_polar(mask, resolution)
    _thick = _r_out - _r_in

    _a = _area(mask)
    _eff_r = float(np.sqrt(max(_a, 1) / np.pi))      # 유효 반경(크기 스칼라)

    # 크기 스칼라는 항상 보존 (정규화해도 크기 정보 유지)
    _vals = [float(_a), _eff_r]
    _names = ["area", "effective_radius"]

    _po, _pi, _pt = _r_out, _r_in, _thick
    if normalize:                                    # 형상만 scale-free
        _po, _pi, _pt = _po / _eff_r, _pi / _eff_r, _pt / _eff_r

    for _prof, _pre in ((_po, "r_outer"), (_pi, "r_inner"), (_pt, "thickness")):
        _v, _n = profile_stats(_prof, _pre)
        _vals += _v; _names += _n

    _ffts = {}
    for _prof, _pre in ((_po, "r_outer"), (_pi, "r_inner")):
        _v, _n, _R = fourier_descriptor(_prof, n_harmonics, _pre)
        _vals += _v; _names += _n
        _ffts[_pre] = _R

    return ShapeResult(
        vector=np.asarray(_vals, np.float32),
        names=_names,
        parts={"r_outer": _r_out, "r_inner": _r_in, "thickness": _thick,
               "effective_radius": _eff_r, "fft": _ffts, "normalized": normalize},
    )
