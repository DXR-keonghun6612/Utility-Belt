from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ...func.cv.filter import Canny_edges
from .. import PROCESS_REGISTRY, Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Detect_edge(Base_Process, outputs=("edge",), category="필터/탐색"):
    """raw 프레임에서 Canny edge(0/255)를 뽑는다 — ``func.cv.filter.Canny_edges``.

    gray 한 장(기본) / 채널별 OR(``gray=False``). 결과가 비면 빈 dict("스킵").
    """

    low:  Annotated[int, UI(label="Canny 하한 임계", min=0, max=500)]            = 50
    high: Annotated[int, UI(label="Canny 상한 임계", min=0, max=500)]            = 150
    blur: Annotated[int, UI(label="Gaussian blur 커널 (홀수, 1=생략)", min=1, max=21)] = 3
    gray: Annotated[bool, UI(label="gray 변환 후 검출 (끄면 채널별 OR)",
                             tip="표준 방식 — gray 한 장에서 Canny. 끄면 채널별 Canny 를 OR 로 합쳐 색경계도 잡음")] = True

    def Run(self, frame: np.ndarray, **kwargs) -> dict:
        _edge = Canny_edges(frame, low=self.low, high=self.high, blur=self.blur, gray=self.gray)
        return {"edge": _edge} if _edge is not None else {}
