"""ImageFolder style classification sink — ``{split}/{class}/{sample}``.

class 가 split 아래 한 계층 더 생기는 layout(torchvision ``ImageFolder`` 와 1:1) — 사이드카는 class
단위(한 class 의 sample 을 통째로 담음). 배정·역참조 규약은 [`_base`](_base.py)(``Sample_sink``).
"""

from __future__ import annotations

from dataclasses import dataclass

from ...data.handler import Data_Ref
from ...data.schema import Attr
from ...process.source import Unit
from ._base import Sample_sink

UNLABELED = "unlabeled"   # class_id 가 없는 단위의 fallback class 폴더


@dataclass
class Classification_sink(Sample_sink):
    """class 폴더 style — ``{split}/{class}/{sample}``.

    unit(기본 object)마다 한 sample, class = unit 의 ``class_id`` attr(없으면 ``unlabeled``). class 가
    split 아래 한 계층 더 생기는 layout — meta(image→object) 보다 depth 가 하나 더 깊다.
    """

    def Place(self, split, unit: Unit, ctx: dict):
        _class = Attr(unit.obj, "class_id") or UNLABELED
        _sample_id = f"{unit.stem}_{unit.obj_id}" if unit.obj_id is not None else unit.stem
        _bucket = self.target.Bucket(split)
        _cls_stem = _bucket.setdefault(_class, Data_Ref(type="stem", info={}))
        _ref = self._sample_ref(unit.stem, unit.obj_id, _class)
        self._attach_crop(_ref, ctx, split, _class, _sample_id)   # crop 실체화 (있으면)
        _cls_stem.info[_sample_id] = _ref
