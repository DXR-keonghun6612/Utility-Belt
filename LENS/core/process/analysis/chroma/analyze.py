"""analyze — 누산 히스토그램 → ChromaDiag (순수 계산 진입점, CLI/GUI 공용)."""

from __future__ import annotations

import numpy as np

from core.process.func.chroma._space import Get_space, ChromaSpace
from core.process.stream.chroma import Robust_Chroma_Stats

from ._result import ChromaDiag
from .io import as_histogram
from .stats import (
    per_pixel_stats, global_stats, global_robust_from_pixels, variance_partition,
)


def analyze(
    c0_acc, c1_acc, *,
    space: "str | ChromaSpace" = "hsv",
    window: int = 10,
    min_count: int = 10,
) -> ChromaDiag:
    """누산 히스토그램에서 공간 의존성 진단을 계산해 ``ChromaDiag`` 로 돌려준다.

    ``c0_acc``/``c1_acc`` 는 **배열(GUI: in-memory)** 또는 **경로 str/Path(CLI: 저장본)** 모두
    허용한다 — 경로면 dir 의 경우 최대 누산 스냅샷을 자동 선택해 로드한다.
    """
    _sp = Get_space(space)
    _b0, _b1 = _sp.bins
    _cir0, _cir1 = _sp.circular

    _h0 = as_histogram(c0_acc, _b0, "c0_acc", _sp.name)
    _h1 = as_histogram(c1_acc, _b1, "c1_acc", _sp.name)
    if _h0.shape[:2] != _h1.shape[:2]:
        raise ValueError(f"c0/c1 공간 크기 불일치: {_h0.shape[:2]} vs {_h1.shape[:2]}")

    m0, s0, n0 = per_pixel_stats(_h0, window, circular=_cir0)
    m1, s1, n1 = per_pixel_stats(_h1, window, circular=_cir1)
    n = np.minimum(n0, n1)                  # 두 채널 공통 신뢰도

    g0 = global_stats(_h0, window, circular=_cir0)
    g1 = global_stats(_h1, window, circular=_cir1)

    # 2중 robust — 픽셀별 대표색을 픽셀당 1표로 다시 robust (고정 위치 객체 오염에 강한 전역색)
    _valid = n >= max(min_count, 1)
    gr0 = global_robust_from_pixels(m0, _valid, window, _cir0, _b0)
    gr1 = global_robust_from_pixels(m1, _valid, window, _cir1, _b1)

    p0 = variance_partition(m0, s0, n, circular=_cir0, period=_b0, min_count=min_count)
    p1 = variance_partition(m1, s1, n, circular=_cir1, period=_b1, min_count=min_count)

    return ChromaDiag(
        space=_sp, window=window, min_count=min_count,
        mean=(m0, m1), std=(s0, s1), n=n,
        g_mean=(g0[0], g1[0]), g_std=(g0[1], g1[1]),
        g_robust=(gr0[0], gr1[0]), part=(p0, p1),
    )
