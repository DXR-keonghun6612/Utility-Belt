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
    def _Read(cls, path: Path) -> Any:
        return np.load(str(path))

    @classmethod
    def _Write(cls, data: Any, path: Path) -> None:
        np.save(str(path), data)

    @classmethod
    def Extensions(cls) -> tuple[str, ...]:
        return ("npy",)
