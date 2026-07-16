"""편집 오버레이 — **칠하기 전에 무엇이 칠해질지 보여준다** (합성된 캔버스 위에 덧그린다).

합성(`viewer/_compose`)은 *데이터가 무엇인가*를 그리고, 여기는 *지금 무엇을 하려는가*를 그린다 —
아직 데이터가 아닌 것들(그리는 중인 도형·브러시 크기·bbox 핸들). 그래서 합성 결과에 얹고 버린다.

**미리보기는 아래 픽셀의 보색으로 칠한다.** 고정색을 쓰면 하필 그 색인 배경 위에서 안 보이는데, 라벨링은
안 보이는 1초가 곧 오칠이다. 보색 + 노란 외곽선이면 어떤 배경 위에서도 경계가 선다.
"""
from __future__ import annotations

import cv2
import numpy as np

_YELLOW = (0, 255, 255)          # 미리보기 외곽선 (BGR)
_BLACK = (0, 0, 0)
_ALPHA = 0.5


def brightness(image: np.ndarray, delta: int) -> np.ndarray:
    """표시용 밝기 보정 — **보기만 바꾼다**(저장 데이터·색 채우기 기준은 원본 그대로).

    Args:
        image: 합성된 BGR 캔버스.
        delta: 더할 밝기 (-100~100). 0 이면 원본을 그대로 돌려준다.
    """
    if delta == 0:
        return image
    return cv2.convertScaleAbs(image, alpha=1.0, beta=int(delta))


def fill_complement(canvas: np.ndarray, region: np.ndarray) -> None:
    """``region`` 을 아래 픽셀의 **보색**(255-픽셀)으로 반투명 채운다 (in-place)."""
    _sel = region > 0
    if not _sel.any():
        return
    canvas[_sel] = ((1 - _ALPHA) * canvas[_sel]
                    + _ALPHA * (255 - canvas[_sel].astype(np.float32))).astype(np.uint8)


def preview_polygon(canvas: np.ndarray, points) -> None:
    """그리는 중인 다각형 — 3점 이상이면 보색 채움 + 폴리라인 + 꼭짓점 점.

    Args:
        canvas: 합성된 BGR 캔버스 (in-place).
        points: 꼭짓점 ``(N, 2)`` — 픽셀 격자에 반올림해 그린다.
    """
    _pts = np.asarray(points, float).round().astype(np.int32)
    if len(_pts) == 0:
        return
    if len(_pts) >= 3:
        _region = np.zeros(canvas.shape[:2], np.uint8)
        cv2.fillPoly(_region, [_pts], 1)
        fill_complement(canvas, _region)
    cv2.polylines(canvas, [_pts], len(_pts) >= 3, _YELLOW, 1)
    for _p in _pts:
        cv2.circle(canvas, tuple(_p), 3, _YELLOW, -1)


def preview_circle(canvas: np.ndarray, center: tuple[int, int], radius: int) -> None:
    """그리는 중인 원 — 보색 채움 + 외곽선."""
    if radius < 1:
        return
    _region = np.zeros(canvas.shape[:2], np.uint8)
    cv2.circle(_region, center, radius, 1, -1)
    fill_complement(canvas, _region)
    cv2.circle(canvas, center, radius, _YELLOW, 1)


def cursor(canvas: np.ndarray, center: tuple[int, int], radius: int) -> None:
    """커서 반경 원 — 브러시는 칠할 footprint, 채우기는 번짐을 가둘 ROI 한계."""
    cv2.circle(canvas, center, max(1, radius), _YELLOW, 1)


def handles(canvas: np.ndarray, corners, faces) -> None:
    """bbox 편집 핸들 — 코너는 **사각형**(전 축 리사이즈), 면 중심은 **원**(한 축 이동).

    모양으로 가른다 — 색만 다르면 무엇이 한 축이고 무엇이 전 축인지 알 수 없다.

    Args:
        canvas: 합성된 BGR 캔버스 (in-place).
        corners: 코너 위치 ``(N, 2)``.
        faces: 면 중심 위치 ``(M, 2)`` — 어느 축·쪽인지는 히트 판정의 몫이라 위치만 받는다.
    """
    for _x, _y in np.asarray(corners, float).round().astype(int):
        cv2.rectangle(canvas, (_x - 4, _y - 4), (_x + 4, _y + 4), _BLACK, -1)
        cv2.rectangle(canvas, (_x - 3, _y - 3), (_x + 3, _y + 3), _YELLOW, -1)
    for _x, _y in np.asarray(faces, float).round().astype(int):
        cv2.circle(canvas, (_x, _y), 4, _BLACK, -1)
        cv2.circle(canvas, (_x, _y), 3, _YELLOW, -1)
