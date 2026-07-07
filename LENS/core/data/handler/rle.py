"""rle 핸들러 — coco RLE mask (인코딩/디코딩을 직접 소유).

payload 는 ``Data_Ref.info["value"]`` 에 RLE dict 로 인라인. raw Path(마스크 이미지)면
읽어서 인코딩하고, ndarray 면 그대로 인코딩한다. load 는 디코딩해 uint8 마스크 반환.
coco 코덱(``_encode``/``_decode``)은 이 핸들러의 payload 인코딩이라 여기서 소유한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from pycocotools import mask as coco_mask

from . import HANDLER_REGISTRY
from ._base import Data_Ref, Handler


def _decode(rle: dict) -> np.ndarray:
    """coco RLE dict → uint8 마스크 배열."""
    _rle_b = {"counts": rle["counts"].encode("utf-8"), "size": rle["size"]}
    return coco_mask.decode(_rle_b).astype(np.uint8)  # type: ignore[arg-type]


def _encode(mask: np.ndarray) -> dict:
    """uint8 마스크 배열 → coco RLE dict."""
    _rle = coco_mask.encode(np.asfortranarray(mask.astype(np.uint8)))
    return {  # type: ignore[union-attr]
        "counts": _rle["counts"].decode("utf-8"),
        "size":   _rle["size"],
    }


@HANDLER_REGISTRY.Register_module("rle")
class Rle_Handler(Handler):

    @classmethod
    def Load(cls, root: str, stem: str | None, name: str, ref: Data_Ref,
             *, obj_id: str | None = None) -> Any:
        _v = ref.info.get("value")
        return _decode(_v) if _v is not None else None

    @classmethod
    def Save(cls, root: str, stem: str | None, name: str, ref: Data_Ref, src: Any,
             *, obj_id: str | None = None) -> Data_Ref:
        _mask = cls._Read_mask(src) if isinstance(src, (str, Path)) else src
        _rle = _encode(np.asarray(_mask).astype(np.uint8))
        return Data_Ref(
            type=ref.type,
            format=ref.format or cls.Default_format(),
            info={**ref.info, "value": _rle},
        )

    @staticmethod
    def _Read_mask(path: str | Path) -> np.ndarray:
        """raw 마스크 이미지 파일을 읽는다 (인코딩 전 소스가 Path 인 경우)."""
        _img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if _img is None:
            raise FileNotFoundError(f"마스크 로드 실패: {path}")
        return _img

    @classmethod
    def Default_format(cls) -> str:
        return "rle"

    @classmethod
    def Can_visualize(cls) -> bool:
        return True
