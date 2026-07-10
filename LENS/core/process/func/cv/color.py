"""도메인 무관 색 primitive — 색공간을 오가며 채널을 손보는 픽셀 연산.

``func/chroma`` 와 구분할 것 — 저쪽은 **크로마 배경모델**(2채널 히스토그램·robust 통계)이라는 도메인
지식을 담고, 여기는 그런 의미가 없는 순수 채널 조작이다. 어느 도메인 유닛이 써도 누수가 아니다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ....typing import GRAY_IMAGE


def Scale_intensity(image: GRAY_IMAGE, scale: int) -> GRAY_IMAGE:
    """픽셀값에 ``scale`` 을 곱하고 ``[0, 255]`` 로 clip 한다 (uint8).

    이진화가 아니라 곱셈이라 ``scale=1`` 이면 무변경이고, ``0/1`` mask 를 ``255`` 배 하면 눈으로 볼 수
    있는 ``0/255`` 가 된다. 이미 ``0/255`` 인 mask 에 ``scale=1`` 을 주면 그대로다.
    """
    if scale == 1:
        return image
    return np.clip(image.astype(np.int32) * scale, 0, 255).astype(np.uint8)


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
