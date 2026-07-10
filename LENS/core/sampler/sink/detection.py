"""COCO style detection sink — 작업 버킷 아래 ``{image}/{object}`` (내보내기가 split·manifest 를 낸다).

meta 처럼 image(frame stem)→object 2단(계층 안 늘어남). split 배정·class→정수 ``id_map``·split 별
COCO manifest 는 파생이라 내보내기(``core/sampler/export``)가 소유한다 — 빌드 sink 는 배치만. 배정·
역참조 규약은 [`_base`](_base.py)(``Sample_sink``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from ...data.sample import SPLITS, WORKING
from ...data.schema import Attr
from ...process.source import Unit
from ._base import DEFAULT_RATIOS, Sample_sink


@dataclass
class Detection_sink(Sample_sink):
    """COCO style — 작업 버킷 아래 image→object 2단 (split·manifest 는 내보내기 소유).

    unit=object 로 순회하되 frame stem 으로 묶어 image 항목 아래에 object 를 꽂는다. classification 과
    달리 계층이 안 늘어난다(meta 와 같은 image→object). split 은 안 붙인다.
    """

    def Place(self, unit: Unit, ctx: dict):
        _bucket = self.target.Bucket(WORKING)
        _img = _bucket.setdefault(unit.stem, self._sample_ref(unit.stem, None, ""))
        if unit.obj_id is not None:
            _obj = self._sample_ref(unit.stem, unit.obj_id, Attr(unit.obj, "class_id"))
            self._attach_crop(_obj, ctx, unit.stem, unit.obj_id)   # crop 실체화 (있으면)
            _img.info[unit.obj_id] = _obj

    def Export(self, dest, *, ratios=None, salt: str = "", id_map=None):
        """``{image}/{object}`` → ``{dest}/{split}/{image}/{object}.png`` + split 별 COCO manifest·id_map.

        split 은 image(frame) stem 으로 배정하므로 한 이미지의 객체는 통째로 한 split 에 들어간다. class→
        정수 ``id_map`` 은 주어지면(정본 params) 그대로, 없으면 전 이미지의 class 를 모아 짓고, split 별
        images/annotations 를 채워 manifest 를 낸다.
        """
        _ratios = ratios or DEFAULT_RATIOS
        _out = Path(dest)
        _images = self.target.Bucket(WORKING)
        _classes = {
            Attr(_obj, "class_id")
            for _img in _images.values()
            for _obj in _img.info.values()
            if _obj.Is_stem() and Attr(_obj, "class_id")
        }
        _id_map = self._resolve_id_map(id_map, _classes)
        _docs = {_s: {"images": [], "annotations": []} for _s in SPLITS}
        _img_id = {_s: 1 for _s in SPLITS}
        _ann_id = {_s: 1 for _s in SPLITS}
        for _stem, _img in sorted(_images.items()):
            _split = self._assign(_stem, _ratios, salt)
            _iid = _img_id[_split]
            _img_id[_split] += 1
            _docs[_split]["images"].append(
                {"id": _iid, "file_name": Attr(_img, "source_stem") or _stem})
            for _oid, _obj in _img.info.items():
                if not _obj.Is_stem():
                    continue
                self._copy_crop(_obj, _out / _split, _oid)
                _docs[_split]["annotations"].append({
                    "id": _ann_id[_split], "image_id": _iid,
                    "category_id": _id_map.get(Attr(_obj, "class_id"), 0),
                    "source_obj": Attr(_obj, "source_obj") or _oid,
                })
                _ann_id[_split] += 1
        _categories = [{"id": _i, "name": _n} for _n, _i in _id_map.items()]
        for _split in SPLITS:
            Write_to(_out / _split / f"instances_{_split}.json",
                     {**_docs[_split], "categories": _categories})
        Write_to(_out / "id_map.json", _id_map)
