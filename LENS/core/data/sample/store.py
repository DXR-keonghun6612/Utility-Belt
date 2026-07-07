"""파생 스테이지 — thin ``Sample_Set``(``Bucket_Store`` 서브클래스, 범주 = split).

정본(staged ``Dataset_Meta``)을 소비해 task별 학습셋으로 파생한다. 트리는 **split → class → sample**
3단 중첩(``Node`` 재귀) — ``CATEGORIES`` = split 이 top, 각 split 의 children = class Node, class 의
children = sample(leaf). sample leaf 는 payload + ``(stem, obj_id)`` 정본 역참조를 ``data`` 로 든다.

영속(Scatter/Gather/Load)·전이는 ``Bucket_Store`` 상속 — 사이드카 단위 = 범주(split)의 직속 children
= class(그 class 의 sample 들을 통째로 담음). 파생은 순수 재생성이라 class 사이드카를 매번 새로 흩는다.
공유 컨테이너는 [`../schema.py`](../schema.py), leaf ``Data_Ref`` 는 [`../handler`](../handler), 파생
빌드는 [`sampler.py`](sampler.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Iterator

from ..schema import Node
from ..schema import Bucket_Store

SAMPLE_DIR = "samples"   # 정본 root 아래 파생 서브트리 ({dataset_root}/samples)


@dataclass
class Sample_Set(Bucket_Store):
    """파생 학습셋 — 범주(``CATEGORIES``) = split, 중첩 split → class → sample.

    classification 의 class 폴더 구조와 1:1 (``{root}/{split}/{class}/{id}``). class 는 sample 의
    **위치**(부모 key)로 산다 — sample leaf 는 payload + ``(stem, obj_id)`` 역참조만 든다. 구조 조작·
    영속·전이는 ``Bucket_Store`` 상속. 여기 더하는 건 3단 중첩 편의(Place/Iter_samples)뿐.
    """

    CATEGORIES: ClassVar[tuple[str, ...]] = ("train", "val", "test")
    TOP_STEM:   ClassVar[str] = "sample_set"

    def Place(self, split: str, class_id: str, sample_id: str, sample: Node) -> None:
        """``split``/``class``(없으면 생성) 아래 ``sample`` 을 넣는다 (중첩 3단)."""
        _cls = self.children[split].children.setdefault(class_id, Node())
        _cls.children[sample_id] = sample

    def Iter_samples(self) -> Iterator[tuple[str, str, str, Node]]:
        """전 sample 을 ``(split, class, sample_id, Node)`` 로 순회."""
        for _split in self.CATEGORIES:
            for _cls, _cnode in self.children[_split].children.items():
                for _sid, _sample in _cnode.children.items():
                    yield _split, _cls, _sid, _sample
