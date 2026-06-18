"""FrameMeta로부터 이미지를 디스크에서 로드하는 frame process."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import cv2

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process
from ...dataloader._base import Frame_Meta


NAME = "load_frame"

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}
_TEXT_EXTS  = {".txt"}


# ── Config ────────────────────────────────────────────────────────────────────

@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Load_frame_config(Base_Config):
    """로드 파라미터."""

    config_type: str = f"{NAME}_config"
    object_type: str = NAME

    keys: list[str] = field(default_factory=list, metadata={"ui": {
        "label": "로드할 key (쉼표구분)",
        "tip": "data_path 중 읽을 key 목록 (예: frame,mask). 비우면 전체 로드",
    }})


# ── Process ───────────────────────────────────────────────────────────────────

@pipeline_registry.Register_module(NAME)
@dataclass
class Load_frame_process(Base_Process):
    """Frame_Meta.data_path 의 경로들을 확장자 기반으로 로드한다.

    keys 가 지정되면 그 key 들만, 비어 있으면 data_path 전체를 로드한다.
    이미지(.png/.jpg 등) → cv2.imread(UNCHANGED), 텍스트(.txt) → str.
    지원하지 않는 확장자는 경고 후 해당 key 를 건너뛴다.
    이미지 로드 실패 시 None 을 반환한다.
    """

    name: str = NAME
    keys: list[str] = field(default_factory=list)

    # data_path 의 로드 key(frame/mask 등)는 동적 — stem 만 항상 보장.
    INPUTS:  ClassVar[tuple[str, ...]] = ("meta",)
    OUTPUTS: ClassVar[tuple[str, ...]] = ("stem",)

    def __post_init__(self) -> None:
        self._keys = set(self.keys)

    def Run(self, meta: Frame_Meta, **kwargs) -> dict:
        _frame: dict = {"stem": meta.stem}
        for _key, _path in meta.data_path.items():
            if self._keys and _key not in self._keys:
                continue
            _ext = Path(_path).suffix.lower()
            if _ext in _IMAGE_EXTS:
                _val = cv2.imread(str(_path), cv2.IMREAD_UNCHANGED)
                if _val is None:
                    return {}
            elif _ext in _TEXT_EXTS:
                _val = Path(_path).read_text(encoding="utf-8").strip()
            else:
                warnings.warn(f"load_frame: 지원하지 않는 확장자 {_ext!r} — {Path(_path).name}")
                continue
            _frame[_key] = _val
        return _frame
