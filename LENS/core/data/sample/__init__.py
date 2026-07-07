"""파생(sample) 스테이지 — staged 정본 → task별 학습셋.

``_base`` 가 store(``Sample_Set``) + 빌더 베이스(``Base_Sampler``)를, task 서브패키지가 구체 sampler 를
든다: ``classification``(class 폴더) · ``detection``(COCO). ``SAMPLERS`` 는 config ``object_type`` →
sampler 클래스 팩토리 맵(``_base.py`` 의 converter/process 레지스트리와 같은 결).
"""

from ._base import SAMPLE_DIR, SPLITS, Base_Sampler, Sample_Set
from .classification import Classification_Sampler
from .detection import Detection_Sampler

# config object_type → sampler 클래스 (Pipeline._build_sampler 가 소비).
SAMPLERS: dict[str, type[Base_Sampler]] = {
    "classification": Classification_Sampler,
    "detection":      Detection_Sampler,
}

__all__ = [
    "Sample_Set",
    "Base_Sampler",
    "Classification_Sampler",
    "Detection_Sampler",
    "SAMPLERS",
    "SAMPLE_DIR",
    "SPLITS",
]
