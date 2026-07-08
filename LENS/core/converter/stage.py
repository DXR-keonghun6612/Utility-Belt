"""Convert stage — ``Stage(Raw_source, [], Register_sink)``.

raw 발견(``Raw_source``)을 modified 등록(``Register_sink``)으로 잇는 Stage 구성. 체인(``processes``)은
보통 비지만, raw→정본 변환 process 를 끼우면(예: 포맷 정규화) 그대로 태워진다(Run 과 같은 엔진).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..process import Stage
from ..process.sink import Base_Sink
from ..process.source import Base_Source
from .sink import Register_sink
from .source import Raw_source


@dataclass
class Convert_stage(Stage):
    """raw → 정본(modified) ingest stage. ``sources``/``globs``/``params`` 는 ``Raw_source`` 로 넘어간다."""

    sources: list[str]                 = field(default_factory=list)
    globs:   dict[str, dict[str, Any]] = field(default_factory=dict)
    params:  dict[str, dict[str, Any]] = field(default_factory=dict)

    def _make_source(self) -> Base_Source:
        return Raw_source(sources=self.sources, globs=self.globs, params=self.params)

    def _make_sink(self) -> Base_Sink:
        return Register_sink()

    def _label(self) -> str:
        return self.name or "convert"
