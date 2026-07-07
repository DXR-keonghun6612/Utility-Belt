"""COCO style detection sampler — ``{split}/{image}/{object}`` + split 별 ``instances_{split}.json``.

meta 처럼 image(frame stem)→object 2단(계층 안 늘어남). ``Finalize`` 가 class→정수 ``id_map`` 을 짓고
(정본은 class 이름만) split 별 COCO manifest(images + annotations)를 낸다. 빌드 뼈대·역참조 규약은
[`.._base`](../_base.py)(``Base_Sampler``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from ...schema import Attr
from .._base import SPLITS, Base_Sampler


@dataclass
class Detection_Sampler(Base_Sampler):
    """COCO style — image→object 2단 + split 별 COCO manifest.

    단위=object 로 순회하되 frame stem 으로 묶어 image 항목 아래에 object 를 꽂는다. classification 과
    달리 계층이 안 늘어난다(meta 와 같은 image→object). class→정수 매핑(``id_map``)은 이 계층 소유.
    """

    unit: str = "object"

    def Place(self, sset, split, stem, obj_id, ref):
        _bucket = sset.Bucket(split)
        _img = _bucket.setdefault(stem, self._sample_ref(stem, None, ""))
        if obj_id is not None:
            _img.info[obj_id] = self._sample_ref(stem, obj_id, Attr(ref, "class_id"))

    def Finalize(self, sset, meta):
        """class→정수 id_map(params) + split 별 COCO manifest(images/annotations) 를 낸다."""
        _classes = sorted({
            Attr(_obj, "class_id")
            for _split in SPLITS
            for _img in sset.Bucket(_split).values()
            for _obj in _img.info.values()
            if _obj.Is_stem() and Attr(_obj, "class_id")
        })
        _id_map = {_name: _i for _i, _name in enumerate(_classes, start=1)}
        self._set_param(sset, "id_map", _id_map)
        for _split in SPLITS:
            self._write_manifest(sset, _split, _id_map)

    def _write_manifest(self, sset, split: str, id_map: dict[str, int]) -> None:
        """split 하나의 COCO-ish manifest 를 ``{root}/{split}/instances_{split}.json`` 로 쓴다."""
        _images, _annotations, _ann_id = [], [], 1
        for _img_id, (_stem, _img) in enumerate(sorted(sset.Bucket(split).items()), start=1):
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
        Write_to(Path(sset.Category_root(split)) / f"instances_{split}.json", _doc)
