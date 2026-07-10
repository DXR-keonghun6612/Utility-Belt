"""ImageFolder style classification sink — ``{split}/{class}/{sample}``.

class 가 split 아래 한 계층 더 생기는 layout(torchvision ``ImageFolder`` 와 1:1) — 사이드카는 class
단위(한 class 의 sample 을 통째로 담음). 배정·역참조 규약은 [`_base`](_base.py)(``Sample_sink``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from ...data.handler import Data_Ref
from ...constant import UNCLASSIFIED
from ...data.sample import WORKING
from ...data.schema import Attr
from ...process.source import Unit
from ._base import DEFAULT_RATIOS, Sample_sink

UNLABELED = UNCLASSIFIED   # class_id 가 없는 단위의 fallback class (정본 미분류 값 __unclassified__ 와 통일)


@dataclass
class Classification_sink(Sample_sink):
    """class 폴더 style — 작업 버킷 아래 ``{class}/{sample}`` (내보내기가 ``{split}/{class}/{sample}`` 로 가름).

    unit(기본 object)마다 한 sample, class = unit 의 ``class_id`` attr(없으면 ``unlabeled``). class 가
    작업 버킷 아래 한 계층 — meta(image→object) 보다 depth 가 하나 더 깊다. split 은 안 붙인다.
    """

    def Place(self, unit: Unit, ctx: dict):
        _class = Attr(unit.obj, "class_id") or UNLABELED
        _sample_id = f"{unit.stem}_{unit.obj_id}" if unit.obj_id is not None else unit.stem
        _bucket = self.target.Bucket(WORKING)
        _cls_stem = _bucket.setdefault(_class, Data_Ref(type="stem", info={}))
        _ref = self._sample_ref(unit.stem, unit.obj_id, _class)
        self._attach_crop(_ref, ctx, _class, _sample_id)   # crop 실체화 (있으면)
        _cls_stem.info[_sample_id] = _ref

    def Export(self, dest, *, ratios=None, salt: str = "", id_map=None):
        """``{class}/{sample}`` → ``{dest}/{split}/{class}/{sample}.png`` (ImageFolder; crop 만 복사) + id_map.json.

        split 은 sample 의 정본 프레임(``source_stem``) 해시로 배정 — 같은 프레임에서 나온 crop 은 한
        split 에 몰린다. crop payload 가 실체화된 sample 만 픽셀이 나온다(레시피에 ``frame_crop`` 필요).
        class↔index 매핑(``id_map``)은 주어지면(정본 params) 그대로, 없으면 class 정렬로 생성해 ``id_map.json``
        으로 낸다 — 폴더명이 class 라 학습 측 index 일관성용.
        """
        _ratios = ratios or DEFAULT_RATIOS
        _out = Path(dest)
        for _cls_stem in self.target.Bucket(WORKING).values():
            for _sid, _ref in _cls_stem.info.items():
                _split = self._assign(Attr(_ref, "source_stem") or _sid, _ratios, salt)
                self._copy_crop(_ref, _out / _split, _sid)
        Write_to(_out / "id_map.json", self._resolve_id_map(id_map, self.target.Bucket(WORKING)))
