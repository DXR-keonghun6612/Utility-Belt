"""내보내기 — 파생 store → 학습 프레임워크 레이아웃. **task 하나 = 파일 하나.**

task 축은 파생(sample) **안쪽에만** 산다 — 정본은 task 를 모르고, 빌드도 무엇을 뽑을지만 정한다.
task 는 *같은 데이터를 어떤 폴더 모양으로 내놓느냐*라서 **내보낼 때** 비로소 의미가 생긴다.

계약·근거는 [`_base.py`](_base.py). 새 포맷(YOLO 등)은 **파일 하나 + `EXPORTERS` 한 줄**.
"""

from ._base import Exporter
from .classification import ImageFolder_exporter
from .detection import Coco_exporter

# 레시피의 task → exporter. 새 포맷은 여기 한 줄.
EXPORTERS: dict[str, type[Exporter]] = {
    "classification": ImageFolder_exporter,
    "detection":      Coco_exporter,
}

__all__ = ["Exporter", "ImageFolder_exporter", "Coco_exporter", "EXPORTERS"]
