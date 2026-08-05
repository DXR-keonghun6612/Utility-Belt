"""객체별 mask 변형의 공용 순회 — 프레임의 객체마다 mask 를 풀어 함수를 돌리고 되싼다.

mask 를 **객체별로** 바꾸는 유닛들(refine·cut·morph …)이 같은 배선을 두 번 짜지 않게 여기 모은다.
각 객체의 rle mask 를 배열로 풀어 ``fn(frame, mask, region)`` 에 넘기고, 결과를 다시 rle·bbox 로 굳혀
새 ``Data_Ref`` 목록을 낸다. 알고리즘(무엇을 어떻게 바꾸나)은 ``fn`` 이 갖고, 여기는 순회·인코딩만 든다.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ....constant import UNCLASSIFIED_ID
from ....schema import Build, Data_Ref
from ....format import rle
from ....func.mask.instance import Scale_box


def mask_bbox(mask: np.ndarray) -> list[float] | None:
    """이진 mask 의 tight XYXY bbox (전경이 없으면 None)."""
    _ys, _xs = np.where(mask > 0)
    if _xs.size == 0:
        return None
    return [float(_xs.min()), float(_ys.min()), float(_xs.max() + 1), float(_ys.max() + 1)]


def box_region(box: list[float], shape: tuple[int, int]) -> np.ndarray:
    """XYXY bbox → ``(H,W)`` bool 사각 영역 (정수 클램프). ``Scale_box`` 출력을 정제 roi 로 쓰는 자리."""
    _h, _w = shape
    _x0, _y0, _x1, _y1 = box
    _sel = np.zeros(shape, bool)
    _sel[max(0, int(_y0)):min(_h, int(np.ceil(_y1))),
         max(0, int(_x0)):min(_w, int(np.ceil(_x1)))] = True
    return _sel


def map_objects(objects: list[Data_Ref], frame: np.ndarray, bbox_gap: float,
                fn: Callable[[np.ndarray, np.ndarray, np.ndarray | None], np.ndarray | None],
                ) -> list[Data_Ref]:
    """객체마다 ``fn(frame, mask, region)`` 을 돌려 mask·bbox 를 갈아끼운 새 목록을 만든다.

    ``region`` 은 그 객체 bbox 를 ``bbox_gap`` 만큼 넓힌 사각(없으면 mask 에서 잰다 — ``bbox_gap`` 이
    필요 없는 연산은 ``0.0`` 을 주고 ``fn`` 에서 region 을 무시하면 된다). rle mask 가 없는 객체와
    ``fn`` 이 빈 결과를 낸 객체는 **원본을 그대로 유지**한다 — 정제로 객체를 잃지 않는다.
    """
    _h, _w = frame.shape[:2]
    _new: list[Data_Ref] = []
    for _o in objects:
        _m = _o.Attr("mask", None)
        if not isinstance(_m, dict):                            # rle mask 가 없는 객체 → 그대로
            _new.append(_o)
            continue
        _mask = rle.To_mask(_m)
        _b = _o.Attr("bbox", None)
        _box = ([float(_x) for _x in _b] if isinstance(_b, (list, tuple)) and len(_b) == 4
                else mask_bbox(_mask))                          # bbox 없으면 mask 에서
        _region = box_region(Scale_box(_box, bbox_gap, _w, _h), (_h, _w)) \
            if _box is not None else None                       # bbox(XYXY)를 넓혀 여유
        _out = fn(frame, _mask, _region)
        _tight = mask_bbox(_out) if _out is not None else None
        if _out is None or _tight is None:                      # 실패 → 원본 유지
            _new.append(_o)
            continue
        _new.append(Data_Ref(info=Build({
            "class_id": {"format": ("", "int"),
                         "info": {"value": _o.Attr("class_id", None) or UNCLASSIFIED_ID}},
            "bbox":     {"format": ("region", "bbox", "xyxy"), "info": {"value": _tight}},
            "mask":     {"format": ("mask", "rle"), "info": {"value": rle.From_mask(_out)}},
        })))
    return _new
