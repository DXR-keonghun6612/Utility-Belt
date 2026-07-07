"""정본 스테이지 — thin ``Dataset_Meta``(``Bucket_Store`` 서브클래스, 범주 = staging 상태).

영속(Scatter/Gather/Load)·전이(Move/Delete/Merge)는 전부 ``Bucket_Store`` 상속이라, 여기는
``CATEGORIES`` + top 파일명 + annotation 내보내기 편의만 둔다. 공유 컨테이너·영속·전이 구현은
[`../schema.py`](../schema.py), leaf 서술자 ``Data_Ref`` 는 [`../handler`](../handler).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ...constant import META_STATES
from ..handler import Data_Ref
from ..schema import Bucket_Store

ANNOTATION_FILE = "annotation.json"   # 내보내기 — staged 를 뭉친 자기완결 본


@dataclass
class Dataset_Meta(Bucket_Store):
    """정본 — 범주(``CATEGORIES``) = ``META_STATES``(modified/staged), 항목 = stem → 컨테이너 ``Data_Ref``.

    ``modified`` = flow 출력·가져오기, ``staged`` = 검수 완료(annotation 대상). 한 stem 은 한 범주에만
    (멤버십이 곧 상태). class→id 매핑(id_map)은 meta 소유가 아니라 파생(sample)이 받아 쓴다 — meta 는
    class **이름**만 ``frame.info["class_id"]`` 로 든다. 범주 조회·영속·전이는 ``Bucket_Store`` 상속.
    여기 더하는 건 staging 용어 편의(``STATES``/``State_of``/``modified``/``staged``/``Get``/``Has``)뿐 —
    범주(category) = 상태(state) 라 ``Bucket_Store`` 의 범주 API 를 상태 이름으로 감싼다.
    """

    CATEGORIES: ClassVar[tuple[str, ...]] = META_STATES
    STATES:     ClassVar[tuple[str, ...]] = META_STATES   # CATEGORIES 의 staging 별칭 (GUI 용어)
    TOP_STEM:   ClassVar[str] = "dataset_meta"

    # ── staging 편의 (범주 = 상태; Bucket_Store 범주 API 의 상태 이름 래퍼) ──────
    @property
    def modified(self) -> dict[str, Data_Ref]:
        """``modified`` 상태 버킷 (flow 출력·가져오기). live 참조."""
        return self.Bucket("modified")

    @property
    def staged(self) -> dict[str, Data_Ref]:
        """``staged`` 상태 버킷 (검수 완료). live 참조."""
        return self.Bucket("staged")

    def State_of(self, stem: str) -> str | None:
        """stem 이 사는 상태 (없으면 None) — ``Category_of`` 별칭."""
        return self.Category_of(stem)

    def State_root(self, state: str) -> str:
        """그 상태의 파일 루트 ``{root}/{state}`` — ``Category_root`` 별칭."""
        return self.Category_root(state)

    def Get(self, stem: str) -> Data_Ref | None:
        """stem 항목을 상태 무관하게 찾는다 — ``Find`` 별칭."""
        return self.Find(stem)

    def Has(self, stem: str) -> bool:
        """stem 이 어느 상태에든 있는지."""
        return self.Category_of(stem) is not None
