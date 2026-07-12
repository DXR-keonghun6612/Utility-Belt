"""Exporter 계약 — 파생 store → 학습 프레임워크 레이아웃.

**task 가 사는 곳은 여기다** — 그래서 파생(sample) 안쪽이다. 빌드는 무엇을 뽑을지만 정하고 task 를
모른다. classification 이냐 detection 이냐는 *같은 데이터를 어떤 폴더 모양으로 내놓느냐*의 문제이고,
그 축이 서로 배타적이라 store 구조로는 둘 다 못 섬긴다:

- **ImageFolder** (classification) — ``{split}/{class}/{sample}.png``. **class-major**: 폴더명이 곧 라벨.
- **COCO** (detection) — ``{split}/images/{stem}.png`` + ``instances_{split}.json``. **kind-major**:
  픽셀과 annotation 이 갈리고 class 는 json 안 정수.

그래서 store 는 축을 하나만(kind-major) 고르고, 학습셋 관행은 여기서 옮겨 짓는다. 원본(작업 store)은
비파괴 — payload 는 ``port.Path_of`` 로 원본 파일을 찾아 **복사**한다(디코드·재인코딩 없음).

split 은 **재배정하지 않는다** — store 가 이미 split 범주로 갈려 있다(빌드가 배정). 여기선 순회할 뿐이다.

**task 하나 = 파일 하나** — [`classification.py`](classification.py) · [`detection.py`](detection.py).
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ....constant import UNCLASSIFIED as UNLABELED
from ...meta import Dataset_Meta
from ..store import Sample_Set

__all__ = ["Exporter", "UNLABELED"]


@dataclass
class Exporter(ABC):
    """파생 store → 학습셋 레이아웃 (task 별 서브클래스).

    Attributes:
        source: 파생 store — 내보낼 sample 들 (split 범주로 이미 갈려 있다).
        meta:   정본 store — sample 이 순수 역참조라 픽셀이 여기 있을 수 있다(detection 의 프레임 이미지).
        id_map: class→정수 매핑. 주어지면(정본 params 유래) 그대로, None 이면 class 정렬로 생성.
    """

    source: Sample_Set
    meta:   Dataset_Meta | None    = None
    id_map: dict[str, int] | None  = None

    @abstractmethod
    def Export(self, dest: str | Path) -> None:
        """``dest`` 아래에 이 task 의 레이아웃으로 실체화한다."""

    # ── 공통 ──────────────────────────────────────────────────────────────────
    def _resolve_id_map(self, classes) -> dict[str, int]:
        """class→정수 확정 — 주어지면 그대로, 없으면 class 정렬로 1부터."""
        return (dict(self.id_map) if self.id_map else
                {_c: _i for _i, _c in enumerate(sorted(classes), start=1)})

    @staticmethod
    def _copy(src: Path | None, dst: Path) -> bool:
        """원본 파일 → dst 로 복사 (없으면 False). 부모 dir 보장."""
        if src is None or not src.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
