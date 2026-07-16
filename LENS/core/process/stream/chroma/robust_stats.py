from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ....func.chroma._space import Get_space, DEFAULT_SPACE
from ....func.chroma._core import Robust_mean_std
from .. import PROCESS_REGISTRY, Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Robust_Chroma_Stats(Base_Process, outputs=("mean_c0", "mean_c1", "std_c0", "std_c1"), category="색공간/통계"):
    """누산 히스토그램에서 robust 통계로 배경 평균/표준편차 4키를 낸다 (finalize 끝단).

    추정기·근거(median + IQR, mode-window 실패 이력)는 ``func.chroma._core.Robust_mean_std``.
    per-frame 루프 후 carry 최종값을 채널별로 변환 — 1-D면 스칼라 4개, ``(H,W,B)``면 ``(H,W)`` 배열
    4개. 전역/픽셀별은 앞단 ``accumulate.per_pixel`` 로 갈린다. 누산기 없으면 빈 dict("finalize 스킵").
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
        _m0, _s0 = Robust_mean_std(c0_acc, circular=_cir0)
        _m1, _s1 = Robust_mean_std(c1_acc, circular=_cir1)
        return {"mean_c0": _m0, "mean_c1": _m1, "std_c0": _s0, "std_c1": _s1}
