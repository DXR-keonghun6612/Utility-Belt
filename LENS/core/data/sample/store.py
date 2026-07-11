"""파생 스테이지 store — thin ``Sample_Set``(``Bucket_Store``, 범주 = split train/val/test).

정본(staged ``Dataset_Meta``)에서 파생된 학습셋의 구조·영속만 소유한다 — 정본→파생 빌드는
[`../../sampler`](../../sampler)가 짓는다(meta store↔converter 대칭). split 은 build 때 frame stem 해시로
배정되는 **데이터셋 정체성**이다(같은 이미지의 객체는 한 split → leakage 방지). class_id 와 split 은
독립이라 class 재배정이 split 을 안 건드린다. 트리 모양(task별)은 sampler 가 짓고 여기는 모른다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Mapping

from ...constant import SPLITS, TEST, TRAIN, VAL
from ..bucket_store import Bucket_Store
from ..data_ref import Data_Ref

SAMPLE_DIR = "sample"                                # 정본 root 아래 파생 서브트리 ({dataset_root}/sample/{tasker})


@dataclass
class Sample_Set(Bucket_Store):
    """파생 학습셋 store — 범주 = split. **추상** (직접 인스턴스화 금지).

    트리 모양(task별)이 곧 타입이라 ``Merge`` 는 같은 타입끼리만 — 모양이 다른 store 를 섞으면 무의미하다.
    구체 타입: ``Classification_Set`` / ``Detection_Set``.
    """

    CATEGORIES:       ClassVar[tuple[str, ...]] = SPLITS
    DEFAULT_CATEGORY: ClassVar[str]             = TRAIN   # placeholder — split 배정은 sampler(frame 해시) 몫

    # ── named accessor — ``Bucket(split)`` 읽기 뷰에 이름을 얹은 sugar ──────────────
    @property
    def train(self) -> Mapping[str, Data_Ref]:
        """train split 항목 — 읽기 전용 뷰."""
        return self.Bucket(TRAIN)

    @property
    def val(self) -> Mapping[str, Data_Ref]:
        """val split 항목 — 읽기 전용 뷰."""
        return self.Bucket(VAL)

    @property
    def test(self) -> Mapping[str, Data_Ref]:
        """test split 항목 — 읽기 전용 뷰."""
        return self.Bucket(TEST)


@dataclass
class Classification_Set(Sample_Set):
    """분류 학습셋 — 트리 = ``{class}/{sample}`` (class 가 한 계층, meta 보다 depth 가 하나 더 깊다)."""


@dataclass
class Detection_Set(Sample_Set):
    """검출 학습셋 — 트리 = ``{image}/{object}`` (meta 와 같은 모양)."""
