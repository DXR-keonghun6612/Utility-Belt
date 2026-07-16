from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from ....func.cv.color import Scale_intensity
from ....func.cv.filter import Morph_clean
from ....func.cv.geom import Crop_square, Mask_padding
from ....func.mask.combine import Area_change, Combine_regions
from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Normalize_mask(Base_Process, outputs=("mask",), category="마스크/정리"):
    """mask 를 정사각으로 crop 후 ``target_shape`` 로 pad 한다 (분류기 입력 규격화)."""

    target_shape: Annotated[int, UI(label="출력 크기 (px)", min=32, max=1024)] = 224
    # 전경 픽셀값 스케일 — 1=원본 유지(0/1 이진 그대로), 255=0/255 로 확대해 png 로 보이게.
    scale: Annotated[int, UI(label="값 스케일 (전경 밝기)", min=1, max=255)] = 1

    def Run(self, mask: GRAY_IMAGE, **kwargs) -> dict:
        _crop = Crop_square(mask)
        if _crop.size == 0:
            return {}
        return {"mask": Scale_intensity(Mask_padding(_crop, self.target_shape), self.scale)}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Morph_mask(Base_Process, outputs=("mask",), category="마스크/정리"):
    """이진 mask 에 morphology CLOSE 와 OPEN 을 적용한다 — ``func.cv.filter.Morph_clean``.

    결과가 비면(전부 0) 빈 dict 를 내 "이 프레임 스킵" 관례를 따른다.
    """

    close_size: Annotated[int,  UI(label="CLOSE 커널 크기 (px)", min=1, max=21)] = 3
    open_size:  Annotated[int,  UI(label="OPEN 커널 크기 (px)",  min=1, max=21)] = 3
    reverse:    Annotated[bool, UI(label="OPEN→CLOSE 순서 (기본 CLOSE→OPEN)")]   = False

    def Run(self, mask: GRAY_IMAGE, **kwargs) -> dict:
        _m = Morph_clean(mask, close_size=self.close_size,
                         open_size=self.open_size, reverse=self.reverse)
        return {"mask": _m} if _m.any() else {}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Combine_mask(Base_Process, outputs=("mask",), category="마스크/정리"):
    """``mask`` 와 ``other`` 를 ``mode`` 로 합친다 — ``func.mask.combine.Combine_regions``.

    합성 자체는 primitive 가 하고, 이 유닛은 **결과를 받아들일지**만 정한다. ``max_change``
    (``[-1,1]``, 0=무제한)는 면적 변화율 한계이고, 넘으면 ``drop_on_over`` 로 갈린다 — True 면 프레임
    스킵(빈 dict), False 면 연산을 취소하고 원본 ``mask`` 를 통과시킨다. ``other`` 가 없으면 무연산
    통과, 결과가 비면 스킵.
    """

    mode:         Annotated[str,   UI(label="합성 모드", tip="subtract / intersect / union")]        = "subtract"
    max_change:   Annotated[float, UI(label="면적 변화율 한계 (0=무제한)", min=-1.0, max=1.0, step=0.05)] = 0.0
    drop_on_over: Annotated[bool,  UI(label="한계 초과 시 프레임 스킵 (끄면 원본 통과)")]                 = False

    def Run(self, mask: GRAY_IMAGE, other: GRAY_IMAGE | None = None, **kwargs) -> dict:
        _out = mask if other is None else Combine_regions(mask, other, self.mode)

        if self.max_change:                                # 면적 변화율 한계 검사
            _ratio = Area_change(mask, _out)
            if _ratio is not None:
                _over = (_ratio > self.max_change if self.max_change > 0
                         else _ratio < self.max_change)
                if _over:                                  # 한계 초과 → 스킵 or 원본 통과
                    return {} if self.drop_on_over else {"mask": mask}

        return {"mask": _out} if _out.any() else {}
