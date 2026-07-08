"""converter — raw → 정본(modified) ingest 스테이지 (process 기반).

``process`` 의 Stage 엔진 위에서 ``Raw_source``(glob 발견) → ``Register_sink``(stem 등록)를 잇는다.
``Convert_stage`` 가 config-facing 엔트리(``Pipeline.Convert`` 가 빌드). 정해진 포맷 파서(coco/yolo)는
다른 Source 로 이 패키지에 더한다.
"""

from .sink import Register_sink
from .source import Raw_source
from .stage import Convert_stage

__all__ = ["Convert_stage", "Raw_source", "Register_sink"]
