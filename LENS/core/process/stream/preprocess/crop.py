from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ....func.cv.geom import Crop_to_mask
from .. import PROCESS_REGISTRY, Base_Process, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Frame_crop(Base_Process, outputs=("crop",), category="전처리/크롭"):
    """``mask`` 가 덮는 영역의 외접 박스로 ``frame`` 을 잘라 ``crop`` 을 낸다.

    계산은 ``func.cv.geom.Crop_to_mask``. mask 가 비면 빈 dict("스킵").
    """

    def Run(self, frame: np.ndarray, mask: GRAY_IMAGE, **kwargs) -> dict:
        _crop = Crop_to_mask(frame, mask)
        return {"crop": _crop} if _crop is not None else {}
