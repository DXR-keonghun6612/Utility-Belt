"""정본 스테이지 — thin ``Dataset_Meta``(``Bucket_Store`` 서브클래스, 범주 = staging 상태).

조회·쓰기 게이트는 [`../schema.py`](../schema.py)의 ``Bucket_Store``, 영속·전이는
[`../store_io.py`](../store_io.py) 자유함수가 소유한다. 여기 남는 건 **설정**(범주 목록·진입 범주·
top 파일명)뿐이다 — 타입이 곧 트리 모양 보장이라 병합이 같은 타입끼리만 허용된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ...constant import META_STATES, MODIFIED
from ..schema import Bucket_Store

ANNOTATION_FILE = "annotation.json"   # 내보내기 — staged 를 뭉친 자기완결 본


@dataclass
class Dataset_Meta(Bucket_Store):
    """정본 store — 범주 = staging 상태, 항목 = stem(프레임) → 컨테이너 ``Data_Ref``.

    **버킷 멤버십이 곧 상태다**(라벨 필드 없음). ``modified`` = 작업(flow 출력·가져오기),
    ``staged`` = 검수 완료(annotation 대상), ``skipped`` = 보류. 상태 전이 = 버킷 이동(``store_io.Move``).
    새 stem 과 **내용이 바뀐 stem** 은 ``modified`` 로 들어온다(``DEFAULT_CATEGORY``) — 검수는 내용에
    대한 것이라 내용이 달라지면 다시 받아야 한다.

    트리 모양은 frame → object 로 고정이고, class→id 매핑(id_map)은 meta 가 아니라 파생(sample) 소유다
    (meta 는 class **이름**만 ``frame.info["class_id"]`` 로 든다).

    여기 있는 건 **설정뿐** — 조회·쓰기 게이트는 ``Bucket_Store``, 영속·전이는 ``store_io``.
    """

    CATEGORIES:       ClassVar[tuple[str, ...]] = META_STATES
    DEFAULT_CATEGORY: ClassVar[str] = MODIFIED
    TOP_STEM:         ClassVar[str] = "dataset_meta"
