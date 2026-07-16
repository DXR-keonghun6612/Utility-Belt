"""polygon 구조 — 외곽선 좌표열. **면인지 선인지 모른다.**

``{"size": [H, W], "contours": [[x0,y0,x1,y1,…], …]}`` — COCO ``segmentation`` 의 평탄 좌표열과 같은
표현이라 그대로 실어 낼 수 있다. 외곽선이 여럿이면(구멍·조각) 리스트가 여럿이다.

**여기는 `Fill` 을 제공만 하고 고르지 않는다.** 같은 폴리곤이 mask 면 채워지고 polyline 이면 그어진다 —
그 선택은 도메인의 말이다([`../port/domain`](../port/domain)). 한때 이 함수가 `codec/polygon.py` 의
``Decode_polygon`` 이었는데, "Decode"(= 정준형으로 푼다)라는 이름 자체가 "폴리곤은 언제나 픽셀이다"라는
**결정**이었다 — I/O 모듈이 의미를 정하고 있었다.

**`Fill` 은 손실이다** — 래스터화된 외곽선이라 구멍(hole)은 ``RETR_LIST`` 로 딴 조각들이 겹쳐 채워질 수
있고, 좌표는 픽셀 격자에 맞춰 근사된다. 그래서 폴리곤을 **truth 로 들면 채우지 말고 좌표를 그대로**
둬야 한다(편집기가 꼭짓점을 보려면 이것이 전제다).
"""

from __future__ import annotations

import cv2
import numpy as np


# ── 구조를 읽고 쓴다 (폴리곤을 **폴리곤으로** 다루는 쪽) ─────────────────────────
def Points(poly: dict) -> list[np.ndarray]:
    """외곽선별 꼭짓점 ``(N, 2)`` 목록 — 평탄 좌표열을 풀어 준다.

    **이게 없으면 소비처가 ``poly["contours"]`` 를 손으로 판다** — 그러면 "좌표가 평탄하게 누워 있고
    2개씩 끊어 읽는다"는 사실이 곳곳에 박혀, 구조를 이 파일이 소유한다는 말이 거짓이 된다. 편집기가
    꼭짓점을 잡는 문도 여기다.
    """
    return [np.asarray(_c, float).reshape(-1, 2) for _c in poly.get("contours", [])]


def From_points(contours, size: tuple[int, int]) -> dict:
    """꼭짓점 목록 → 폴리곤 구조 (`Points` 의 역).

    Args:
        contours: 외곽선별 ``(N, 2)`` 좌표들.
        size: ``(H, W)`` — 폴리곤은 자기가 어느 크기 안에 사는지 함께 든다(래스터화의 전제).
    """
    return {
        "size":     [int(size[0]), int(size[1])],
        "contours": [[float(_v) for _v in np.asarray(_c, float).reshape(-1)]
                     for _c in contours],
    }


def Size(poly: dict) -> tuple[int, int]:
    """이 폴리곤이 사는 캔버스 크기 ``(H, W)``."""
    return (int(poly["size"][0]), int(poly["size"][1]))


# ── 다른 구조로 (도메인이 **고르는** 것 — 여기는 제공만 한다) ─────────────────────
def Fill(poly: dict) -> np.ndarray:
    """폴리곤을 **채워** 이진 mask ``(H, W) uint8`` 로 — mask 도메인이 고르는 읽기.

    Args:
        poly: ``{"size": [H, W], "contours": [[x0,y0,…], …]}``. 점 3개 미만 외곽선은 면적이 없어 버린다.
    """
    _h, _w = (int(_v) for _v in poly["size"])
    _mask = np.zeros((_h, _w), np.uint8)
    _cnts = [np.asarray(_c, np.float64).reshape(-1, 1, 2).round().astype(np.int32)
             for _c in poly.get("contours", []) if len(_c) >= 6]
    if _cnts:
        cv2.fillPoly(_mask, _cnts, 1)
    return _mask


def From_mask(mask: np.ndarray) -> dict:
    """이진 mask 의 외곽선을 따 폴리곤 구조로 (``Fill`` 의 역 — **근사**다).

    Args:
        mask: 이진 mask ``(H, W)``. 점 3개 미만 외곽선은 버린다(면적 0).
    """
    _m = (np.asarray(mask) > 0).astype(np.uint8)
    _cnts, _ = cv2.findContours(_m, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return {
        "size":     [int(_m.shape[0]), int(_m.shape[1])],
        "contours": [_c.reshape(-1).astype(float).tolist()
                     for _c in _cnts if len(_c) >= 3],
    }
