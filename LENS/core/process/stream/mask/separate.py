from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ....constant import UNCLASSIFIED_ID
from ....schema import Build, Data_Ref
from ....format import rle
from ....func.cv.geom import Roi_to_mask
from ....func.mask.instance import Split_components, Mask_of
from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE, BBOX


def _object(cls: int | None, box: list[float], mask: np.ndarray) -> Data_Ref:
    """조각 하나 → 객체 컨테이너(class_id·bbox·mask rle) — split 계열 공통 형식."""
    return Data_Ref(info=Build({
        "class_id": {"format": ("", "int"),                "info": {"value": cls or UNCLASSIFIED_ID}},
        "bbox":     {"format": ("region", "bbox", "xyxy"), "info": {"value": box}},
        "mask":     {"format": ("mask", "rle"),            "info": {"value": rle.From_mask(mask)}},
    }))


@PROCESS_REGISTRY.Register_module()
@dataclass
class Split_objects(Base_Process, outputs=("object",), category="마스크/분리"):
    """이진 mask 를 연결 요소로 쪼개 **객체마다 자기 mask 를 든** ``object`` 리스트를 만든다.

    분할 계산은 ``func.mask.instance.Split_components``. 라벨맵은 그 계산의 내부 표현일 뿐이라 **저장하지
    않고**, 컴포넌트마다 ``Mask_of`` 로 잘라 객체의 ``mask``(rle)로 인라인한다 — 객체별 mask 가 정본이다
    (mask 도메인). ``bbox``·``class_id`` 도 같은 객체 컨테이너에 담는다. ``class_id`` 는 프레임 ctx 값을
    그대로 물려주고, 없으면 ``__unclassified__``. 살아남은 객체가 없으면 빈 dict("스킵").

    선택 입력 ``edge``(producer 의 Canny 등)를 주면 그 경계를 따라 **붙어 나온 객체를 갈라낸다** —
    두 객체가 닿아 한 연결 요소로 뭉친 것을 사이 edge 로 끊어 각자 bbox 를 얻는다(``cut_grow`` 로 선을
    부풀려 확실히 끊음).
    """

    min_area:     Annotated[int,  UI(label="최소 객체 면적 (px²)", min=0, max=100000)] = 200
    mask_reverse: Annotated[bool, UI(label="mask 반전 (배경→전경)")]                   = False
    merge_gap:    Annotated[int,  UI(label="bbox 중심 병합 거리 (px, 0=끄기)",
                                     tip="bbox 중심점 거리가 이 값 이하면 한 객체로 묶음", min=0, max=999)] = 0
    bbox_gap:     Annotated[float, UI(label="bbox 확대/축소 비율 (-1~1)",
                                      tip="원본 대비 (0.1=10% 확대, -0.1=축소)",
                                      min=-1.0, max=1.0, step=0.05)]                  = 0.0
    cut_grow:     Annotated[int,  UI(label="edge 절단 팽창 (px, edge 입력 시)",
                                     tip="붙은 객체를 가를 edge 선을 이만큼 부풀려 목을 끊음", min=0, max=15)] = 1

    def Run(
        self, mask: GRAY_IMAGE, class_id: int | None = None,
        roi: BBOX | GRAY_IMAGE | None = None, edge: GRAY_IMAGE | None = None, **kwargs,
    ) -> dict:
        _cls = class_id or UNCLASSIFIED_ID      # 0·None 모두 미분류로

        _bin = mask > 0
        if self.mask_reverse:                   # 배경 mask → 전경 mask
            _bin = ~_bin
        _sel = Roi_to_mask(roi, _bin.shape)     # roi 밖은 버림 (None이면 전체)
        if _sel is not None:
            _bin &= _sel

        _seg, _boxes = Split_components(
            _bin, min_area=self.min_area, merge_gap=self.merge_gap, bbox_gap=self.bbox_gap,
            cut=edge, cut_grow=self.cut_grow)
        if not _boxes:
            return {}

        _objs = [_object(_cls, _box, Mask_of(_seg, _i))   # 라벨맵 조각 = 객체 mask (obj_id = 순번)
                 for _i, _box in enumerate(_boxes)]
        return {"object": _objs}                # 라벨맵은 위에서 mask 로 분산 — 저장/전달 안 함


@PROCESS_REGISTRY.Register_module()
@dataclass
class Separate_objects(Base_Process, outputs=("object",), category="마스크/분리"):
    """이미 만들어진 객체 중 **붙어 나온 것**을 ``edge`` 로 갈라 객체를 다시 만든다 (frame 단위).

    각 객체의 ``mask``(rle)를 ``edge``(Canny 등) 절단으로 재-연결성분 분리한다 — 한 덩어리로 붙은 두
    객체가 사이 edge 를 따라 둘로 갈린다(``cut_grow`` 로 선을 부풀려 확실히 끊음). 안 붙은 객체는 그대로
    하나. ``class_id`` 는 원 객체에서 물려받고 bbox·mask 는 조각마다 새로 낸다. **확장 전에** 돌려야
    깔끔하다 — 확장으로 부풀린 뒤엔 목이 두꺼워져 못 끊는다. ``edge`` 가 없으면 무연산 통과, 객체가
    없으면 스킵(``{}``).
    """

    min_area: Annotated[int, UI(label="최소 조각 면적 (px²)", min=0, max=100000)]            = 200
    cut_grow: Annotated[int, UI(label="edge 절단 팽창 (px)",
                               tip="붙은 객체를 가를 edge 선을 이만큼 부풀려 목을 끊음", min=0, max=15)] = 1

    def Run(
        self, object: list[Data_Ref], edge: GRAY_IMAGE | None = None, **kwargs,
    ) -> dict:
        if not object:
            return {}
        if edge is None:                        # 절단선 없음 → 그대로 통과
            return {"object": list(object)}
        _new: list[Data_Ref] = []
        for _o in object:
            _m = _o.Attr("mask", None)
            if not isinstance(_m, dict):        # rle mask 없는 객체 → 그대로
                _new.append(_o)
                continue
            _cls = _o.Attr("class_id", None)
            _seg, _boxes = Split_components(
                rle.To_mask(_m), min_area=self.min_area, cut=edge, cut_grow=self.cut_grow)
            if not _boxes:                      # 다 걸러짐 → 원본 유지(데이터 안 잃음)
                _new.append(_o)
                continue
            _new.extend(_object(_cls, _box, Mask_of(_seg, _i))
                        for _i, _box in enumerate(_boxes))
        return {"object": _new} if _new else {}
