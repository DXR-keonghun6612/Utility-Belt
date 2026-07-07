"""파생 스테이지 기본 구조 — ``Sample_Set``(store) + ``Base_Sampler``(빌더 베이스).

정본(staged ``Dataset_Meta``)을 소비해 task별 학습셋으로 파생한다. 범주(``CATEGORIES``) = split
(train/val/test)만 고정하고, **split 안의 트리 모양은 고정하지 않는다** — task 마다 다르기 때문이다:

- classification: ``{split}/{class}/{sample}``  (class 가 폴더 계층 — meta 보다 한 계층 더)
- COCO detection: ``{split}/{image}/{object}``  (meta 처럼 image→object, split 별 annotations 집계)

이 depth 차이는 스키마가 흡수한다 — ``Bucket_Store`` 항목(범주 직속)은 ``type="stem"`` ``Data_Ref`` 라
임의 깊이로 중첩되고, 사이드카 영속(``Scatter``/``Load``)이 그 중첩을 재귀 직렬화로 그대로 담는다. 즉
``Sample_Set`` 은 depth 를 모르고, 트리 모양은 task 별 ``Base_Sampler`` 서브클래스가 짓는다:
[`classification/`](classification)(class 폴더) · [`detection/`](detection)(COCO). ``converter`` 가 raw→meta
를 정하듯, ``Base_Sampler`` 는 staged meta→sample 을 정한다 — 순회·split 배정 뼈대는 베이스가, 트리
모양(``Place``)·집계 export(``Finalize``)만 서브클래스가 변주한다.

공유 컨테이너·영속·전이는 ``Bucket_Store`` 상속, leaf ``Data_Ref`` 는 [`../handler`](../handler).
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Iterator

from ...constant import STAGED
from ..handler import Data_Ref
from ..meta import Dataset_Meta
from ..schema import Attr, Bucket_Store, Set_attr

SAMPLE_DIR = "samples"                                # 정본 root 아래 파생 서브트리 ({dataset_root}/samples)
SPLITS: tuple[str, ...] = ("train", "val", "test")   # 파생(sample) 스테이지 범주
DEFAULT_RATIOS: dict[str, float] = {"train": 0.8, "val": 0.1, "test": 0.1}


@dataclass
class Sample_Set(Bucket_Store):
    """파생 학습셋 — 범주(``CATEGORIES``) = split. split 안의 트리 모양은 task(sampler) 가 정한다.

    한 split 버킷(``categories[split]``)의 항목(범주 직속 key)이 무엇인지는 task 마다 다르다 —
    classification 은 class(그 안에 sample 중첩), detection 은 image(그 안에 object 중첩). ``Sample_Set``
    은 그 의미를 모르고 range(split)만 고정한다. 영속·전이·병합·번들(Gather)은 ``Bucket_Store`` 상속.
    """

    CATEGORIES: ClassVar[tuple[str, ...]] = SPLITS
    TOP_STEM:   ClassVar[str]             = "sample_set"


@dataclass
class Base_Sampler(ABC):
    """staged ``Dataset_Meta`` → ``Sample_Set`` 빌더 (task 별 서브클래스).

    ``Build`` 가 staged 순회·split 배정을 소유하고, ``Place``(트리 배치)·``Finalize``(집계 export)만
    서브클래스가 구현한다. ``ratios`` 는 split 비율(정규화됨), ``salt`` 는 해시 배정 소금(재현성 유지한
    채 다른 배정을 원할 때). 순회 단위는 ``unit`` — "object"(단위마다 sample) / "frame"(프레임마다 sample).

    sample 은 A+ (순수 재생성) — leaf 는 payload 실체화가 아니라 정본 ``(stem, obj_id)`` **역참조**만 든다
    (원본 진실은 정본에만; crop 실체화는 process 재사용으로 다음 단계). split 배정은 **frame stem 해시**로
    결정적(재실행 안정) + **frame 단위**(같은 image 의 object 가 흩어지는 leakage 방지).
    """

    ratios: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_RATIOS))
    salt:   str              = ""
    unit:   str              = "object"      # object | frame

    # ── 뼈대 (베이스 소유) ─────────────────────────────────────────────────────
    def Build(self, meta: Dataset_Meta) -> Sample_Set:
        """staged 정본을 순회해 ``Sample_Set`` 을 새로 짓는다 (A+ 재생성).

        각 단위를 frame stem 해시로 split 에 결정적 배정하고(같은 image 는 한 split — leakage 방지),
        ``Place`` 로 트리에 꽂은 뒤 ``Finalize`` 로 집계 export 를 남긴다.
        """
        _sset = Sample_Set(root=str(Path(meta.root) / SAMPLE_DIR))
        for _stem, _obj_id, _ref in self._iter_units(meta):
            self.Place(_sset, self._assign(_stem), _stem, _obj_id, _ref)
        self.Finalize(_sset, meta)
        return _sset

    def _iter_units(
        self, meta: Dataset_Meta
    ) -> Iterator[tuple[str, str | None, Data_Ref]]:
        """staged 프레임을 ``unit`` 단위로 ``(stem, obj_id, ref)`` 로 순회.

        object 단위 = 프레임의 객체(중첩 stem)마다(obj_id = key), frame 단위 = 프레임 컨테이너 자체
        (obj_id=None). 객체 0개인 프레임은 object 단위에선 건너뛴다.
        """
        for _stem, _frame in meta.Iter_category(STAGED):
            if self.unit == "object":
                for _oid, _obj in _frame.info.items():
                    if _obj.Is_stem():
                        yield _stem, _oid, _obj
            else:
                yield _stem, None, _frame

    def _assign(self, stem: str) -> str:
        """frame stem → split (해시 기반 결정적 배정; ``ratios`` 누적 구간에 떨군다)."""
        _h = hashlib.md5(f"{self.salt}{stem}".encode()).hexdigest()
        _f = int(_h[:16], 16) / float(1 << 64)              # [0, 1)
        _norm = self._norm_ratios()
        _acc = 0.0
        for _split in SPLITS:
            _acc += _norm.get(_split, 0.0)
            if _f < _acc:
                return _split
        return SPLITS[-1]

    def _norm_ratios(self) -> dict[str, float]:
        """``ratios`` 를 합=1 로 정규화 (합이 0이면 균등)."""
        _total = sum(self.ratios.get(_s, 0.0) for _s in SPLITS)
        if _total <= 0:
            return {_s: 1.0 / len(SPLITS) for _s in SPLITS}
        return {_s: self.ratios.get(_s, 0.0) / _total for _s in SPLITS}

    @staticmethod
    def _sample_ref(stem: str, obj_id: str | None, class_id: str) -> Data_Ref:
        """sample leaf(=컨테이너 stem) — 정본 ``(stem, obj_id)`` 역참조 + class 이름 attr.

        payload 실체화(crop)는 안 한다(A+ 역참조) — 소비 측이 ``source_stem``/``source_obj`` 로 정본
        payload 를 ``handler.Load`` 한다. class 이름은 meta 처럼 ``class_id`` attr 로 든다.
        """
        _ref = Data_Ref(type="stem", info={})
        Set_attr(_ref, "source_stem", stem)
        if obj_id is not None:
            Set_attr(_ref, "source_obj", obj_id)
        if class_id:
            Set_attr(_ref, "class_id", class_id)
        return _ref

    @staticmethod
    def _set_param(sset: Sample_Set, name: str, value) -> None:
        """forest params(범주 무관 root leaf)에 인라인 attr 를 설정한다 (id_map 등)."""
        _a = sset.params.get(name)
        if isinstance(_a, Data_Ref):
            _a.info["value"] = value
        else:
            sset.params[name] = Data_Ref(type="attr", info={"value": value})

    # ── task 훅 ────────────────────────────────────────────────────────────────
    @abstractmethod
    def Place(self, sset: Sample_Set, split: str, stem: str,
              obj_id: str | None, ref: Data_Ref) -> None:
        """한 단위를 ``sset`` 트리에 꽂는다 — task 별 layout(class 폴더 / image→object)."""

    def Finalize(self, sset: Sample_Set, meta: Dataset_Meta) -> None:
        """순회 후 1회 — 집계 export(id_map·COCO manifest 등). 기본 no-op."""
        return None
