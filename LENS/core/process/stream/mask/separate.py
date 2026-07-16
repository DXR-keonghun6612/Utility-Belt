from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from ....schema import Build, Data_Ref
from ....func.cv.geom import Roi_to_mask
from ....func.mask.instance import Split_components
from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE, BBOX


@PROCESS_REGISTRY.Register_module()
@dataclass
class Split_objects(Base_Process, outputs=("segment", "object"), category="마스크/분리"):
    """이진 mask 를 연결 요소로 쪼개 인스턴스 ``segment`` 맵 + ``object`` 리스트를 만든다.

    분할 계산은 ``func.mask.instance.Split_components``. 이 유닛은 roi/반전 적용과 결과 bbox 를 객체
    컨테이너(``Data_Ref``)로 조립하는 일만 한다. ``class_id`` 는 프레임 ctx 값을 그대로 물려주고,
    없으면 ``__unclassified__``. 살아남은 객체가 없으면 빈 dict("스킵").
    """

    min_area:     Annotated[int,  UI(label="최소 객체 면적 (px²)", min=0, max=100000)] = 200
    mask_reverse: Annotated[bool, UI(label="mask 반전 (배경→전경)")]                   = False
    merge_gap:    Annotated[int,  UI(label="bbox 중심 병합 거리 (px, 0=끄기)",
                                     tip="bbox 중심점 거리가 이 값 이하면 한 객체로 묶음", min=0, max=999)] = 0
    bbox_gap:     Annotated[float, UI(label="bbox 확대/축소 비율 (-1~1)",
                                      tip="원본 대비 (0.1=10% 확대, -0.1=축소)",
                                      min=-1.0, max=1.0, step=0.05)]                  = 0.0

    def Run(
        self, mask: GRAY_IMAGE, class_id: str | None = None,
        roi: BBOX | GRAY_IMAGE | None = None, **kwargs,
    ) -> dict:
        _cls = class_id or "__unclassified__"   # 빈 문자열·None 모두 기본값으로

        _bin = mask > 0
        if self.mask_reverse:                   # 배경 mask → 전경 mask
            _bin = ~_bin
        _sel = Roi_to_mask(roi, _bin.shape)     # roi 밖은 버림 (None이면 전체)
        if _sel is not None:
            _bin &= _sel

        _seg, _boxes = Split_components(
            _bin, min_area=self.min_area, merge_gap=self.merge_gap, bbox_gap=self.bbox_gap)
        if not _boxes:
            return {}

        _objs = [                               # obj_id = 리스트 순번 (sink 가 info key 로 씀)
            Data_Ref(info=Build({
                "class_id": {"format": ("", "str"),                "info": {"value": _cls}},
                "bbox":     {"format": ("region", "bbox", "xyxy"), "info": {"value": _box}},
            }))
            for _box in _boxes
        ]
        return {"segment": _seg, "object": _objs}
