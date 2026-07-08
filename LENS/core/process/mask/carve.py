"""color floodFill 로 mask 관통부(구멍/슬릿) 제거 — 몸통색 편차 seed + LoG 벽.

SAM ``segment`` 는 구멍 메워진 solid 로 나오므로, 그 안에서 **몸통 평균색과 크게 다르고 LoG 벽에
갇힌** 영역을 구멍으로 보고 뺀다(``utils.fill.color_holes`` — 편집기 fill 과 같은 cv2.floodFill).
반사광은 RGB 밝기 임계(``highlight_thr``)로 seed 에서 빼고, 남은 작은 flood 는 morphology open 으로
턴다. Mahalanobis·Pass-2 없이 순수 CV. ``remove_edge_holes`` 와 같은 자리(frame+mask→carved mask).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, GRAY_IMAGE
from ..utils.fill import color_holes


@PROCESS_REGISTRY.Register_module()
@dataclass
class Carve_color_holes(Base_Process, outputs=("mask",), category="마스크/정리"):
    """mask 안에서 몸통색과 확 다른 관통부를 LoG 벽 + color floodFill 로 빼낸다 (``mask & ~구멍``).

    mask 영역 평균색에서 ``dev_thr`` 이상 벗어난 픽셀을 seed 로 floodFill 해 구멍을 찾고 carve 한다.
    반사광은 ``highlight_thr``(RGB 평균 밝기) 이상 seed 제외 + morphology open(``open_size``)으로 제거.
    결과가 비면 스킵(``{}``). SAM ``segment`` 뒤에 붙여 구멍/슬릿을 다시 뚫는 용도.
    """

    dev_thr:    Annotated[int, UI(label="몸통색 편차 seed 임계", tip="mask 평균색에서 이보다 크게 다른 픽셀만 seed", min=0, max=255)] = 40
    tolerance:  Annotated[int, UI(label="floodFill 색 허용 (seed 대비 ±)", min=0, max=255)]        = 20
    highlight_thr: Annotated[float, UI(label="반사광 제외 RGB 평균 (0=끄기)", tip="이 밝기 이상 픽셀을 seed 에서 제외", min=0.0, max=255.0, step=5.0)] = 0.0
    open_size:  Annotated[int, UI(label="morphology OPEN (px, 반사광/잡티 제거)", min=1, max=31)]  = 5
    log_sigma:  Annotated[float, UI(label="LoG σ (벽 블러)", min=0.1, max=10.0, step=0.1)]          = 1.2
    log_factor: Annotated[float, UI(label="LoG 임계 배수 (클수록 벽 성김)", min=0.1, max=10.0, step=0.1)] = 1.0
    grow:       Annotated[int, UI(label="경계 밴드 회복 (px, LoG 벽 보정)", min=0, max=20)]         = 2
    min_area:   Annotated[int, UI(label="최소 구멍 면적 (px, 미만 무시)", min=0, max=10000)]        = 50

    def Run(self, frame: np.ndarray, mask: GRAY_IMAGE, **kwargs) -> dict:
        _m255 = (np.asarray(mask) > 0).astype(np.uint8) * np.uint8(255)
        if not _m255.any():
            return {}
        _hole = color_holes(
            frame, _m255, dev_thr=self.dev_thr, tolerance=self.tolerance,
            sigma=self.log_sigma, factor=self.log_factor,
            highlight_thr=self.highlight_thr, open_size=self.open_size,
            grow=self.grow, min_area=self.min_area)
        _out = cv2.bitwise_and(_m255, cv2.bitwise_not(_hole))                   # mask & ~구멍
        if not _out.any():
            return {}
        return {"mask": _out}
