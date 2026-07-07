from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Normalize_color(Base_Process, outputs=("norm_image",), category="전처리/색보정"):
    """조명 정규화 — HSV V(명도)를 상수(``value``)로 덮어 밝기 변화를 지운다(색 경계만 남김).

    배경·용도는 ``README.md``.
    """

    value: Annotated[int, UI(label="고정 명도 (V)", min=1, max=255,
                             tip="HSV V 채널을 이 값으로 덮어 밝기 변화를 제거")] = 255

    def Run(self, frame: np.ndarray, **kwargs) -> dict:
        _hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        _hsv[..., 2] = self.value
        return {"norm_image": cv2.cvtColor(_hsv, cv2.COLOR_HSV2BGR)}
