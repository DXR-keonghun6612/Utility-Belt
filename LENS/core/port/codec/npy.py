"""npy codec — numpy 배열 파일 ↔ ndarray. np.load/np.save.

차원을 안 따진다 — 2D 마스크든 3D 포인트든 배열이면 그대로 싣고 내린다(그 의미는 도메인이 든다).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from . import CODEC_REGISTRY
from ._base import File_Codec


@CODEC_REGISTRY.Register_module("npy")
class Npy_Codec(File_Codec):

    @classmethod
    def Formats(cls) -> tuple[str, ...]:
        return ("npy",)

    @classmethod
    def _Read(cls, path: Path) -> Any:
        return np.load(str(path))

    @classmethod
    def _Write(cls, data: Any, path: Path) -> None:
        np.save(str(path), data)
