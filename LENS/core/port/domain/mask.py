"""mask 도메인 — **그 객체가 덮는 픽셀 영역.** 여러 포맷이 같은 뜻을 나눠 든다.

같은 영역을 rle·polygon(인라인) · png·npy(파일)로 담는다 — 표현이 달라도 다 "그 객체의 픽셀"이라,
그 **뜻이 하나임을 아는 게 이 도메인의 일**이다. 그래서 SAM 처럼 폴리곤을 내는 생산자도 배열을 내는
생산자와 같은 도메인에 들어온다.

**대표 포맷은 없다.** 한때 정준형(이진 배열)을 정해 ``Load`` 가 폴리곤이든 rle 든 전부 배열로 뭉갰다 —
그래서 폴리곤을 truth 로 들 수가 없었다(편집기가 꼭짓점을 못 봤다). 이제 각 포맷은 자기 구조로 살고,
배열이 **필요한 소비처만** ``To(value, "npy")`` 로 요청한다. 구조 변환의 계산은 [`../../format`](../../format)
이 들고, 도메인은 **어느 것을 쓸지 고르기만** 한다.

**라벨맵(옛 ``segmap`` 도메인)은 삭제됐다.** 여러 객체를 한 장에 겹쳐 담은 라벨맵은 카디널리티가 다를 뿐
같은 뜻이라 도메인을 가를 이유가 없었고, 정본이 **객체마다 자기 mask** 를 들게 되면서 저장 표현으로서도
사라졌다. 지금 라벨맵은 **transient 로만** 산다 — 계산 중간물(``Split_components``)과 표시용 합성
(gui ``viewer/_compose``). 둘 다 디스크로 안 내려가므로 도메인이 필요 없다.

**bbox 는 여기 없다 — [`region`](region.py) 도메인이다.** bbox 를 배열로 채우려면 캔버스 크기가
필요한데, 그 size 부재가 곧 "bbox 는 픽셀 영역이 아니라 좌표 경계"라는 경계 신호였다. region↔mask
변환(rasterize/vectorize)은 도메인을 넘는 별도 연산이라 그 size·손실을 아는 자리가 든다.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from ...format import polygon as _polygon
from ...format import rle as _rle
from . import DOMAIN_REGISTRY
from ._base import Domain


@DOMAIN_REGISTRY.Register_module("mask")
class Mask_Domain(Domain):
    """그 객체가 덮는 픽셀 영역 — rle·polygon(인라인) / png·npy(파일)."""

    FORMATS:   ClassVar[tuple[str, ...]] = ("rle", "polygon", "png", "npy")
    INFERABLE: ClassVar[bool]            = False   # png 는 image 와 구분 불가 → type 명시

    @classmethod
    def Normalize(cls, value: Any) -> Any:
        """배열이면 이진 uint8 ``(H, W)`` 로 — 다채널이면 첫 채널, 0/1 로 이진화(255 저장본도 1 로).

        **구조는 그대로 통과한다** — 폴리곤 dict·rle dict 는 배열이 아니므로 손대지 않는다. 생산자가
        이미 그 포맷으로 낸 것을 배열로 오인해 부수지 않는다(정준형이 없다는 게 이런 뜻이다).
        """
        if not isinstance(value, np.ndarray):
            return value
        _m = value[..., 0] if value.ndim == 3 else value
        return (_m > 0).astype(np.uint8)

    @classmethod
    def To(cls, value: Any, fmt: str) -> Any:
        """값을 ``fmt`` 구조로 — **저장할 때 도메인이 고른다.**

        생산자가 배열을 내도 인라인 포맷(rle·polygon)으로 저장할 수 있고, 그 반대도 된다. 어느 쪽이든
        먼저 배열로 뜻을 통일(`_as_mask`)한 뒤 목표 구조로 편성한다 — 그 변환의 계산은 `format` 이 든다.
        """
        if fmt in ("png", "npy"):
            return cls._as_mask(value)                        # 파일 포맷 = 배열 (구조로 왔으면 채운다)
        if fmt == "rle":
            return value if _is_rle(value) else _rle.From_mask(cls._as_mask(value))
        if fmt == "polygon":
            return value if _is_polygon(value) else _polygon.From_mask(cls._as_mask(value))
        return cls._as_mask(value)

    @classmethod
    def _as_mask(cls, value: Any) -> np.ndarray:
        """어떤 포맷으로 들어오든 이진 배열로 — 포맷 간 변환의 **경유지**(rle→polygon 도 여기 지난다)."""
        if _is_rle(value):
            return _rle.To_mask(value)
        if _is_polygon(value):
            return _polygon.Fill(value)
        return cls.Normalize(value)

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """위치 있는 **인라인** 2D+ ndarray = 단일 마스크 → 기본 포맷(rle)."""
        return 3 if (not storage and not params
                     and isinstance(value, np.ndarray) and value.ndim >= 2) else 0


def _is_rle(value: Any) -> bool:
    return isinstance(value, dict) and "counts" in value


def _is_polygon(value: Any) -> bool:
    return isinstance(value, dict) and "contours" in value

    @classmethod
    def Can_visualize(cls) -> bool:
        return True

    @classmethod
    def Blank(cls, *, size=None):
        """빈 마스크 — 2D uint8 영배열."""
        if size is None:
            raise ValueError("mask 빈 객체는 size(H, W)가 필요합니다")
        return np.zeros(size, np.uint8)
