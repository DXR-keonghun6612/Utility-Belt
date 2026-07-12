"""converter — raw → 정본(modified) ingest.

**stage 가 아니다.** Convert 는 process 체인이 비어 엔진을 쓰지 않는다 — ``scan → Save → store.Set`` 이라
계산이 아니라 **store 진입 게이트**이고, ``Restore``/``Merge``/``Export`` 의 형제다. 그래서 source/sink 를
세우지 않고 자유함수 ``Ingest`` 하나로 둔다 ([`ingest.py`](ingest.py)).

정해진 포맷 파서(coco/yolo)는 다른 ``Scan``/``Ingest`` 변주로 여기 더한다.
(2단계에서 `core/port/` 로 이사한다 — [`../TODO.md`](../TODO.md) "★ core 4분할".)
"""

from .ingest import Ingest, Scan

__all__ = ["Ingest", "Scan"]
