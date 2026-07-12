"""sampler — staged 정본 → 파생 학습셋(``Sample_Set``) 빌드 + 내보내기.

``process`` 의 ``Stage`` 엔진 위에서 staged 범주를 순회해 파생 store 에 배치한다. Convert 와 달리 Sample 은
체인을 **실제로 쓴다**(gate 로 솎고 crop 으로 실체화) — 그래서 엔진에 남는다. 배치 자체(payload write +
범주 등록)는 ``Sample_Set.Place`` 가 소유한다(라이프사이클은 store 소유) — 여기가 정하는 건 **빌드 정책**
(무엇을 뽑나·어떻게 나누나)뿐이다.

**두 축이 갈린다** — 빌드(``unit``·crop·split 배정)와 내보내기(classification=ImageFolder /
detection=COCO). task 는 후자에만 산다([`export.py`](export.py) — 2단계에서 `core/port/` 로 이사).
"""

from .export import EXPORTERS, Coco_exporter, Exporter, ImageFolder_exporter
from .stage import DEFAULT_RATIOS, UNLABELED, Sample_stage
from .tasker import TASKERS_FILE, Load_taskers, Save_taskers

__all__ = [
    "Sample_stage", "DEFAULT_RATIOS", "UNLABELED",
    "Exporter", "ImageFolder_exporter", "Coco_exporter", "EXPORTERS",
    "TASKERS_FILE", "Load_taskers", "Save_taskers",
]
