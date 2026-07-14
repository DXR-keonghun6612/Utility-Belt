"""mask 레이아웃 — 원본 이미지 + 인스턴스 라벨맵 png. segmentation 전용 serializer.

``{dest}/{split}/images/{stem}.{ext}`` + ``{split}/masks/{stem}.png``. mask png 는 인스턴스 라벨맵
(픽셀=obj_id+1) — sample 에 든 객체들로 재구성한다(정본 segment 와 같은 규약, 객체 집합만 sample 기준).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ._instance import Frame_exporter, Instance


@dataclass
class Mask_exporter(Frame_exporter):
    """인스턴스 라벨맵 png — segmentation 전용 (원본 이미지 + ``masks/{stem}.png``)."""

    def Export(self, dest: str | Path) -> None:
        self._require_meta()
        self._require_frame_samples()
        _out = Path(dest)
        for _split in self.source.CATEGORIES:
            for _rec in self._records(_split):
                _label = self._label_map(_rec.instances)
                if _label is None:                      # 그릴 mask 가 없는 프레임 — skip
                    continue
                self._copy_image(_rec, _out / _split / "images")
                _mdir = _out / _split / "masks"
                _mdir.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(_mdir / f"{_rec.stem}.png"), _label)

    @staticmethod
    def _label_map(instances: list[Instance]) -> np.ndarray | None:
        """인스턴스들 → 라벨맵 ``(H,W)`` uint8 (픽셀=obj_id+1). mask 가 하나도 없으면 None.

        uint8 이라 인스턴스 255개까지 — 정본 ``segmap`` 규약과 같은 한계(그 이상은 별도 승격 필요).
        """
        _with_mask = [(_i.obj_id, _i.mask) for _i in instances if _i.mask is not None]
        if not _with_mask:
            return None
        _h, _w = _with_mask[0][1].shape[:2]
        _canvas = np.zeros((_h, _w), np.uint8)
        for _oid, _m in _with_mask:
            try:
                _lbl = int(_oid) + 1
            except (TypeError, ValueError):
                continue
            _canvas[_m > 0] = _lbl
        return _canvas
