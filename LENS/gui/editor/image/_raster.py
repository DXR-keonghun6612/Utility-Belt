"""region — **찍을 픽셀 영역** (이진 mask). 무엇으로 그렸는지도, 어디에 찍힐지도 모른다.

[`format/`](../format/__init__.py) 의 좌표 데이터와 나란한 세 번째 표현인데 **혼자 여기 산다** — 둘이
갈리는 지점이 이 파일의 요점이다:

- region 만은 **저장되지 않는다.** 라스터에 찍히고 버려진다 — 찍힌 *결과*가 데이터고 region 은 그 손짓이다.
- region 만은 **차원이 박혀 있다.** 래스터화가 cv2 라 2d 다 (bbox·polygon 은 numpy 로 D 를 안 박는다).

그래서 여기 함수는 전부 새 배열을 내기만 하고, 그걸 어디에 어떤 값으로 찍을지는
[`tool/_pixel.py`](tool/_pixel.py) 가 안다. 같은 이유로 여기는 `Target` 도 편집기도 모른다.

[`_overlay`](_overlay.py) 와 짝이다 — 저기는 *보여줄 것*을 그리고 여기는 *찍을 것*을 만든다. 둘 다
cv2 로 2d 배열을 다루지만 결과의 수명이 다르다(오버레이는 표시본에, region 은 데이터에 얹힌다).

색 유사 영역(magic wand)은 배경 이미지를 봐야 해서 [`tool/_fill`](tool/_fill.py) 에 따로 산다 —
나머지 셋은 기하다.
"""
from __future__ import annotations

import cv2
import numpy as np


def blank(shape: tuple[int, ...]) -> np.ndarray:
    """아무것도 안 든 region — ``shape`` 의 앞 두 축만 쓴다 ``(H, W)``."""
    return np.zeros(shape[:2], np.uint8)


def brush(shape: tuple[int, ...], a: tuple[int, int], b: tuple[int, int],
          thickness: int) -> np.ndarray:
    """두 점을 잇는 굵은 선분 — 드래그가 지나간 자리.

    Args:
        shape: 찍을 라스터의 크기 ``(H, W)``.
        a: 선분의 시작점 (원본 픽셀).
        b: 선분의 끝점 — 드래그 중이면 직전 위치에서 현재 위치까지.
        thickness: 브러시 굵기(px). 1 미만은 1 로 올린다.
    """
    _m = blank(shape)
    cv2.line(_m, a, b, 1, thickness=max(1, thickness))
    return _m


def circle(shape: tuple[int, ...], center: tuple[int, int], radius: int) -> np.ndarray:
    """속을 채운 원 — 반지름이 0 이하면 빈 region.

    Args:
        shape: 찍을 라스터의 크기 ``(H, W)``.
        center: 원의 중심 (원본 픽셀).
        radius: 반지름(px).
    """
    _m = blank(shape)
    if radius > 0:
        cv2.circle(_m, center, radius, 1, -1)
    return _m


def polygon(shape: tuple[int, ...], points) -> np.ndarray:
    """속을 채운 다각형 — **올가미가 폴리곤을 픽셀로 바꾸는 자리**.

    폴리곤 좌표가 region 이 되는 변환이 여기 있고 [`format/polygon`](../format/polygon.py) 에 없는 것이
    요점이다 — 좌표 데이터는 자기가 어떻게 쓰일지 몰라야 저장되는 쪽과 찍히는 쪽 양쪽에 같이 설 수 있다.

    Args:
        shape: 찍을 라스터의 크기 ``(H, W)``.
        points: 꼭짓점 ``(N, 2)`` — 3점 미만이면 면적이 없어 빈 region. 픽셀 격자에 반올림한다.
    """
    _m = blank(shape)
    _p = np.asarray(points, float)
    if len(_p) >= 3:
        cv2.fillPoly(_m, [_p.round().astype(np.int32)], 1)
    return _m
