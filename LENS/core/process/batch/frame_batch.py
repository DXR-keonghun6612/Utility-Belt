"""frame 단위 process 들을 CATEGORIZE_FILE_LIST 에 적용하는 batch process 군."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process
from ...dataloader._base import CATEGORIZE_FILE_LIST
from ..build import Build_process


# ── 공통 베이스 ───────────────────────────────────────────────────────────────

@dataclass
class Base_frame_batch(Base_Process):
    """inner frame process 들을 프레임마다 순차 적용하는 공통 베이스.

    meta 는 context 에 담아 전달한다.
    load_frame 은 inner processes 의 첫 번째 항목으로 구성한다.
    _prev 교체로 이전 단계 이미지가 자연 해제되어 O(1 프레임) 메모리를 유지한다.
    """

    processes: list[str | dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._inners = [Build_process(_m) for _m in self.processes]

    def _Apply_frame(
        self, shared: dict[str, Any], debug: bool, **context: Any
    ) -> dict:
        for _inner in self._inners:
            _out: dict = _inner.Run(**{**context, **shared})
            if not _out:
                break
            if debug:
                print(f"  {_inner.name}→" + (",".join(_out) or "None"))

            shared.update({_k: _v for _k, _v in _out.items() if _k in shared}) 
            context = _out
        return {**context, **shared}


# ── class-aware / flat ────────────────────────────────────────────────────────

NAME = "frame_batch_process"


@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Frame_batch_config(Base_Config):
    """frame process 매핑 설정. is_flatten 으로 class-aware / flat 선택."""

    config_type: str = f"{NAME}_config"
    object_type: str = NAME

    processes:  list[str | dict[str, Any]] = field(default_factory=list)
    is_flatten: bool = field(default=False, metadata={"ui": {
        "label": "평탄화(flat)",
        "tip": "체크 시 class_name 없이 전체 프레임을 평탄화해 순회",
    }})


@pipeline_registry.Register_module(NAME)
@dataclass
class Frame_batch_process(Base_frame_batch):
    """CATEGORIZE_FILE_LIST 를 class_name 포함 per-frame context 로 inner processes 실행."""

    name: str = NAME
    is_flatten: bool = False

    # 출력은 내부 step 들이 내보내는 key 의 합집합 — 동적.
    INPUTS:  ClassVar[tuple[str, ...]] = ("frames",)
    OUTPUTS: ClassVar[tuple[str, ...]] = ()

    def Run(
        self, frames: CATEGORIZE_FILE_LIST, debug: bool, **shared: Any
    ) -> dict:
        _all:  list[dict] = []
        _keys: set[str]   = set()

        if self.is_flatten:
            for _meta in (m for metas in frames.values() for m in metas):
                _frame = self._Apply_frame(shared, debug, meta=_meta)
                _keys.update(_frame.keys())
                _all.append(_frame)
        else:
            for _class_name, _meta_list in frames.items():
                for _meta in _meta_list:
                    _frame = self._Apply_frame(
                        shared, debug, meta=_meta, class_name=_class_name)
                    _keys.update(_frame.keys())
                    _all.append(_frame)
        _out = {_k: [_f.get(_k) for _f in _all] for _k in _keys}
        return {_k: _v for _k, _v in _out.items() if any(x is not None for x in _v)}
