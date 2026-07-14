"""image 핸들러 — png/jpg 등 이미지 파일. cv2 입출력."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from . import HANDLER_REGISTRY
from ._base import File_Handler


@HANDLER_REGISTRY.Register_module("image")
class Image_Handler(File_Handler):

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """frame/object 파일 이미지 — 위치 있는 storage 요청의 ndarray 를 png 로."""
        return 3 if (storage and not params and isinstance(value, np.ndarray)) else 0

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

    @classmethod
    def Extensions(cls) -> tuple[str, ...]:
        return ("png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp")

    @classmethod
    def Can_visualize(cls) -> bool:
        return True

    @classmethod
    def Blank(cls, *, size=None):
        """빈 이미지 — 검은 BGR 3채널 (``size`` = (H, W) 필수)."""
        if size is None:
            raise ValueError("image 빈 객체는 size(H, W)가 필요합니다")
        return np.zeros((*size, 3), np.uint8)
