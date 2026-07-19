"""COCO 레이아웃 — 원본 이미지 + annotation json. detection·segmentation 공용 serializer.

``{dest}/{split}/images/{stem}.{ext}`` + ``{split}/instances_{split}.json``. COCO 는 **원본 이미지 +
annotation** 이라 픽셀은 sample 이 아니라 정본 프레임에서 복사한다. task 가 ``segmentation`` 이면 각
annotation 에 ``segmentation`` 필드(인스턴스 mask)를 더 낸다 — 그 외엔 bbox 만(detection).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from ._instance import Frame_exporter, Instance


@dataclass
class Coco_exporter(Frame_exporter):
    """``instances_{split}.json`` (COCO) — bbox+class, segmentation task 면 mask 도.

    class 는 sample 인스턴스의 ``class_id`` attr 에서 읽는다 — class-agnostic(attr 없음)이면 단일
    카테고리로 접힌다(``id_map`` 이 비어 category 가 하나). detection·segmentation 이 이 한 클래스를
    공유하고, ``segmentation`` 필드는 :meth:`_needs_mask` 일 때만 붙는다.
    """

    def Export(self, dest: str | Path) -> None:
        self._require_meta()
        self._require_frame_samples()
        _out = Path(dest)
        _ids = self._resolve_id_map(self._classes())

        for _split in self.source.CATEGORIES:
            _images: list[dict] = []
            _anns:   list[dict] = []
            for _iid, _rec in enumerate(self._records(_split), start=1):
                _file = self._copy_image(_rec, _out / _split / "images")
                _images.append({"id": _iid, "file_name": _file or f"{_rec.stem}.png"})
                for _inst in _rec.instances:
                    _anns.append(self._annotation(_inst, _iid, len(_anns) + 1, _ids))
            Write_to(_out / _split / f"instances_{_split}.json", {
                "images":      _images,
                "annotations": _anns,
                "categories":  [{"id": _i, "name": _n} for _n, _i in _ids.items()],
            })
        Write_to(_out / "id_map.json", _ids)

    # ── annotation 조립 ─────────────────────────────────────────────────────────
    def _annotation(self, inst: Instance, image_id: int, ann_id: int,
                    ids: dict[str, int]) -> dict:
        """한 인스턴스 → COCO annotation. mask 가 있으면 ``segmentation`` 필드까지 (segmentation task)."""
        _bbox = self._coco_bbox(inst.bbox)
        _ann = {
            "id":          ann_id,
            "image_id":    image_id,
            "category_id": ids.get(inst.class_id, 0),      # class-agnostic 이면 0
            "bbox":        _bbox,
            "area":        self._area(inst.mask, _bbox),
            "iscrowd":     0,
            "source_obj":  inst.obj_id,
        }
        if inst.mask is not None:
            _ann["segmentation"] = self._segmentation(inst.mask)
        return _ann

    @staticmethod
    def _coco_bbox(bbox: list[float] | None) -> list[float]:
        """정본 ``xyxy`` 코너 → COCO ``[x, y, w, h]`` (좌상단+폭높이). 없으면 ``[]``."""
        if not bbox:
            return []
        _x0, _y0, _x1, _y1 = bbox
        return [_x0, _y0, _x1 - _x0, _y1 - _y0]

    @staticmethod
    def _area(mask, bbox: list[float]) -> float:
        """annotation area — mask 있으면 전경 픽셀 수, 없으면 bbox 넓이 (COCO 평가가 요구)."""
        if mask is not None:
            return float(int(mask.sum()))
        return float(bbox[2] * bbox[3]) if bbox else 0.0

    def _segmentation(self, mask) -> dict:
        """인스턴스 mask → COCO ``segmentation`` RLE — codec 은 store 경유로 얻는다.

        pycocotools RLE 라 detectron2·mmdet 등이 그대로 먹는다. RLE 코덱은 port(`rle` codec)가 소유하는데,
        export 는 binder 라 port 를 직접 못 부른다(소비자는 store 하나) — ``source.Encode`` 로 mask 를 인라인
        ``rle`` ``Data_Ref`` 로 만들어(디스크 안 씀) 그 값을 읽는다. 같은 인코딩을 두 곳에서 안 짠다.
        """
        return self.source.Encode({"type": "mask", "format": "rle"}, mask).info["value"]
