"""내보내기 — 파생(sample) store → 학습 프레임워크 레이아웃. 축 둘: **task × format**.

- **task** = 데이터 성격 (classification / detection / segmentation). 빌드 ``unit`` 과 mask 필요 여부를 건다.
- **format** = 직렬화 레이아웃 (imagefolder / coco / yolo / mask). 같은 task 를 여러 모양으로 낸다.

``EXPORTERS[(task, format)]`` 가 조합을 exporter 로 건다 — 한 serializer 가 여러 task 를 겸할 수 있다
(``Coco``·``Yolo`` 는 detection·segmentation 을 함께, task 가 mask 를 토글). 새 조합은 **파일 하나 +
``EXPORTERS`` 한 줄**. task 계약(빌드 제약)은 ``TASKS``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._base import Exporter
from ._instance import Frame_exporter
from .classification import ImageFolder_exporter
from .coco import Coco_exporter
from .yolo import Yolo_exporter
from .mask import Mask_exporter


@dataclass(frozen=True)
class Task_spec:
    """task 의 빌드 계약 — 무엇을 뽑아야 이 task 로 내보낼 수 있나.

    Attributes:
        unit:           빌드 순회 단위 — object(crop) / frame(객체들).
        needs_mask:     정본 ``segment`` 필수? (segmentation) — 없으면 실행 전에 막는다.
        default_format: 미지정 시 기본 format.
    """

    unit:           str
    needs_mask:     bool
    default_format: str


TASKS: dict[str, Task_spec] = {
    "classification": Task_spec(unit="object", needs_mask=False, default_format="imagefolder"),
    "detection":      Task_spec(unit="frame",  needs_mask=False, default_format="coco"),
    "segmentation":   Task_spec(unit="frame",  needs_mask=True,  default_format="coco"),
}

# (task, format) → exporter. det/seg 가 coco·yolo serializer 를 공유(task 가 mask 토글).
EXPORTERS: dict[tuple[str, str], type[Exporter]] = {
    ("classification", "imagefolder"): ImageFolder_exporter,
    ("detection",      "coco"):        Coco_exporter,
    ("detection",      "yolo"):        Yolo_exporter,
    ("segmentation",   "coco"):        Coco_exporter,
    ("segmentation",   "yolo"):        Yolo_exporter,
    ("segmentation",   "mask"):        Mask_exporter,
}


def Formats_for(task: str) -> list[str]:
    """이 task 가 지원하는 format 목록 (GUI 가 유효 조합만 제시하게) — 기본 format 이 맨 앞."""
    _default = TASKS[task].default_format if task in TASKS else None
    _fmts = [_f for (_t, _f) in EXPORTERS if _t == task]
    return sorted(_fmts, key=lambda _f: (_f != _default, _f))


__all__ = ["Exporter", "Frame_exporter", "ImageFolder_exporter", "Coco_exporter",
           "Yolo_exporter", "Mask_exporter", "Task_spec", "TASKS", "EXPORTERS", "Formats_for"]
