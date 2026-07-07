"""ImageFolder style classification sampler — ``{split}/{class}/{sample}``.

class 가 split 아래 한 계층 더 생기는 layout(torchvision ``ImageFolder`` 와 1:1) — 사이드카는 class
단위(한 class 의 sample 을 통째로 담음). 빌드 뼈대·역참조 규약은 [`.._base`](../_base.py)(``Base_Sampler``).
"""

from __future__ import annotations

from dataclasses import dataclass

from ...handler import Data_Ref
from ...schema import Attr
from .._base import Base_Sampler

UNLABELED = "unlabeled"   # class_id 가 없는 단위의 fallback class 폴더


@dataclass
class Classification_Sampler(Base_Sampler):
    """class 폴더 style — ``{split}/{class}/{sample}``.

    단위(기본 object)마다 한 sample, class = 단위의 ``class_id`` attr(없으면 ``unlabeled``). class 가
    split 아래 한 계층 더 생기는 layout — meta(image→object) 보다 depth 가 하나 더 깊다.
    """

    def Place(self, sset, split, stem, obj_id, ref):
        _class = Attr(ref, "class_id") or UNLABELED
        _sample_id = f"{stem}_{obj_id}" if obj_id is not None else stem
        _bucket = sset.Bucket(split)
        _cls_stem = _bucket.setdefault(_class, Data_Ref(type="stem", info={}))
        _cls_stem.info[_sample_id] = self._sample_ref(stem, obj_id, _class)
