"""store — 무엇이 어느 범주로 있나 + 라이프사이클.

``Bucket_Store`` 와 구체 store — 정본 ``Dataset_Meta`` · 파생 ``Sample_Set`` · 내보내기에 먹일 일회용
``Split_Set``(범주가 인스턴스 값이고 디스크에 안 앉는다 — [`split.py`](split.py)).
범주·item 주소를 소유하고,
전이·삭제·병합·영속·내보내기 같은 **라이프사이클을 자기 메서드로** 든다(호출 측이 ``meta.Move(…)`` 를
직접 부른다). 트리 기계는 [`../schema.py`](../schema.py), payload 실체화는 [`../port`](../port) 에 위임한다.

의존은 한 방향 — ``schema ← port ← store``. **port 는 store 를 모른다.**
"""

from .bucket_store import MERGE, MERGE_MODES, OVERWRITE, SKIP, Bucket_Store
from .meta import Dataset_Meta
from .sample import SAMPLE_DIR, SPLITS, Sample_Set
from .split import Split_Set

__all__ = [
    "Bucket_Store", "SKIP", "OVERWRITE", "MERGE", "MERGE_MODES",
    "Dataset_Meta",
    "Sample_Set", "SAMPLE_DIR", "SPLITS",
    "Split_Set",
]
