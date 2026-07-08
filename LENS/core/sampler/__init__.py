"""sampler — staged 정본 → task별 학습셋(Sample_Set) 빌드 스테이지 (process 기반).

``process`` 의 Stage 엔진 위에서 ``Staged_source``(staged 순회) → ``Sample_sink``(task 트리 배치)를 잇는다.
``Sample_stage`` 가 config-facing 엔트리(``Pipeline.Sample`` 이 빌드, ``target`` 주입). store(``Sample_Set``)는
[`../data/sample`](../data/sample) 소유 — meta store↔converter 대칭으로 sample store↔sampler.
"""

from .sink import DEFAULT_RATIOS, SAMPLE_SINKS, Classification_sink, Detection_sink, Sample_sink
from .source import Staged_source
from .stage import Sample_stage
from .tasker import TASKERS_FILE, Load_taskers, Save_taskers

__all__ = [
    "Sample_stage",
    "Staged_source",
    "Sample_sink", "Classification_sink", "Detection_sink",
    "SAMPLE_SINKS", "DEFAULT_RATIOS",
    "TASKERS_FILE", "Load_taskers", "Save_taskers",
]
