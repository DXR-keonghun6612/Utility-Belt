"""정본 스테이지 — thin ``Dataset_Meta``(``Bucket_Store`` 서브클래스, 범주 = staging 상태).

조회·쓰기 게이트도 영속·전이도 [`../bucket_store.py`](../bucket_store.py)의 ``Bucket_Store`` 메서드가
소유한다(순수 트리 코어는 [`../data_ref.py`](../data_ref.py)). 여기 남는 건 **설정**(범주 목록·진입 범주)
+ 그 범주를 이름으로 노출하는 **named accessor**뿐 — 타입이 곧 트리 모양 보장이라 병합이 같은 타입끼리만.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Mapping

from ...constant import META_STATES, MODIFIED, SKIPPED, STAGED
from ..bucket_store import Bucket_Store
from ..data_ref import Data_Ref

ANNOTATION_FILE = "annotation.json"   # 내보내기 — staged 를 뭉친 자기완결 본


@dataclass
class Dataset_Meta(Bucket_Store):
    """정본 store — 범주 = staging 상태 (modified/staged/skipped).

    ``modified`` = 작업(flow 출력·가져오기), ``staged`` = 검수 완료(annotation 대상), ``skipped`` = 보류.
    새 항목과 **내용이 바뀐 항목**은 ``modified`` 로 진입한다(``DEFAULT_CATEGORY``) — 검수는 내용에 대한
    것이라 내용이 달라지면 다시 받아야 한다. class→id 매핑은 파생(sample) 소유고, meta 는 class **이름**만
    ``class_id`` LEAF 로 든다.

    설정 + named accessor 뿐 — 조회·쓰기·영속·전이는 ``Bucket_Store`` 메서드.
    """

    CATEGORIES:       ClassVar[tuple[str, ...]] = META_STATES
    DEFAULT_CATEGORY: ClassVar[str] = MODIFIED

    # ── named accessor — ``Bucket(상태)`` 읽기 뷰에 이름을 얹은 sugar ─────────────────
    @property
    def modified(self) -> Mapping[str, Data_Ref]:
        """작업 대상(flow 출력·가져오기) 항목 — 읽기 전용 뷰."""
        return self.Bucket(MODIFIED)

    @property
    def staged(self) -> Mapping[str, Data_Ref]:
        """검수 완료(annotation 대상) 항목 — 읽기 전용 뷰."""
        return self.Bucket(STAGED)

    @property
    def skipped(self) -> Mapping[str, Data_Ref]:
        """보류(파이프라인 제외) 항목 — 읽기 전용 뷰."""
        return self.Bucket(SKIPPED)
