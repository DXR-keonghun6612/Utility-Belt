"""mask 도메인 — **단일 객체** 이진 마스크. 정준형 = 이진 uint8 ``(H, W)``.

이 도메인이 **여러 포맷을 갖는 첫 자리**다 — 같은 마스크를 rle·polygon(인라인) · png·npy(파일)로 담는다.
표현이 달라도 **같은 것**(그 객체가 덮는 픽셀 영역)이라, 포맷은 정준형을 경유해 서로 오간다
(``Load`` 로 이진 배열로 풀고 다른 포맷으로 ``Save``). 그래서 SAM 처럼 **폴리곤을 내는 생산자**도
마스크를 내는 생산자와 같은 도메인에 들어온다 — codec 파일 하나 + ``FORMATS`` 한 줄이면 붙는다.

**다객체 라벨맵은 ``segmap`` 이다** — 카디널리티가 다르다(마스크 하나 vs 객체 N개 한 장). 둘을 한 도메인에
두면 "라벨맵을 rle 로" 같은 정의 불가한 변환이 생긴다.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from . import DOMAIN_REGISTRY
from ._base import Domain


@DOMAIN_REGISTRY.Register_module("mask")
class Mask_Domain(Domain):
    """단일 객체 이진 마스크 — rle·polygon(인라인) / png·npy(파일)."""

    FORMATS:   ClassVar[tuple[str, ...]] = ("rle", "polygon", "png", "npy")
    INFERABLE: ClassVar[bool]            = False   # png 는 image 와 구분 불가 → type 명시

    @classmethod
    def Canonicalize(cls, value: Any) -> Any:
        """이진 uint8 ``(H, W)`` 로 — 다채널이면 첫 채널, 0/1 로 이진화(255 저장본도 1 로).

        **배열 payload 에만 적용된다** — codec 의 네이티브 표현(SAM 이 바로 내는 polygon dict 등)은 그대로
        통과시켜 codec 이 해석한다. 생산자가 이미 그 포맷으로 낸 것을 배열로 오인해 부수지 않기 위함이다.
        """
        if not isinstance(value, np.ndarray):
            return value
        _m = value[..., 0] if value.ndim == 3 else value
        return (_m > 0).astype(np.uint8)

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """위치 있는 **인라인** 2D+ ndarray = 단일 마스크 → 기본 포맷(rle)."""
        return 3 if (not storage and not params
                     and isinstance(value, np.ndarray) and value.ndim >= 2) else 0

    @classmethod
    def Can_visualize(cls) -> bool:
        return True

    @classmethod
    def Blank(cls, *, size=None):
        """빈 마스크 — 2D uint8 영배열."""
        if size is None:
            raise ValueError("mask 빈 객체는 size(H, W)가 필요합니다")
        return np.zeros(size, np.uint8)
