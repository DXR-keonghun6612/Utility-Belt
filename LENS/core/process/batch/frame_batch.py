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
        self, share: dict[str, Any], debug: bool, **context: Any
    ) -> dict:
        """inner frame process 체인을 한 프레임에 순차 적용한다.

        각 inner 에 `{**context, **share}` 를 전달하고, 직전 출력이 다음 입력이 된다
        (`context = _out`). share 는 읽기 전용으로 전 inner 에 동일 전달되며 집계되지
        않는다 — 공유 상수가 프레임별 리스트로 변형되는 것을 막는다.

        Args:
            share: 실행 공유 상수(읽기 전용).
            debug: step 별 출력 key 로깅 여부.
            **context: 프레임별 시작 context(meta, class_name 등).

        Returns:
            마지막 inner 의 출력(프레임별 산출물). 빈 출력이 나오면 그 직전까지의 결과.
        """
        for _inner in self._inners:
            _out: dict = _inner.Run(**{**context, **share})
            if not _out:
                break
            if debug:
                print(f"  {_inner.name}→" + (",".join(_out) or "None"))
            context = _out
        return context


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

    # context 출력은 내부 step 들이 내보내는 key 의 합집합 — 동적. share 채널은 통과만.
    TOP_LEVEL: ClassVar[bool]            = True
    INPUTS:    ClassVar[tuple[str, ...]] = ("frames",)
    OUTPUTS:   ClassVar[tuple[str, ...]] = ()
    SHARE_IN:  ClassVar[tuple[str, ...]] = ()
    SHARE_OUT: ClassVar[tuple[str, ...]] = ()

    def Run(
        self, share: dict[str, Any], frames: CATEGORIZE_FILE_LIST, **context: Any
    ) -> tuple[dict, dict]:
        """프레임마다 inner 체인을 실행하고 산출물을 key 별 리스트로 집계한다.

        Args:
            share:  실행 공유 상수(읽기 전용). inner 에 그대로 전달된다.
            frames: dataloader 가 만든 CATEGORIZE_FILE_LIST.
            **context: 잔여 context(미사용).

        Returns:
            (context_out, share_out). context_out 은 프레임별 산출물의 key→list 집계.
            frame_batch 자체는 share 를 생산하지 않으므로 share_out 은 빈 dict.
        """
        _debug = bool(share.get("debug", False))
        _all:  list[dict] = []
        _keys: set[str]   = set()

        if self.is_flatten:
            for _meta in (m for metas in frames.values() for m in metas):
                _frame = self._Apply_frame(share, _debug, meta=_meta)
                _keys.update(_frame.keys())
                _all.append(_frame)
        else:
            for _class_name, _meta_list in frames.items():
                for _meta in _meta_list:
                    _frame = self._Apply_frame(
                        share, _debug, meta=_meta, class_name=_class_name)
                    _keys.update(_frame.keys())
                    _all.append(_frame)

        # key 별로 프레임 값을 모으되, 한 번도 산출되지 않은(전부 None) key 는 버린다.
        _out: dict[str, list] = {}
        for _k in _keys:
            _vals = [_f.get(_k) for _f in _all]
            if any(_v is not None for _v in _vals):
                _out[_k] = _vals
        return _out, {}
