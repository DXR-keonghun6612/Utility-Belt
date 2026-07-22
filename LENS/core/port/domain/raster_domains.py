"""raster 계열 도메인 — ``image`` (사진).

BGR 사진을 그대로 싣고 내린다. png/jpg 확장자를 **추론에 쓴다**(관행상 png = 사진). mask(픽셀 영역)는
별도 도메인([`mask`](mask.py))이라 여기 없다 — png 하나로 사진인지 마스크인지 알 수 없어 그쪽은 추론을
안 한다(``type: mask`` 명시를 요구).

**옛 ``segmap``(다객체 라벨맵) 도메인은 삭제됐다** — 정본이 객체별 mask 라 라벨맵은 저장 표현이 아니라
transient 계산·표시 중간물일 뿐이다(라벨맵↔per-obj mask 합성은 [`func.mask`](../../func/mask/instance.py)).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from . import DOMAIN_REGISTRY
from ._base import Domain

_RASTER_FORMATS = ("png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp")


@DOMAIN_REGISTRY.Register_module("image")
class Image_Domain(Domain):
    """사진 — BGR raster."""

    FORMATS:   ClassVar[tuple[str, ...]] = _RASTER_FORMATS
    INFERABLE: ClassVar[bool]            = True    # png/jpg → image (관행)

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """위치 있는 storage 요청의 ndarray → png 파일."""
        return 3 if (storage and not params and isinstance(value, np.ndarray)) else 0

    @classmethod
    def Can_visualize(cls) -> bool:
        return True

    @classmethod
    def Blank(cls, *, size=None):
        """빈 이미지 — 검은 BGR 3채널 (``size`` = (H, W) 필수)."""
        if size is None:
            raise ValueError("image 빈 객체는 size(H, W)가 필요합니다")
        return np.zeros((*size, 3), np.uint8)
