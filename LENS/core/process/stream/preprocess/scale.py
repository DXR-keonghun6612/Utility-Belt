"""작업 해상도 스케일 관리 — 큰 이미지를 줄여 CV 를 돌리고 결과를 원본 크기로 되돌린다.

큰 프레임(4000px+)은 고정 커널(canny·clahe·morphology)이 해상도에 안 맞고 느리다. ``Downscale`` 이
canonical 해상도로 줄여 ``source_hw``(원본 크기)를 ctx 로 흘리고, 사이 step 들이 작은 프레임에서 처리한
뒤 ``Upscale`` 이 결과를 그 크기로 되돌린다(라벨 보존). 계산은 ``func.cv.geom`` 의 resize primitive.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from ...func.cv.geom import Resize_to, Resize_within
from .. import PROCESS_REGISTRY, Base_Process, UI, IMAGE, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Downscale(Base_Process, outputs=("frame", "source_hw"), category="전처리/스케일"):
    """``frame`` 을 ``max_side`` 이하로 축소하고 원본 크기를 ``source_hw`` 로 흘린다.

    출력 ``frame`` 은 ctx 를 덮어 이후 step 이 그대로 작은 프레임을 받는다 — 원본 크기는 ``source_hw``
    (원본 ``(H,W)``)가 들고, 뒤의 ``Upscale`` 이 그걸로 결과를 되돌린다. 이미 작으면 무변경(축소만 함).
    """

    max_side: Annotated[int, UI(label="최대 변 (px)", min=64, max=8192,
                                tip="이보다 크면 비율 유지로 축소 — 작으면 그대로")] = 1024

    def Run(self, frame: IMAGE, **kwargs) -> dict:
        return {"frame": Resize_within(frame, self.max_side),
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

    def Run(self, mask: GRAY_IMAGE, source_hw=None, **kwargs) -> dict:
        if source_hw is None:
            raise KeyError("Upscale: source_hw 가 ctx 에 없다 — 앞에 downscale 을 둬야 한다")
        _full = Resize_to(mask, source_hw, nearest=True)
        return {"mask": _full} if _full.any() else {}
