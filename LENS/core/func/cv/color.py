"""도메인 무관 색 primitive — 색공간을 오가며 채널을 손보는 픽셀 연산.

``func/chroma`` 와 구분할 것 — 저쪽은 **크로마 배경모델**(2채널 히스토그램·robust 통계)이라는 도메인
지식을 담고, 여기는 그런 의미가 없는 순수 채널 조작이다. 어느 도메인 유닛이 써도 누수가 아니다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ...typing import IMAGE, GRAY_IMAGE


def Scale_intensity(image: GRAY_IMAGE, scale: int) -> GRAY_IMAGE:
    """픽셀값에 ``scale`` 을 곱하고 ``[0, 255]`` 로 clip 한다 (uint8).

    이진화가 아니라 곱셈이라 ``scale=1`` 이면 무변경이고, ``0/1`` mask 를 ``255`` 배 하면 눈으로 볼 수
    있는 ``0/255`` 가 된다. 이미 ``0/255`` 인 mask 에 ``scale=1`` 을 주면 그대로다.
    """
    if scale == 1:
        return image
    return np.clip(image.astype(np.int32) * scale, 0, 255).astype(np.uint8)


def _per_channel(image: IMAGE, fn) -> IMAGE:
    """``fn`` (2D uint8 → 2D uint8) 을 채널마다 독립 적용한다 — 채널 수는 shape 로 **런타임 구분**.

    히스토그램 정규화 primitive 들이 공유하는 채널 순회. 채널을 타입으로 쪼개지 않고 여기서 배열
    shape 만 본다:

    - **gray ``(H,W)``** — 채널이 없으니 통째 1회.
    - **3ch ``(H,W,3)``** — 각 채널 독립.
    - **4ch ``(H,W,4)``** — 색 채널 3개만 손보고 **alpha(마지막)는 그대로 보존**한다 (투명도를 늘리면
      안 되므로). 그래서 소비처가 채널 수를 방어하지 않아도 된다.
    """
    if image.ndim == 2:
        return fn(image)
    _n = image.shape[-1]
    _color = 3 if _n == 4 else _n                       # 4ch 면 alpha 제외
    _chans = [fn(image[..., _c]) for _c in range(_color)]
    if _n == 4:
        _chans.append(image[..., 3])                    # alpha 보존
    return np.stack(_chans, axis=-1)


def Stretch_contrast(image: IMAGE, low: float = 0.0, high: float = 100.0) -> IMAGE:
    """각 채널을 ``[low, high]`` 백분위 구간 → ``[0, 255]`` 로 선형 스트레칭한다 (채널 독립).

    ``low=0``·``high=100`` 이면 순수 **min–max 정규화**, 안쪽으로 좁히면(예 ``1``·``99``) 이상치에
    강건한 **percentile 스트레칭**이다. 채널마다 독립이라 색 균형이 이동한다(화이트밸런스 보정 효과).
    구간이 평평한 채널(``hi <= lo``)은 그대로 둔다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)`` uint8.
        low: 하단 백분위 ``[0, 100)``.
        high: 상단 백분위 ``(low, 100]``.

    Returns:
        채널별로 대비가 늘어난 같은 shape 의 uint8.
    """
    def _f(ch: np.ndarray) -> np.ndarray:
        _lo, _hi = np.percentile(ch, (low, high))
        if _hi <= _lo:                                  # 상수 채널 — 스트레칭 불가
            return ch
        _scaled = (ch.astype(np.float32) - _lo) * (255.0 / (_hi - _lo))
        return np.clip(_scaled, 0, 255).astype(np.uint8)
    return _per_channel(image, _f)


def Equalize_histogram(image: IMAGE) -> IMAGE:
    """각 채널에 히스토그램 평활화(``cv2.equalizeHist``)를 적용한다 (채널 독립).

    CDF 를 균등하게 재분포해 대비를 최대화한다 — 비선형이라 색·질감이 크게 변할 수 있다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)`` uint8.

    Returns:
        채널별로 평활화된 같은 shape 의 uint8.
    """
    return _per_channel(image, cv2.equalizeHist)


def Clahe(image: IMAGE, clip_limit: float = 2.0, tile: int = 8) -> IMAGE:
    """각 채널에 CLAHE(대비제한 적응형 평활화)를 적용한다 (채널 독립).

    타일 단위로 국소 대비를 살리되 ``clip_limit`` 으로 노이즈 증폭을 억제한다 — 조명이 고르지
    않은 장면에 강하다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)`` uint8.
        clip_limit: 대비 제한(클수록 강한 평활화).
        tile: 타일 격자 한 변의 개수(``tile x tile``).

    Returns:
        채널별로 적응 평활화된 같은 shape 의 uint8.
    """
    _clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    return _per_channel(image, _clahe.apply)


def Flatten_brightness(image: np.ndarray, value: int = 255) -> np.ndarray:
    """BGR 이미지의 명도(HSV ``V``)를 상수로 덮어 밝기 변화를 지운다.

    색상(``H``)·채도(``S``)는 보존되므로 그림자·하이라이트가 만드는 **밝기 경계는 사라지고 색 경계만**
    남는다. 조명이 고르지 않은 장면에서 edge 검출 전에 태우는 정규화.

    Args:
        image: BGR ``(H,W,3)``.
        value: 덮어쓸 명도 상수 ``[1, 255]``.

    Returns:
        명도가 평탄해진 BGR ``(H,W,3)``.
    """
    _hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    _hsv[..., 2] = value
    return cv2.cvtColor(_hsv, cv2.COLOR_HSV2BGR)
