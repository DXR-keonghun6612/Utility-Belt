"""LoG 벽 + 배경 color floodFill 로 프레임에서 객체 raw mask 를 뽑는다.

알고리즘·근거는 ``func.mask.flood.Flood_background``. 이 유닛은 ``roi`` 를 영역 bool 로 풀어 넘긴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from .. import PROCESS_REGISTRY, Base_Process, UI, BBOX, GRAY_IMAGE
from ....func.cv.geom import Roi_to_mask
from ....func.mask.flood import Flood_background as Flood_background_mask


@PROCESS_REGISTRY.Register_module()
@dataclass
class Flood_background(Base_Process, outputs=("mask",), category="마스크/추출"):
    """``roi`` 안의 배경(벨트)을 color floodFill 로 채우고 반전해 객체 raw mask 를 만든다.

    산출물의 쓰임은 실루엣이 아니라 **뒤따르는 ``split_objects`` 의 객체 bbox**(SAM3 box 프롬프트).
    ``roi`` 가 없으면 프레임 전체를 대상으로 한다. 인자 의미는 ``func.mask.flood.Flood_background``.
    결과가 비면 스킵(``{}``).
    """

    belt_dev:   Annotated[int, UI(label="벨트 seed 판정 (기준색 편차 이내)", tip="이 안쪽 픽셀만 seed — 객체는 색이 멀어 제외", min=0, max=255)] = 60
    tolerance:  Annotated[int, UI(label="floodFill 색 허용 (이웃 픽셀 대비 ±)", min=0, max=255)]   = 4
    seeds:      Annotated[int, UI(label="seed 표본 수 (roi 에서 고르게)", min=1, max=512)]         = 64
    log_sigma:  Annotated[float, UI(label="LoG σ (벽 블러)", min=0.1, max=10.0, step=0.1)]         = 1.2
    log_factor: Annotated[float, UI(label="LoG 임계 배수 (클수록 벽 성김)", min=0.1, max=10.0, step=0.1)] = 1.0
    roi_margin: Annotated[int, UI(label="roi 침식 (px, 경계 edge 제외)", min=0, max=50)]           = 3
    open_size:  Annotated[int, UI(label="morphology OPEN (px, 벨트 잡티 제거)", min=1, max=31)]    = 9
    shrink:     Annotated[int, UI(label="실루엣 벽 두께 보정 침식 (px, 0=끄기)", min=0, max=20)]   = 1
    min_area:   Annotated[int, UI(label="최소 객체 면적 (px², 0=끄기)", min=0, max=100000)]        = 500

    def Run(self, frame: np.ndarray, roi: BBOX | GRAY_IMAGE | None = None, **kwargs) -> dict:
        _out = Flood_background_mask(
            frame, Roi_to_mask(roi, frame.shape[:2]),            # None = 프레임 전체
            belt_dev=self.belt_dev, tolerance=self.tolerance, seeds=self.seeds,
            log_sigma=self.log_sigma, log_factor=self.log_factor, roi_margin=self.roi_margin,
            open_size=self.open_size, shrink=self.shrink, min_area=self.min_area)
        return {"mask": _out} if _out is not None else {}
