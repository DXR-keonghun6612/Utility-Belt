"""mask.shape 회전 미세정합 — (r,θ) 프로파일 공간에서의 ICP-등가 회전 최적화.

회전 = 프로파일의 **circular shift**. 두 프로파일의 최적 shift(=상대 회전)는 circular
cross-correlation 으로 한 번에 찾고, 피크 주변 **포물선 보간**으로 bin(2π/N)보다 미세한 sub-bin
각도까지 정밀화한다 → resolution(N)이 클수록 각도 분해능이 세지고, 보간으로 그 한계도 넘는다.

역할: PCA+flip(:mod:`mask.align`)이 coarse 자세를 잡고, 이 단계가 reference(템플릿/클래스 평균)
대비 **잔여 회전**을 미세 정합한다. reference 는 호출자가 준다 — 데이터셋 단계에서 평균 프로파일로
Procrustes 반복(전체를 평균에 맞추고 평균 갱신)에 쓰면 된다.
"""

from __future__ import annotations

import numpy as np


def best_shift(profile: np.ndarray, reference: np.ndarray) -> float:
    """``profile`` 을 ``reference`` 에 맞추는 circular shift(bin 단위, sub-bin 실수).

    ``apply_shift(profile, best_shift(profile, ref))`` 가 ``ref`` 에 정합된다. 부호 규약: 양수
    shift = θ 증가 방향 회전. 결과는 ``[-N/2, N/2)`` 로 wrap.
    """
    _N = profile.size
    _f = np.fft.rfft(profile)
    _g = np.fft.rfft(reference)
    _corr = np.fft.irfft(_f * np.conj(_g), n=_N)     # 원형 상관: 피크 = 최적 정합 shift
    _k = int(np.argmax(_corr))

    _y0, _y1, _y2 = _corr[(_k - 1) % _N], _corr[_k], _corr[(_k + 1) % _N]   # sub-bin 포물선 보간
    _den = _y0 - 2.0 * _y1 + _y2
    _delta = 0.5 * (_y0 - _y2) / _den if _den != 0 else 0.0
    _shift = _k + _delta
    if _shift >= _N / 2.0:                            # 최단 회전으로 wrap
        _shift -= _N
    return float(_shift)


def apply_shift(profile: np.ndarray, shift: float) -> np.ndarray:
    """프로파일을 ``shift`` bin(실수) 만큼 원형 이동 (선형보간, sub-bin 허용)."""
    _N = profile.size
    _idx = (np.arange(_N) - shift) % _N
    _lo = np.floor(_idx).astype(np.int64)
    _frac = _idx - _lo
    return ((1.0 - _frac) * profile[_lo % _N] + _frac * profile[(_lo + 1) % _N]).astype(profile.dtype)


def shift_to_angle(shift: float, resolution: int) -> float:
    """shift(bin) → 회전각(rad). 분해능 2π/resolution."""
    return float(shift * 2.0 * np.pi / resolution)


def register_rotation(
    outer: np.ndarray, inner: np.ndarray, ref_outer: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    """``ref_outer`` 기준 잔여 회전을 추정해 outer·inner 를 함께 정합한다.

    회전은 mask 전체의 단일 자유도이므로 dominant 한 ``outer`` 로 shift 를 구하고 ``inner`` 에도
    같은 shift 를 적용한다.

    Returns:
        ``(shift_bins, outer_aligned, inner_aligned)``.
    """
    _s = best_shift(outer, ref_outer)
    return _s, apply_shift(outer, _s), apply_shift(inner, _s)
