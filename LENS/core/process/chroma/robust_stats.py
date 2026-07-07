from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ._space import Get_space, DEFAULT_SPACE
from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI


def _robust_mean_std(hist: np.ndarray, circular: bool) -> tuple[np.ndarray, np.ndarray]:
    """히스토그램 → median + IQR robust 배경 평균/표준편차 (마지막 축, 벡터화, leading shape 무관).

    가중 median=배경값, IQR/1.349=σ (분위수라 객체 꼬리에 면역). 순환 채널(hue)은 mode 중심 ``±B/2``
    좌표로 gather 해 비순환처럼 처리. 근거·이전 mode-window 방식 실패는 ``README.md``.

    ``hist`` 마지막 축이 bin(``circular`` = hue처럼 0/끝이 이어지면 True). ``(B,)``→스칼라,
    ``(H,W,B)``→``(H,W)`` float32 ``(mean, std)``.
    """
    _b    = hist.shape[-1]
    _mode = np.argmax(hist, axis=-1).astype(np.int32)            # (...,) 최빈 bin = 좌표 중심
    if circular:
        # mode를 중심에 두는 ±B/2 좌표로 가중치만 gather → 순환을 비순환처럼 (좌표는 상수 offset)
        _idx   = (_mode[..., None] - _b // 2 + np.arange(_b, dtype=np.int32)) % _b
        _w     = np.take_along_axis(hist, _idx, axis=-1).astype(np.float64)
        _coord = np.arange(_b, dtype=np.float64) - _b // 2       # (B,) mode 기준 offset
    else:
        _w     = hist.astype(np.float64)
        _coord = np.arange(_b, dtype=np.float64)                 # (B,) 절대 bin

    _cw  = np.cumsum(_w, axis=-1)                                # (..., B) 누적 가중
    _tot = _cw[..., -1:]                                         # (..., 1) 총 표본

    def _q(p: float) -> np.ndarray:                             # 가중 분위수 (좌표 오름차순)
        _k = np.argmax(_cw >= _tot * p, axis=-1)                # 누적이 p 넘는 첫 bin
        return _coord[_k]

    _med   = _q(0.5)
    _sigma = (_q(0.75) - _q(0.25)) / 1.349                       # IQR → σ (robust)
    _mean  = (_mode.astype(np.float64) + _med) % _b if circular else _med

    _ok    = _tot[..., 0] > 0                                    # 표본 없는 위치 = 0
    _mean  = np.where(_ok, _mean,  0.0)
    _sigma = np.where(_ok, _sigma, 0.0)
    return _mean.astype(np.float32), _sigma.astype(np.float32)


@PROCESS_REGISTRY.Register_module()
@dataclass
class Robust_Chroma_Stats(Base_Process, outputs=("mean_c0", "mean_c1", "std_c0", "std_c1"), category="색공간/통계"):
    """누산 히스토그램에서 median+IQR robust 통계로 배경 평균/표준편차 4키를 낸다 (finalize 끝단).

    per-frame 루프 후 carry 최종값(누산 히스토그램)을 채널별로 변환 — 1-D면 스칼라 4개,
    ``(H,W,B)``면 ``(H,W)`` 배열 4개. 전역/픽셀별은 앞단 ``accumulate.per_pixel`` 로 갈리고,
    positional bias 등 배경·주의는 ``README.md``. 누산기 없으면 빈 dict("finalize 스킵").
    """

    space: Annotated[str, UI(label="색공간", tip="hsv / lab")] = DEFAULT_SPACE

    def __post_init__(self) -> None:
        self.space = Get_space(self.space)   # str → ChromaSpace

    def Run(
        self, c0_acc: np.ndarray | None = None, c1_acc: np.ndarray | None = None, **kwargs,
    ) -> dict:
        if c0_acc is None or c1_acc is None:
            return {}  # 누산된 프레임 없음 → finalize 스킵 (params 안 씀)
        _cir0, _cir1 = self.space.circular
        _m0, _s0 = _robust_mean_std(c0_acc, circular=_cir0)
        _m1, _s1 = _robust_mean_std(c1_acc, circular=_cir1)
        return {"mean_c0": _m0, "mean_c1": _m1, "std_c0": _s0, "std_c1": _s1}
