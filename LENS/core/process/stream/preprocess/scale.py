"""작업 해상도 스케일 관리 — 큰 이미지를 줄여 CV 를 돌리고 결과를 원본 크기로 되돌린다.

큰 프레임(4000px+)은 고정 커널(canny·clahe·morphology)이 해상도에 안 맞고 느리다. ``Downscale`` 이
``ratio`` 배로 줄여 ``source_hw``(원본 크기)를 ctx 로 흘리고, 사이 step 들이 작은 프레임에서 처리한
뒤 ``Upscale`` 이 결과를 그 크기로 되돌린다(라벨 보존). 계산은 ``func.cv.geom`` 의 resize primitive.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from ....func.cv.geom import (
    Resize_by, Resize_to, DEFAULT_DOWN_INTERP, DEFAULT_LABEL_INTERP)
from .. import PROCESS_REGISTRY, Base_Process, UI, IMAGE, GRAY_IMAGE

_INTERP_TIP = "area / linear / cubic / nearest / lanczos"


@PROCESS_REGISTRY.Register_module()
@dataclass
class Downscale(Base_Process, outputs=("frame", "source_hw"), category="전처리/스케일"):
    """``frame`` 을 ``ratio`` 배로 축소하고 원본 크기를 ``source_hw`` 로 흘린다.

    출력 ``frame`` 은 ctx 를 덮어 이후 step 이 그대로 작은 프레임을 받는다 — 원본 크기는 ``source_hw``
    (원본 ``(H,W)``)가 들고, 뒤의 ``Upscale`` 이 그걸로 결과를 되돌린다. ``ratio=1.0`` 이면 무변경.
    """

    ratio:  Annotated[float, UI(label="축소 비율", min=0.05, max=1.0, step=0.05,
                                tip="0.5 면 반으로 — 1.0 이면 그대로")] = 0.5
    interp: Annotated[str,   UI(label="보간", tip=_INTERP_TIP)]        = DEFAULT_DOWN_INTERP

    def Run(self, frame: IMAGE, **kwargs) -> dict:
        return {"frame": Resize_by(frame, self.ratio, self.interp),
                "source_hw": tuple(frame.shape[:2])}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Upscale(Base_Process, outputs=("mask",), category="전처리/스케일"):
    """작은 해상도에서 만든 ``mask`` 를 ``source_hw``(원본 크기)로 되돌린다 — 라벨 보존 NEAREST.

    ``Downscale`` 의 짝. mask 는 라벨맵이라 NEAREST 로 되돌려 값(obj_id+1)을 섞지 않는다. ``source_hw``
    가 ctx 에 없으면(=Downscale 을 앞에 안 뒀으면) 되돌릴 크기가 없어 **실패**한다(조용한 통과 없음).
    bbox·좌표를 내는 step(``split_objects`` 등)은 이 뒤(원본 크기)에서 돌려야 좌표가 원본 기준이 된다.
    결과가 비면 스킵.
    """

    interp: Annotated[str, UI(label="보간", tip=_INTERP_TIP)] = DEFAULT_LABEL_INTERP

    def Run(self, mask: GRAY_IMAGE, source_hw=None, **kwargs) -> dict:
        if source_hw is None:
            raise KeyError("Upscale: source_hw 가 ctx 에 없다 — 앞에 downscale 을 둬야 한다")
        _full = Resize_to(mask, source_hw, self.interp)
        return {"mask": _full} if _full.any() else {}
