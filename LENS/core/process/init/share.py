"""share 채널에 공유 상수를 주입하는 top-level process.

시퀀스 맨 앞에 두어 ROI 마스크·스칼라 등 실행 내내 유지될 값을 share 에 1회 주입한다.
하위 process(frame_batch 의 inner 포함)는 share 를 통해 이 값을 투명하게 받는다.

    images: (key, path) 목록 — cv2.imread(UNCHANGED) 한 ndarray 를 share[key] 로 주입.
    values: (key, literal) 목록 — int/float/bool/str 로 파싱한 스칼라를 share[key] 로 주입.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

import cv2

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process


NAME = "share"


def _parse_literal(text: str) -> Any:
    """문자열 리터럴을 int → float → bool → str 순으로 파싱한다."""
    _t = text.strip()
    for _cast in (int, float):
        try:
            return _cast(_t)
        except ValueError:
            pass
    if _t.lower() in ("true", "false"):
        return _t.lower() == "true"
    return _t


# ── Config ────────────────────────────────────────────────────────────────────

@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Share_config(Base_Config):
    """share 주입 파라미터."""

    config_type: str = f"{NAME}_config"
    object_type: str = NAME

    images: list[tuple[str, str]] = field(default_factory=list, metadata={"ui": {
        "label": "이미지 주입 (key:path)",
        "tip": "cv2.imread 한 ndarray 를 share[key] 로 주입 (예: bg_roi:roi.png)",
    }})
    values: list[tuple[str, str]] = field(default_factory=list, metadata={"ui": {
        "label": "값 주입 (key:리터럴)",
        "tip": "int/float/bool/str 로 파싱해 share[key] 로 주입 (예: k:1.5)",
    }})


# ── Process ───────────────────────────────────────────────────────────────────

@pipeline_registry.Register_module(NAME)
@dataclass
class Share_process(Base_Process):
    """share 채널에 이미지/스칼라 상수를 주입하는 top-level process.

    어떤 context 도 소비/생산하지 않고 share_out 만 채운다. SHARE_OUT 은 config 의
    images/values key 합집합이라 동적이며, GUI 에는 정적으로 표시하지 않는다.
    """

    name:   str = NAME
    images: list[tuple[str, str]] = field(default_factory=list)
    values: list[tuple[str, str]] = field(default_factory=list)

    TOP_LEVEL: ClassVar[bool]            = True
    INPUTS:    ClassVar[tuple[str, ...]] = ()
    OUTPUTS:   ClassVar[tuple[str, ...]] = ()
    SHARE_IN:  ClassVar[tuple[str, ...]] = ()
    SHARE_OUT: ClassVar[tuple[str, ...]] = ()   # 동적(주입 key 합집합)

    def Run(self, share: dict, **context) -> tuple[dict, dict]:
        """설정된 이미지/값을 share_out 으로 반환한다.

        Args:
            share:  실행 공유 상수(미사용 — 주입만 한다).
            **context: 잔여 context(미사용).

        Returns:
            (빈 context, 주입 share). 이미지 로드 실패 key 는 건너뛴다.
        """
        _out: dict[str, Any] = {}
        for _key, _path in self.images:
            _img = cv2.imread(str(_path), cv2.IMREAD_UNCHANGED)
            if _img is None:
                continue
            _out[_key] = _img
        for _key, _val in self.values:
            _out[_key] = _parse_literal(_val)
        return {}, _out
