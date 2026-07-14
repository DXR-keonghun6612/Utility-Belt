"""YOLO 레이아웃 — 이미지 + 정규화 txt 라벨. detection·segmentation 공용 serializer (골격).

``{dest}/{split}/images/{stem}.{ext}`` + ``{split}/labels/{stem}.txt`` + ``classes.txt``. detection 은
줄마다 ``cls cx cy w h``(이미지 크기로 정규화), segmentation 은 ``cls x1 y1 x2 y2 …``(정규화 polygon).

TODO(yolo): 실제 직렬화 미구현 — ``Frame_exporter._records`` 중간표현은 서 있으니, 좌표 정규화(이미지
크기 필요)와 polygon 추출(seg)만 채우면 된다. detection→box, segmentation→polygon 을 ``_needs_mask``
로 가른다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._instance import Frame_exporter


@dataclass
class Yolo_exporter(Frame_exporter):
    """YOLO txt 라벨 — detection(box) / segmentation(polygon). **미구현 골격**."""

    def Export(self, dest: str | Path) -> None:
        self._require_meta()
        self._require_frame_samples()
        raise NotImplementedError(
            "YOLO export 미구현 — Frame_exporter 중간표현 위에 좌표 정규화(det=box, seg=polygon)만 "
            "채우면 된다. (task 별 (detection/segmentation, yolo) 조합은 EXPORTERS 에 이미 등록됨)")
