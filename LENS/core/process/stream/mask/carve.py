"""color floodFill 로 SAM segment 의 관통부(구멍/슬릿)를 제거 — 평균 특이치 + 국소 배경색 + LoG 벽.

알고리즘·라벨별 처리의 근거는 ``func.mask.fill.Carve_holes_by_label``. 이 유닛은 프레임당 1회 LoG 벽을
구해 넘긴다(라벨마다 다시 구하지 않는다).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE
from ....func.cv.filter import log_edges
from ....func.mask.fill import Carve_holes_by_label


@PROCESS_REGISTRY.Register_module()
@dataclass
class Carve_color_holes(Base_Process, outputs=("segment",), category="마스크/정리"):
    """``segment`` 라벨맵의 각 객체에서 관통부를 LoG 벽 + color floodFill 로 빼낸다 (obj_id 보존).

    ``bg_tol`` 이 반사광을 뺀다 — 절대 밝기 임계는 부품 색에 종속돼 쓰지 않는다. 인자 의미는
    ``func.mask.fill.Carve_holes_by_label``. 모든 라벨이 빈 결과면 스킵(``{}``).
    """

    k:          Annotated[float, UI(label="평균 특이치 배수 (mean + k·std)", tip="클수록 seed 가 보수적", min=0.0, max=10.0, step=0.1)] = 2.0
    bg_tol:     Annotated[int, UI(label="국소 배경색 근접 허용 (반사광 배제)", min=0, max=255)]      = 50
    ring:       Annotated[int, UI(label="배경색 표본 링 폭 (px, 객체 바깥)", min=1, max=100)]        = 25
    tolerance:  Annotated[int, UI(label="floodFill 색 허용 (seed 대비 ±)", min=0, max=255)]          = 20
    log_sigma:  Annotated[float, UI(label="LoG σ (벽 블러)", min=0.1, max=10.0, step=0.1)]           = 1.2
    log_factor: Annotated[float, UI(label="LoG 임계 배수 (클수록 벽 성김)", min=0.1, max=10.0, step=0.1)] = 1.0
    open_size:  Annotated[int, UI(label="morphology OPEN (px, 잡티 제거)", min=1, max=31)]           = 5
    grow:       Annotated[int, UI(label="경계 밴드 회복 (px, LoG 벽 보정)", min=0, max=20)]          = 2
    min_area:   Annotated[int, UI(label="최소 구멍 면적 (px, 미만 무시)", min=0, max=10000)]         = 50

    def Run(self, frame: np.ndarray, segment: GRAY_IMAGE, **kwargs) -> dict:
        _walls = log_edges(frame, sigma=self.log_sigma, factor=self.log_factor)   # 프레임당 1회
        _out = Carve_holes_by_label(
            frame, segment, walls=_walls, k=self.k, bg_tol=self.bg_tol, ring=self.ring,
            tolerance=self.tolerance, open_size=self.open_size, grow=self.grow,
            min_area=self.min_area)
        return {"segment": _out} if _out is not None else {}
