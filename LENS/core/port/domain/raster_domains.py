"""raster 계열 도메인 — ``image`` (사진) · ``segmap`` (다객체 인스턴스 라벨맵).

둘 다 png 를 쓰지만 **의미가 다르다** — 그 차이가 정확히 도메인이 드는 것이다:

- ``image``  — BGR 사진. 그대로 싣고 내린다. png/jpg 확장자를 **추론에 쓴다**(관행상 png = 사진).
- ``segmap`` — 픽셀값이 색이 아니라 **객체 id + 1** 인 단일채널 라벨맵(0 = 배경). 그래서 정준형이
  단일채널 uint8 이고, 다채널로 저장돼 있어도 첫 채널만 취한다. 확장자 추론은 **안 한다** — png 하나로
  사진인지 라벨맵인지 알 수 없어, 추론은 곧 조용히 하나를 고르는 일이다(``type: segmap`` 명시를 요구).

라벨맵↔per-obj mask 합성(``라벨 = id+1``)은 port 가 아니라
[`process.func.mask`](../../process/func/mask/instance.py) 소유 — 그건 배열↔배열 계산이라 ``Data_Ref`` 가 없다.
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


@DOMAIN_REGISTRY.Register_module("segmap")
class Segmap_Domain(Domain):
    """인스턴스 라벨맵 — 단일채널 uint8, 픽셀 = obj_id + 1 (0 = 배경). **다객체**(mask 도메인과 다르다)."""

    FORMATS:   ClassVar[tuple[str, ...]] = ("png", "npy")
    INFERABLE: ClassVar[bool]            = False   # png 는 image 와 구분 불가 → type 명시

    @classmethod
    def Canonicalize(cls, value: Any) -> Any:
        """단일채널 uint8 라벨맵으로 — 다채널로 저장됐으면 첫 채널만(라벨은 단일채널이다).

        **배열 payload 에만 적용된다** (codec 네이티브 표현은 그대로 통과 — mask 도메인과 같은 규약).
        """
        if not isinstance(value, np.ndarray):
            return value
        _m = value[..., 0] if value.ndim == 3 else value
        return _m.astype(np.uint8)

    @classmethod
    def Can_visualize(cls) -> bool:
        return True

    @classmethod
    def Blank(cls, *, size=None):
        """빈 라벨맵 — 2D uint8 영배열(모두 배경). image 의 BGR 3채널이 아니라 단일채널이다."""
        if size is None:
            raise ValueError("segmap 빈 객체는 size(H, W)가 필요합니다")
        return np.zeros(size, np.uint8)
