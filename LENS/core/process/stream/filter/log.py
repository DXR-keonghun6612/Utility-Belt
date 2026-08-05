from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE
from ....func.cv.filter import log_edges


@PROCESS_REGISTRY.Register_module()
@dataclass
class Detect_log_edge(Base_Process, outputs=("edge",), category="필터/탐색"):
    """raw 프레임에서 LoG(Laplacian of Gaussian) edge 벽(0/255)을 뽑는다 — ``func.cv.filter.log_edges``.

    ``Detect_edge``(Canny)와 같은 ``edge`` 를 내는 형제 producer다 — refine/cut 이 벽으로 쓰는 것은
    "변화량 edge" 하나이고, 그 방법론(LoG↔Canny↔…)을 config 에서 producer 블록으로 갈아끼운다.
    소비 측(``func.mask.refine``)은 벽이 어떻게 났는지 모른다(색 기준만 안쪽에서 소유).

    **프레임 전체에서 한 번** 계산한다 — LoG 응답은 지역 커널이라 crop 이든 전체든 같지만, 적응형
    임계 ``factor × std`` 의 ``std`` 는 표본 범위에 따라 달라진다. 프레임 전체로 재야 객체마다 벽의
    성김이 흔들리지 않고 GUI magic-wand 와 같은 벽이 선다. 결과가 비면 빈 dict("스킵").
    """

    log_sigma:  Annotated[float, UI(label="LoG σ", tip="벽 블러 정도 (가우시안 시그마)", min=0.1, max=10.0, step=0.1)]                 = 1.2
    log_factor: Annotated[float, UI(label="LoG 임계 배수", tip="클수록 벽이 성겨 더 넓게 번진다", min=0.1, max=10.0, step=0.1)] = 1.0

    def Run(self, frame: np.ndarray, **kwargs) -> dict:
        _edge = log_edges(frame, sigma=self.log_sigma, factor=self.log_factor)
        _out: GRAY_IMAGE = _edge.astype(np.uint8) * np.uint8(255)
        return {"edge": _out} if _out.any() else {}
