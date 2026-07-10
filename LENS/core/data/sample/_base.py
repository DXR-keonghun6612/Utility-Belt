"""파생 스테이지 store — thin ``Sample_Set``(``Bucket_Store`` 서브클래스, 범주 = 단일 작업 버킷).

정본(staged ``Dataset_Meta``)에서 파생된 task별 학습셋의 **데이터 구조**만 소유한다(영속·전이는
``store_io`` 자유함수; 정본→파생 빌드는 ``core/sampler`` 의 Stage — meta store↔converter 대칭으로 sample
store↔sampler). 범주(``CATEGORIES``)는 split 없는 **단일 작업 버킷**(``WORKING``) 하나만 고정하고, 그 안의
트리 모양은 고정하지 않는다 — task 마다 다르기 때문이다:

- classification: ``{class}/{sample}``  (class 가 폴더 계층 — meta 보다 한 계층 더)
- COCO detection: ``{image}/{object}``  (meta 처럼 image→object)

train/val/test 는 store 범주가 아니라 **내보내기 산출물**이다 — 작업이 끝난 store 를 frame stem 해시로
갈라 ``{split}/…`` 로 실체화한다(``core/sampler`` 의 ``Sample_sink.Export``). 이 depth 차이는 스키마가
흡수한다 — ``Bucket_Store`` 항목(범주 직속)은 ``type="stem"`` ``Data_Ref`` 라 임의 깊이로 중첩되고,
사이드카 영속(``store_io.Save``/``Restore``)이 그 중첩을 재귀 직렬화로 담는다. 즉 ``Sample_Set`` 은
depth 도 split 도 모르고, 트리 모양은 sampler(sink)가 짓는다. leaf ``Data_Ref`` 는 [`../handler`](../handler).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ...constant import SPLITS, WORKING
from ..schema import Bucket_Store

SAMPLE_DIR = "sample"                                # 정본 root 아래 파생 서브트리 ({dataset_root}/sample/{tasker})


@dataclass
class Sample_Set(Bucket_Store):
    """파생 학습셋 store — 범주 = 단일 작업 버킷(``WORKING``). split 은 담지 않는다. **추상.**

    분석·재배정은 split 을 몰라도 되므로(class 이동뿐) 작업 store 는 **split 없는 단일 버킷**만 둔다.
    train/val/test 는 파생(frame stem 해시)이라 **내보내기 때만** 갈라 ``{split}/…`` 로 실체화한다
    (``core/sampler`` 의 ``Sample_sink.Export``).

    **버킷 안의 트리 모양은 task 가 정하고, 그 task 는 서브클래스가 든다** — 모양이 다른 두 store 를
    병합하면 무의미하므로, ``store_io.Merge`` 가 같은 타입만 허용하도록 타입에 모양을 새긴다. 직접
    인스턴스화하지 않는다(``Classification_Set`` / ``Detection_Set``).
    """

    CATEGORIES:       ClassVar[tuple[str, ...]] = (WORKING,)
    DEFAULT_CATEGORY: ClassVar[str]             = WORKING
    TOP_STEM:         ClassVar[str]             = "sample_set"


@dataclass
class Classification_Set(Sample_Set):
    """분류 학습셋 — 트리 = ``{class}/{sample}`` (class 가 한 계층, meta 보다 depth 가 하나 더 깊다)."""


@dataclass
class Detection_Set(Sample_Set):
    """검출 학습셋 — 트리 = ``{image}/{object}`` (meta 와 같은 모양)."""
