"""색공간 spec — 2채널 크로마 배경모델의 단일 진실원.

배경/객체 분리는 본질적으로 **2채널 크로마 거리** 문제다 (명도 채널은 조명에 취약해 버린다).
색공간이 달라도 누산·통계·거리·진단 로직은 동일하고, 달라지는 건 아래 5개 값뿐이다 —
이걸 ``ChromaSpace`` 하나로 모아 convert/accumulate/stats/mask/analysis가 공유한다.

  - ``cvt_code`` : ``cv2.cvtColor`` 변환 코드 (BGR→대상 색공간)
  - ``channels`` : 쓸 두 채널 인덱스 (명도 채널 제외)
  - ``bins``     : 채널별 히스토그램 bin 수 (= 값의 상한, OpenCV 8-bit 기준)
  - ``circular`` : 채널별 순환 여부 (hue 처럼 0/끝이 이어지면 True → wrap 보정)
  - ``labels``   : 리포트·시각화용 채널 이름
  - ``inv_code`` : 대상 색공간→RGB 역변환 코드 (시각화용; 버린 명도는 ``lum_fill`` 로 고정)
  - ``lum_fill`` : 역변환 시 버린 명도 채널에 대입할 값 (크로마만 보존한 대표색 렌더용)

내장 space:
  - ``hsv`` — H,S (V 제외). Hue 순환(180 bin). 저채도에서 Hue 불안정 주의.
  - ``lab`` — a*,b* (L* 제외). 둘 다 비순환(256 bin), 무채색에서도 안정, 거리=ΔE.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ChromaSpace:
    """한 색공간에서 2채널 크로마 배경모델을 정의하는 불변 spec."""

    name:     str
    cvt_code: int
    channels: tuple[int, int]
    bins:     tuple[int, int]
    circular: tuple[bool, bool]
    labels:   tuple[str, str]
    inv_code: int                # 대상 색공간 → RGB 역변환 (시각화용)
    lum_fill: int = 128          # 버린 명도 채널 대입값 (대표색은 크로마만, 명도 무관 → 중간값)

    def chroma_to_rgb(self, c0, c1, lum: int | None = None) -> np.ndarray:
        """두 크로마 채널값 → 실제 RGB 색 (버린 명도는 ``lum`` 으로 고정).

        ``c0``/``c1`` 은 같은 shape 의 배열 또는 스칼라 — 픽셀별 맵 ``(H,W)`` 이면 ``(H,W,3)``,
        스칼라(전역 평균)면 ``(3,)`` uint8 RGB 를 돌려준다. 명도는 대표색과 무관하므로 기본
        중간값(``lum_fill``)으로 채운다.
        """
        _lum = self.lum_fill if lum is None else lum
        _c0 = np.asarray(c0)
        _is_map = _c0.ndim >= 2
        _c0 = np.atleast_2d(_c0).astype(np.uint8)
        _c1 = np.atleast_2d(np.asarray(c1)).astype(np.uint8)

        _img = np.empty((*_c0.shape, 3), np.uint8)
        _lum_idx = ({0, 1, 2} - set(self.channels)).pop()
        _img[..., self.channels[0]] = _c0
        _img[..., self.channels[1]] = _c1
        _img[..., _lum_idx] = _lum
        _rgb = cv2.cvtColor(_img, self.inv_code)
        return _rgb if _is_map else _rgb[0, 0]


CHROMA_SPACES: dict[str, ChromaSpace] = {
    "hsv": ChromaSpace(
        name="hsv",
        cvt_code=cv2.COLOR_BGR2HSV,
        channels=(0, 1),
        bins=(180, 256),
        circular=(True, False),
        labels=("H", "S"),
        inv_code=cv2.COLOR_HSV2RGB,
    ),
    "lab": ChromaSpace(
        name="lab",
        cvt_code=cv2.COLOR_BGR2Lab,
        channels=(1, 2),
        bins=(256, 256),
        circular=(False, False),
        labels=("a*", "b*"),
        inv_code=cv2.COLOR_Lab2RGB,
    ),
}

DEFAULT_SPACE = "hsv"


def Get_space(space: str | ChromaSpace) -> ChromaSpace:
    """이름(str) 또는 ChromaSpace 를 ChromaSpace 로 정규화한다."""
    if isinstance(space, ChromaSpace):
        return space
    try:
        return CHROMA_SPACES[space]
    except KeyError:
        raise ValueError(
            f"알 수 없는 색공간 '{space}'. 가능: {sorted(CHROMA_SPACES)}") from None
