"""polygon codec — 외곽선 좌표 ↔ 이진 mask 배열 (인라인).

payload 는 ``info["value"]`` 에 ``{"size": [H, W], "contours": [[x0,y0,x1,y1,…], …]}`` 로 산다 — COCO
``segmentation`` 의 polygon 표현과 같은 평탄 좌표열이라 그대로 실어 낼 수 있다. 외곽선이 여럿이면
(구멍·조각) 리스트가 여럿이다.

**정준형은 mask 도메인의 이진 배열**이다 — 그래서 ``Load`` 는 폴리곤을 채워 mask 로 돌려주고, ``Save`` 는
mask 에서 외곽선을 따 좌표로 담는다. 즉 SAM 처럼 폴리곤을 내는 생산자도, mask 를 내는 생산자도 같은
도메인에 들어온다(표현만 다르다). rle↔polygon 변환은 이 정준형을 경유한다.

**손실 변환이다** — 래스터화된 외곽선이라 구멍(hole)은 ``RETR_LIST`` 로 딴 조각들이 겹쳐 채워질 수 있고,
좌표는 픽셀 격자에 맞춰 근사된다. 정밀 기하가 필요하면 rle 를 쓴다.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from . import CODEC_REGISTRY
from ._base import Inline_Codec
from ...schema import Data_Ref


def Decode_polygon(poly: dict) -> np.ndarray:
    """polygon dict → uint8 이진 mask (정준형). 외곽선들을 채운다."""
    _h, _w = (int(_v) for _v in poly["size"])
    _mask = np.zeros((_h, _w), np.uint8)
    _cnts = [np.asarray(_c, np.float64).reshape(-1, 1, 2).round().astype(np.int32)
             for _c in poly.get("contours", []) if len(_c) >= 6]      # 점 3개 미만은 면적이 없다
    if _cnts:
        cv2.fillPoly(_mask, _cnts, 1)
    return _mask


def Encode_polygon(mask: np.ndarray) -> dict:
    """uint8 이진 mask → polygon dict (외곽선 평탄 좌표열 ``[x0,y0,x1,y1,…]``)."""
    _m = (np.asarray(mask) > 0).astype(np.uint8)
    _cnts, _ = cv2.findContours(_m, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return {
        "size":     [int(_m.shape[0]), int(_m.shape[1])],
        "contours": [_c.reshape(-1).astype(float).tolist()
                     for _c in _cnts if len(_c) >= 3],                # 점 3개 미만은 버린다(면적 0)
    }


@CODEC_REGISTRY.Register_module("polygon")
class Polygon_Codec(Inline_Codec):

    @classmethod
    def Formats(cls) -> tuple[str, ...]:
        return ("polygon",)

    @classmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        _v = ref.info.get("value")
        return Decode_polygon(_v) if _v is not None else None

    @classmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        """mask(정준형) 또는 이미 polygon dict 인 값을 담는다 — 생산자가 폴리곤을 바로 낼 수 있다."""
        _v = src if isinstance(src, dict) else Encode_polygon(np.asarray(src))
        return Data_Ref(format=(ref.format[0], "polygon"), info={**ref.info, "value": _v})
