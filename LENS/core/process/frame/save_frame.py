"""프레임 이미지를 디스크에 저장하는 frame process (명시적 저장 단계).

저장은 더 이상 Session 에 박혀 있지 않고 시퀀스의 한 step 이다. frame_batch 안에
마지막 step 으로 넣으면, 각 프레임의 targets(key→ext) 이미지를 한꺼번에 저장한다.
save_root 는 Session 이 context 에 주입한다(= workspace).

배치 방식은 nested 로 선택:
    nested=False → <save_root>/<class>/<stem>_<key><ext>   (한 폴더, 파일명 접미)
    nested=True  → <save_root>/<class>/<key>/<stem><ext>   (key 별 하위폴더)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import cv2

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process
from ...dataloader._base import UNCLASSIFIED


NAME = "save"


def _default_targets() -> list[tuple[str, str]]:
    return [("mask", ".png")]


# ── Config ────────────────────────────────────────────────────────────────────

@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Save_config(Base_Config):
    """저장 파라미터."""

    config_type: str = f"{NAME}_config"
    object_type: str = NAME

    targets: list[tuple[str, str]] = field(
        default_factory=_default_targets, metadata={"ui": {
            "label": "저장 대상 (key:ext)",
            "tip": "프레임 context 에서 저장할 (key, 확장자) 목록 (예: mask:.png, frame:.jpg)",
        }})
    nested: bool = field(default=False, metadata={"ui": {
        "label": "key 하위폴더 분리",
        "tip": "체크: <class>/<key>/<stem>, 해제: <class>/<stem>_<key>",
    }})


# ── Process ───────────────────────────────────────────────────────────────────

@pipeline_registry.Register_module(NAME)
@dataclass
class Save_process(Base_Process):
    """targets 의 각 key 이미지를 nested 규칙에 따라 저장한다."""

    name:    str = NAME
    targets: list[tuple[str, str]] = field(default_factory=_default_targets)
    nested:  bool = False

    # 저장할 데이터 key(targets)는 동적 — 구조적 입력만 선언.
    INPUTS:  ClassVar[tuple[str, ...]] = ("save_root", "stem", "class_name")
    OUTPUTS: ClassVar[tuple[str, ...]] = ("saved",)

    def Run(
        self,
        save_root:  str = "",
        stem:       str = "",
        class_name: str = UNCLASSIFIED,
        **kwargs,
    ) -> dict[str, list[str]]:
        """프레임의 targets 이미지를 저장한다.

        Args:
            save_root: 저장 루트 (Session 이 context 에 주입한 workspace).
            stem: 파일 이름(확장자 제외).
            class_name: 소속 class (하위 폴더).
            **kwargs: target key 이미지를 포함한 나머지 프레임 context.

        Returns:
            {"saved": 저장 경로 목록}. 저장한 게 없으면 빈 dict.
        """
        if not save_root:
            return {}

        _saved: list[str] = []
        for _key, _ext in self.targets:
            _img = kwargs.get(_key)
            if _img is None:
                continue
            if self.nested:
                _out = Path(save_root) / class_name / _key / f"{stem}{_ext}"
            else:
                _out = Path(save_root) / class_name / f"{stem}_{_key}{_ext}"
            _out.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(_out), _img)
            _saved.append(str(_out))

        return {"saved": _saved} if _saved else {}
