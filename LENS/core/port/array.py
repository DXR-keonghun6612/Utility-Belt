"""array 핸들러 — numpy npy 배열 파일. np.load/np.save 입출력."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from . import HANDLER_REGISTRY
from ._base import File_Handler


@HANDLER_REGISTRY.Register_module("array")
class Array_Handler(File_Handler):

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """dataset-wide(params) 배열 — 통계 등 ndarray 를 npy 파일로(위치 없는 출력의 배열)."""
        return 3 if (params and isinstance(value, np.ndarray) and value.ndim) else 0

    @classmethod
    def _Read(cls, path: Path) -> Any:
        return np.load(str(path))

    @classmethod
    def _Write(cls, data: Any, path: Path) -> None:
        np.save(str(path), data)

    @classmethod
    def Extensions(cls) -> tuple[str, ...]:
        return ("npy",)
