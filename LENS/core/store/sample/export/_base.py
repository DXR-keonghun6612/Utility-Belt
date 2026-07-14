"""Exporter 계약 — 파생 store → 학습 프레임워크 레이아웃.

**task·format 이 사는 곳은 여기다** — 그래서 파생(sample) 안쪽이다. 빌드는 무엇을 뽑을지(``unit``·crop)만
정하고 레이아웃은 모른다. 축이 둘이다(레지스트리·조합 설명은 [`__init__.py`](__init__.py)):

- **task** = 데이터 성격 (classification / detection / segmentation) — 빌드 ``unit`` 과 mask 필요 여부를 건다.
- **format** = 직렬화 레이아웃 (imagefolder / coco / yolo / mask) — 같은 task 를 여러 모양으로 낸다.

한 serializer 가 여러 task 를 겸한다 — ``Coco``·``Yolo`` 는 detection·segmentation 을 함께 섬기고 task 가
mask 를 토글한다([`_instance.py`](_instance.py) 의 ``Frame_exporter`` 공통 base). 원본(작업 store)은
비파괴 — payload 는 ``port.Path_of`` 로 원본 파일을 찾아 **복사**한다(디코드·재인코딩 없음).

split 은 **재배정하지 않는다** — store 가 이미 split 범주로 갈려 있다(빌드가 배정). 여기선 순회할 뿐이다.
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
    task:   str                    = ""    # 공유 serializer 가 데이터 성격을 읽는 자리 (seg→mask 토글)

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
