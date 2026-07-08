from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from ..utils.mask import Crop_square, Mask_padding, Make_morph_kernel
from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Normalize_mask(Base_Process, outputs=("mask",), category="마스크/정리"):
    target_shape: Annotated[int, UI(label="출력 크기 (px)", min=32, max=1024)] = 224
    # 전경 픽셀값 스케일 — 1=원본 유지(0/1 이진 그대로), 255=0/255 로 확대해 png 로 보이게.
    # 이진화가 아니라 곱셈(clip 0~255)이라 0/255 mask 를 넣던 기존 사용처는 scale=1 이면 무변.
    scale: Annotated[int, UI(label="값 스케일 (전경 밝기)", min=1, max=255)] = 1

    def Run(self, mask: GRAY_IMAGE, **kwargs) -> dict:
        _crop = Crop_square(mask)
        if _crop.size == 0:
            return {}
        _out = Mask_padding(_crop, self.target_shape)
        if self.scale != 1:
            _out = np.clip(_out.astype(np.int32) * self.scale, 0, 255).astype(np.uint8)
        return {"mask": _out}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Morph_mask(Base_Process, outputs=("mask",), category="마스크/정리"):
    """이진 mask 에 morphology CLOSE 와 OPEN 을 적용한다.

    색공간과 무관한 일반 mask 후처리. 기본은 **CLOSE→OPEN** (작은 구멍을 먼저 메운 뒤 가는
    잡티를 털어낸다). ``reverse`` 면 **OPEN→CLOSE** (잡티를 먼저 털어낸 뒤 구멍을 메운다).
    결과가 비면(전부 0) 빈 dict 를 내 "이 프레임 스킵" 관례를 따른다.
    """

    close_size: Annotated[int,  UI(label="CLOSE 커널 크기 (px)", min=1, max=21)] = 3
    open_size:  Annotated[int,  UI(label="OPEN 커널 크기 (px)",  min=1, max=21)] = 3
    reverse:    Annotated[bool, UI(label="OPEN→CLOSE 순서 (기본 CLOSE→OPEN)")]   = False

    def Run(self, mask: GRAY_IMAGE, **kwargs) -> dict:
        _ops = ((cv2.MORPH_OPEN,  self.open_size), (cv2.MORPH_CLOSE, self.close_size))
        if not self.reverse:                       # 기본: CLOSE → OPEN
            _ops = _ops[::-1]
        _m = mask
        for _op, _size in _ops:
            _m = cv2.morphologyEx(_m, _op, Make_morph_kernel(_size))
        if not _m.any():
            return {}
        return {"mask": _m}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Combine_mask(Base_Process, outputs=("mask",), category="마스크/정리"):
    """``mask`` 와 ``other`` 두 이진 영역을 ``mode`` 로 합친다 (제거/교집합/병합).

    - **subtract** — ``mask & ~other`` (``other`` 를 ``mask`` 에서 뺀다). 예: 컨베이어 ROI 에서
      SAM3 segment 를 빼 belt 만 남긴다.
    - **intersect** — ``mask & other`` (겹치는 부분만).
    - **union** — ``mask | other`` (둘 중 하나라도 켜진 곳, 켜진 값은 두 값의 max).

    색공간·출처와 무관한 일반 연산이다. ``other`` 가 없으면 무연산 통과, 결과가 비면(전부 0)
    빈 dict 를 내 "이 프레임 스킵" 관례를 따른다.

    ``max_change`` (``[-1,1]``, 0=무제한) 은 면적 변화율 ``(new-old)/old`` 의 한계다 — 축소 연산
    (subtract/intersect)은 **음수** 한계로 "너무 많이 지워짐", 병합(union)은 **양수** 한계로
    "너무 많이 커짐" 을 막는다(부호가 mode 와 자연히 짝지어져 반대 부호 한계는 무효). 한계를 넘으면
    ``drop_on_over`` 로 갈린다: True 면 프레임 스킵(빈 dict), False 면 연산을 취소하고 원본 ``mask``
    를 그대로 통과한다.
    """

    mode:         Annotated[str,   UI(label="합성 모드", tip="subtract / intersect / union")]        = "subtract"
    max_change:   Annotated[float, UI(label="면적 변화율 한계 (0=무제한)", min=-1.0, max=1.0, step=0.05)] = 0.0
    drop_on_over: Annotated[bool,  UI(label="한계 초과 시 프레임 스킵 (끄면 원본 통과)")]                 = False

    def Run(self, mask: GRAY_IMAGE, other: GRAY_IMAGE | None = None, **kwargs) -> dict:
        if other is None:                                  # 상대 영역 없음 → 무연산 통과
            _out = mask
        elif self.mode == "subtract":
            _out = np.where(other > 0, np.uint8(0), mask)  # mask & ~other
        elif self.mode == "intersect":
            _out = np.where(other > 0, mask, np.uint8(0))  # mask & other
        elif self.mode == "union":
            _out = np.maximum(mask, other)                 # mask | other
        else:
            raise ValueError(f"{type(self).__name__}: 알 수 없는 mode {self.mode!r} "
                             "(subtract / intersect / union)")

        if self.max_change:                                # 면적 변화율 한계 검사
            _old = int(np.count_nonzero(mask))
            if _old:
                _ratio = (int(np.count_nonzero(_out)) - _old) / _old
                _over  = (_ratio > self.max_change if self.max_change > 0
                          else _ratio < self.max_change)
                if _over:                                  # 한계 초과 → 스킵 or 원본 통과
                    return {} if self.drop_on_over else {"mask": mask}

        if not _out.any():
            return {}  # 결과 비면(전부 0) "이 프레임 스킵" 관례
        return {"mask": _out}
