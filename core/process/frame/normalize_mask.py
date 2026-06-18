"""mask bbox crop → 고정 크기 canvas 중앙 배치 process."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process, GRAY_IMAGE
from ..utils.mask import Crop_square, Mask_padding


NAME = "normalize_mask"


@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Normalize_mask_config(Base_Config):
    config_type:  str = f"{NAME}_config"
    object_type:  str = NAME
    target_shape: int = 224


@pipeline_registry.Register_module(NAME)
@dataclass
class Normalize_mask_process(Base_Process):
    """mask를 bbox로 crop하고 target_shape 크기 canvas 중앙에 배치한다."""

    name:         str = NAME
    target_shape: int = 224

    INPUTS:  ClassVar[tuple[str, ...]] = ("mask",)
    OUTPUTS: ClassVar[tuple[str, ...]] = ("mask",)

    def Run(
        self,
        mask: GRAY_IMAGE,
        **kwargs,
    ) -> dict:
        _crop = Crop_square(mask)
        if _crop.size == 0:
            return {}
        return {"mask": Mask_padding(_crop, self.target_shape)}
