"""mask bounding box 기준 단일 프레임 crop process."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process, GRAY_IMAGE


NAME = "frame_crop"


@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Frame_crop_config(Base_Config):
    config_type: str = f"{NAME}_config"
    object_type: str = NAME


@pipeline_registry.Register_module(NAME)
@dataclass
class Frame_crop_process(Base_Process):
    """mask의 bounding box에 맞춰 frame을 crop한다."""

    name: str = NAME

    INPUTS:  ClassVar[tuple[str, ...]] = ("frame", "mask")
    OUTPUTS: ClassVar[tuple[str, ...]] = ("crop",)

    def Run(
        self,
        frame: np.ndarray,
        mask:  GRAY_IMAGE,
        **kwargs,
    ) -> dict[str, np.ndarray]:
        _coords = np.argwhere(mask > 0)
        if _coords.size == 0:
            return {}

        _min = _coords.min(axis=0)
        _max = _coords.max(axis=0) + 1
        return {"crop": frame[_min[0]:_max[0], _min[1]:_max[1]]}
