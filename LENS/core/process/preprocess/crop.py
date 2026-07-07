from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import PROCESS_REGISTRY
from .._base import Base_Process, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Frame_crop(Base_Process, outputs=("crop",), category="전처리/크롭"):
    def Run(self, frame: np.ndarray, mask: GRAY_IMAGE, **kwargs) -> dict:
        _coords = np.argwhere(mask > 0)
        if _coords.size == 0:
            return {}
        _min = _coords.min(axis=0)
        _max = _coords.max(axis=0) + 1
        return {"crop": frame[_min[0]:_max[0], _min[1]:_max[1]]}
