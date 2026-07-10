from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ...func.cv.color import Flatten_brightness
from .. import PROCESS_REGISTRY, Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Normalize_color(Base_Process, outputs=("norm_image",), category="전처리/색보정"):
    """조명 정규화 — 명도를 상수로 덮어 밝기 경계를 지운다(``func.cv.color.Flatten_brightness``).

    색 경계만 남으므로 뒤따르는 ``detect_edge`` 의 입력(``norm_image``)이 된다.
    """

    value: Annotated[int, UI(label="고정 명도 (V)", min=1, max=255,
                             tip="HSV V 채널을 이 값으로 덮어 밝기 변화를 제거")] = 255

    def Run(self, frame: np.ndarray, **kwargs) -> dict:
        return {"norm_image": Flatten_brightness(frame, self.value)}
