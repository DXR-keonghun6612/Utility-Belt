"""파생 스테이지 store — thin ``Sample_Set``(``Bucket_Store`` 서브클래스, 범주 = split).

정본(staged ``Dataset_Meta``)에서 파생된 task별 학습셋의 **데이터 구조·영속**만 소유한다(정본→파생 빌드는
``core/sampler`` 의 Stage 가 한다 — meta store↔converter 대칭으로 sample store↔sampler). 범주
(``CATEGORIES``) = split(train/val/test)만 고정하고, **split 안의 트리 모양은 고정하지 않는다** — task 마다
다르기 때문이다:

- classification: ``{split}/{class}/{sample}``  (class 가 폴더 계층 — meta 보다 한 계층 더)
- COCO detection: ``{split}/{image}/{object}``  (meta 처럼 image→object, split 별 annotations 집계)

이 depth 차이는 스키마가 흡수한다 — ``Bucket_Store`` 항목(범주 직속)은 ``type="stem"`` ``Data_Ref`` 라
임의 깊이로 중첩되고, 사이드카 영속(``Scatter``/``Load``)이 그 중첩을 재귀 직렬화로 그대로 담는다. 즉
``Sample_Set`` 은 depth 를 모르고, 트리 모양은 sampler(sink)가 짓는다. leaf ``Data_Ref`` 는
[`../handler`](../handler).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ..schema import Bucket_Store

SAMPLE_DIR = "sample"                                # 정본 root 아래 파생 서브트리 ({dataset_root}/sample/{tasker})
SPLITS: tuple[str, ...] = ("train", "val", "test")   # 파생(sample) 스테이지 범주


@dataclass
class Sample_Set(Bucket_Store):
    """파생 학습셋 store — 범주(``CATEGORIES``) = split. split 안의 트리 모양은 sampler 가 정한다.

    한 split 버킷(``buckets[split]``)의 항목(범주 직속 key)이 무엇인지는 task 마다 다르다 —
    classification 은 class(그 안에 sample 중첩), detection 은 image(그 안에 object 중첩). ``Sample_Set``
    은 그 의미를 모르고 range(split)만 고정한다. 영속·전이·병합·번들(Gather)은 ``Bucket_Store`` 상속.
    """

    CATEGORIES: ClassVar[tuple[str, ...]] = SPLITS
    TOP_STEM:   ClassVar[str]             = "sample_set"
