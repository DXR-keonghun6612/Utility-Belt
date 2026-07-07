from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Detect_edge(Base_Process, outputs=("edge",), category="엣지/탐색"):
    """raw 프레임에서 cv2 Canny edge(0/255)를 뽑는다. gray 한 장(기본) / 채널별 OR(``gray=False``).

    선택 근거·배경은 ``README.md``. 검출 전 옵션 Gaussian blur. 결과가 비면 빈 dict("스킵").
    """

    low:  Annotated[int, UI(label="Canny 하한 임계", min=0, max=500)]            = 50
    high: Annotated[int, UI(label="Canny 상한 임계", min=0, max=500)]            = 150
    blur: Annotated[int, UI(label="Gaussian blur 커널 (홀수, 1=생략)", min=1, max=21)] = 3
    gray: Annotated[bool, UI(label="gray 변환 후 검출 (끄면 채널별 OR)",
                             tip="표준 방식 — gray 한 장에서 Canny. 끄면 채널별 Canny 를 OR 로 합쳐 색경계도 잡음")] = True

    def Run(self, frame: np.ndarray, **kwargs) -> dict:
        if frame.ndim == 3:
            _chans = (cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),) if self.gray else cv2.split(frame)
        else:
            _chans = (frame,)
        _edge: GRAY_IMAGE | None = None
        for _c in _chans:
            if self.blur > 1:
                _k = self.blur | 1                   # 짝수면 +1 (Gaussian 커널은 홀수)
                _c = cv2.GaussianBlur(_c, (_k, _k), 0)
            _e = cv2.Canny(_c, self.low, self.high)
            _edge = _e if _edge is None else cv2.bitwise_or(_edge, _e)
        if _edge is None or not _edge.any():
            return {}
        return {"edge": _edge}
