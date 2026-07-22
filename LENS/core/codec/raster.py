"""raster codec — 이미지 파일(png/jpg/…) ↔ ndarray. cv2 입출력.

**도메인을 모른다** — png 를 읽는 법은 그게 사진이든 마스크든 같다. 그래서 image·mask 도메인이 이 codec
하나를 공유한다(도메인별 의미 보정 — 단일채널 강제 등 — 은 도메인의 ``Normalize`` 몫).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from . import CODEC_REGISTRY
from ._base import File_Codec


@CODEC_REGISTRY.Register_module("raster")
class Raster_Codec(File_Codec):

    @classmethod
    def Formats(cls) -> tuple[str, ...]:
        return ("png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp")

    @classmethod
    def _Read(cls, path: Path) -> Any:
        _img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if _img is None:
            raise FileNotFoundError(f"이미지 로드 실패: {path}")
        return _img

    @classmethod
    def _Write(cls, data: Any, path: Path) -> None:
        if not cv2.imwrite(str(path), data):
            raise OSError(f"이미지 저장 실패: {path}")
