"""COCO style detection sink — ``{split}/{image}/{object}`` + split 별 ``instances_{split}.json``.

meta 처럼 image(frame stem)→object 2단(계층 안 늘어남). ``Finalize`` 가 class→정수 ``id_map`` 을 짓고
(정본은 class 이름만) split 별 COCO manifest(images + annotations)를 낸다. 배정·역참조 규약은
[`_base`](_base.py)(``Sample_sink``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from ...data.schema import Attr
from ...data.sample import SPLITS
from ...process.source import Unit
from ._base import Sample_sink


@dataclass
class Detection_sink(Sample_sink):
    """COCO style — image→object 2단 + split 별 COCO manifest.

    unit=object 로 순회하되 frame stem 으로 묶어 image 항목 아래에 object 를 꽂는다. classification 과
    달리 계층이 안 늘어난다(meta 와 같은 image→object). class→정수 매핑(``id_map``)은 이 계층 소유.
    """

    def Place(self, split, unit: Unit, ctx: dict):
        _bucket = self.target.Bucket(split)
        _img = _bucket.setdefault(unit.stem, self._sample_ref(unit.stem, None, ""))
        if unit.obj_id is not None:
            _obj = self._sample_ref(unit.stem, unit.obj_id, Attr(unit.obj, "class_id"))
            self._attach_crop(_obj, ctx, split, unit.stem, unit.obj_id)   # crop 실체화 (있으면)
            _img.info[unit.obj_id] = _obj

    def Finalize(self):
        """class→정수 id_map(params) + split 별 COCO manifest(images/annotations) 를 낸다."""
        _classes = sorted({
            Attr(_obj, "class_id")
            for _split in SPLITS
            for _img in self.target.Bucket(_split).values()
            for _obj in _img.info.values()
            if _obj.Is_stem() and Attr(_obj, "class_id")
        })
        _id_map = {_name: _i for _i, _name in enumerate(_classes, start=1)}
        self._set_param("id_map", _id_map)
        for _split in SPLITS:
            self._write_manifest(_split, _id_map)

    def _write_manifest(self, split: str, id_map: dict[str, int]) -> None:
        """split 하나의 COCO-ish manifest 를 ``{root}/{split}/instances_{split}.json`` 로 쓴다."""
        _images, _annotations, _ann_id = [], [], 1
        for _img_id, (_stem, _img) in enumerate(sorted(self.target.Bucket(split).items()), start=1):
            _images.append({"id": _img_id, "file_name": Attr(_img, "source_stem") or _stem})
            for _oid, _obj in _img.info.items():
                if not _obj.Is_stem():
                    continue
                _annotations.append({
                    "id": _ann_id, "image_id": _img_id,
                    "category_id": id_map.get(Attr(_obj, "class_id"), 0),
                    "source_obj": Attr(_obj, "source_obj") or _oid,
                })
                _ann_id += 1
        _doc = {
            "images": _images,
            "annotations": _annotations,
            "categories": [{"id": _i, "name": _n} for _n, _i in id_map.items()],
        }
        Write_to(Path(self.target.Category_root(split)) / f"instances_{split}.json", _doc)
