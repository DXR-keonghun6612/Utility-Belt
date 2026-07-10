"""Sample sink 들 — task = sink (트리 모양·집계). config ``task`` → sink 클래스는 ``SAMPLE_SINKS``.

새 task/포맷은 파일로 추가(``classification.py``·``detection.py`` 처럼)하고 ``SAMPLE_SINKS`` 에 등록한다.
"""

from ._base import DEFAULT_RATIOS, Sample_sink
from .classification import Classification_sink
from .detection import Detection_sink

# config task → sink 클래스 (Sample_stage 가 빌드에, Pipeline 이 내보내기에 소비).
SAMPLE_SINKS: dict[str, type[Sample_sink]] = {
    "classification": Classification_sink,
    "detection":      Detection_sink,
}

__all__ = [
    "Sample_sink", "Classification_sink", "Detection_sink",
    "SAMPLE_SINKS", "DEFAULT_RATIOS",
]
