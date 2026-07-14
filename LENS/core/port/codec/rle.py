"""rle codec — coco RLE ↔ 이진 mask 배열 (인라인).

payload 는 ``Data_Ref.info["value"]`` 에 RLE dict 로 산다. pycocotools 인코딩이라 detectron2·mmdet 등이
그대로 먹는다 — 내보내기(COCO ``segmentation``)도 이 codec 을 재사용한다(같은 인코딩을 두 곳에서 안 짠다).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from pycocotools import mask as coco_mask

from . import CODEC_REGISTRY
from ._base import Inline_Codec
from ...schema import Data_Ref


def Decode_rle(rle: dict) -> np.ndarray:
    """coco RLE dict → uint8 마스크 배열 (정준형)."""
    _rle_b = {"counts": rle["counts"].encode("utf-8"), "size": rle["size"]}
    return coco_mask.decode(_rle_b).astype(np.uint8)  # type: ignore[arg-type]


def Encode_rle(mask: np.ndarray) -> dict:
    """uint8 마스크 배열 → coco RLE dict (``counts`` 는 JSON 직렬화 가능한 str)."""
    _rle = coco_mask.encode(np.asfortranarray(mask.astype(np.uint8)))
    return {  # type: ignore[union-attr]
        "counts": _rle["counts"].decode("utf-8"),
        "size":   _rle["size"],
    }


@CODEC_REGISTRY.Register_module("rle")
class Rle_Codec(Inline_Codec):

    @classmethod
    def Formats(cls) -> tuple[str, ...]:
        return ("rle",)

    @classmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        _v = ref.info.get("value")
        return Decode_rle(_v) if _v is not None else None

    @classmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        _mask = cls._read_mask(src) if isinstance(src, (str, Path)) else src
        return Data_Ref(format=(ref.format[0], "rle"),
                        info={**ref.info, "value": Encode_rle(np.asarray(_mask).astype(np.uint8))})

    @staticmethod
    def _read_mask(path: str | Path) -> np.ndarray:
        """raw 마스크 이미지 파일 (인코딩 전 소스가 Path 인 경우)."""
        _img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if _img is None:
            raise FileNotFoundError(f"마스크 로드 실패: {path}")
        return _img
