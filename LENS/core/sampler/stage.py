"""Sample stage — ``Stage(Staged_source, [], Sample_sink[task])``.

staged 정본 순회(``Staged_source``)를 task별 트리 배치(``Sample_sink``)로 잇는 Stage 구성. ``task`` 가
sink(classification/detection)를 고르고, 결과는 주입된 ``target``(``Sample_Set``)에 쌓인다. source 는 정본
(meta)을, sink 는 ``target`` 을 쓴다(source-store ≠ sink-store). 체인(``processes``)은 보통 비지만, crop
실체화 process 를 끼우면 그대로 태워진다(Run 과 같은 엔진).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..data.sample import Sample_Set
from ..process import Stage
from ..process.sink import Base_Sink
from ..process.source import Base_Source
from .sink import DEFAULT_RATIOS, SAMPLE_SINKS
from .source import Staged_source


@dataclass
class Sample_stage(Stage):
    """staged 정본 → 파생(Sample_Set) 빌드 stage. ``target`` 은 Pipeline 이 주입한다."""

    task:    str              = "classification"
    ratios:  dict[str, float] = field(default_factory=lambda: dict(DEFAULT_RATIOS))
    salt:    str              = ""
    unit:    str              = "object"
    target:  Sample_Set | None = None      # 채울 store (주입; 직렬화 제외)

    __exclude_serialize__: ClassVar[set[str]] = {"config_type", "target"}

    def _make_source(self) -> Base_Source:
        # processes(crop 체인)가 있으면 payload 를 resolve 하는 실체화 모드 — 없으면 A+ 순수 역참조.
        return Staged_source(unit=self.unit, materialize=bool(self.processes))

    def _make_sink(self) -> Base_Sink:
        _cls = SAMPLE_SINKS.get(self.task)
        if _cls is None:
            raise ValueError(f"알 수 없는 sample task: {self.task!r}")
        return _cls(target=self.target, ratios=self.ratios, salt=self.salt)

    def _label(self) -> str:
        return self.name or "sample"
