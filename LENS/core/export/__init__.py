"""내보내기 — 파생(sample) store → 학습 프레임워크 레이아웃. **binder 계층** (func·store 조율).

내보내기는 store 라이프사이클(전이·삭제·병합·pop)이 아니라 read+compute+external-write 다 — 정본·파생
store 를 **읽어** 계산하고 트리 **밖**에 쓸 뿐, store 를 안 바꾼다. 그래서 store 메서드가 아니라 여기(binder)
가 든다: 유일하게 func(합성)·store(`Data_Ref` codec·경로)를 함께 조율할 수 있는 계층이다. **port 는 직접
안 부른다** — codec 은 store 경유(`Path_of`·`Encode`).

축 둘: **task × format**.

- **task** = 데이터 성격 (classification / detection / segmentation). 빌드 ``unit`` 과 mask 필요 여부를 건다.
- **format** = 직렬화 레이아웃 (imagefolder / coco / yolo / mask). 같은 task 를 여러 모양으로 낸다.

``EXPORTERS[(task, format)]`` 가 조합을 exporter 로 건다 — 한 serializer 가 여러 task 를 겸할 수 있다
(``Coco``·``Yolo`` 는 detection·segmentation 을 함께, task 가 mask 를 토글). 새 조합은 **파일 하나 +
``EXPORTERS`` 한 줄**. task 계약(빌드 제약)은 ``TASKS``. 진입점은 :func:`Run_export`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..store import Sample_Set
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


def Run_export(source: Sample_Set, dest: str | Path, *, task: str, format: str | None = None,
               meta=None, id_map: dict[str, int] | None = None) -> Path:
    """파생 store 를 ``(task, format)`` 레이아웃으로 ``dest`` 아래에 실체화한다 (원본 비파괴).

    **split 은 재배정하지 않는다** — store 가 이미 split 범주로 갈려 있다(빌드가 배정). 여기서 정하는 건
    레이아웃뿐이다: ``task``(데이터 성격) × ``format``(직렬화)를 ``EXPORTERS`` 로 조합해 고른다.

    Args:
        source: 내보낼 파생 store (split 범주).
        dest:   산출물 루트.
        task:   데이터 성격 (``TASKS`` 의 key).
        format: 직렬화 레이아웃 (미지정 → task 기본).
        meta:   정본 store — 프레임 픽셀·객체가 sample 이 아니라 정본에 있어 필요하다(det/seg).
        id_map: class→정수. None 이면 class 정렬로 생성.

    Raises:
        ValueError: task 가 없거나 그 task 에 format 조합의 exporter 가 없을 때.
    """
    if task not in TASKS:
        raise ValueError(f"알 수 없는 sample task: {task!r} (가능: {', '.join(sorted(TASKS))})")
    _format = format or TASKS[task].default_format          # 미지정 → task 기본 레이아웃
    try:
        _cls = EXPORTERS[(task, _format)]
    except KeyError:
        raise ValueError(f"task {task!r} 에 format {_format!r} 조합이 없다 "
                         f"(가능: {', '.join(Formats_for(task))})") from None
    _out = Path(dest)
    _cls(source=source, meta=meta, id_map=id_map, task=task).Export(_out)
    return _out


__all__ = ["Exporter", "Frame_exporter", "ImageFolder_exporter", "Coco_exporter",
           "Yolo_exporter", "Mask_exporter", "Task_spec", "TASKS", "EXPORTERS",
           "Formats_for", "Run_export"]
