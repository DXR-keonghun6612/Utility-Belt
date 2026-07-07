from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ...data.handler import Data_Ref
from ...data.meta import Dataset_Meta
from .. import PROCESS_REGISTRY
from .._base import Base_Process, GRAY_IMAGE


def _bbox(obj: Data_Ref) -> list[float] | None:
    """object 의 ``info["bbox"]`` 인라인 값 ``[x0,y0,x1,y1]`` (없거나 형식 불량이면 None)."""
    _ref = obj.info.get("bbox")
    if _ref is None:
        return None
    _v = _ref.info.get("value")
    if not (isinstance(_v, (list, tuple)) and len(_v) == 4):
        return None
    return [float(_x) for _x in _v]


@PROCESS_REGISTRY.Register_module()
@dataclass
class Order_objects(Base_Process, outputs=("segment", "object"), category="마스크/분리"):
    """객체를 **이미지 중심에서 가까운 순**으로 정렬해 ``obj_id`` 를 0부터 다시 부여한다.

    각 객체 bbox 중심과 이미지 중심(``segment`` 크기 기준) 사이 유클리드 거리로 오름차순 정렬해
    가장 가까운 객체가 ``obj_id="0"`` 이 되고, ``segment`` 라벨맵도 새 순서에 맞춰 재라벨한다
    (픽셀 형태는 그대로, 값=obj_id+1 만 갱신). class_id·bbox 등 나머지 데이터는 그대로 유지한다.

    **라벨 매칭은 obj_id 산술이 아니라 bbox 위치**로 한다 — 각 객체의 현재 segmap 라벨을 그 bbox
    안 최빈 라벨로 찾는다. obj_id 와 segmap 라벨이 어긋난(예: 이전에 object 만 재정렬되고 segment
    는 안 써진) desync 상태도 이 프로세스를 한 번 돌리면 위치 기준으로 다시 맞춰진다(self-heal).
    bbox 없거나 segmap 에 대응 라벨이 없는 객체는 맨 뒤로 밀고 segment 에선 빠진다. 객체 없으면
    빈 dict("스킵").
    """

    def _label_in_bbox(self, segment: GRAY_IMAGE, box: list[float] | None) -> int:
        """bbox 안 최빈 non-zero segmap 라벨(=그 객체의 현재 라벨). 없으면 0."""
        if box is None:
            return 0
        _h, _w = segment.shape[:2]
        _x0 = max(int(round(box[0])), 0);  _y0 = max(int(round(box[1])), 0)
        _x1 = min(int(round(box[2])), _w); _y1 = min(int(round(box[3])), _h)
        if _x1 <= _x0 or _y1 <= _y0:
            return 0
        _crop = segment[_y0:_y1, _x0:_x1]
        _vals = _crop[_crop > 0]
        return int(np.bincount(_vals).argmax()) if _vals.size else 0

    def Run(self, segment: GRAY_IMAGE, meta: Dataset_Meta, stem: str, **kwargs) -> dict:
        _frame = meta.Find(stem)
        _objs  = ([_v for _v in _frame.info.values() if _v.Is_stem()]
                  if _frame is not None else [])
        if not _objs:
            return {}

        _h, _w   = segment.shape[:2]
        _cx, _cy = _w / 2.0, _h / 2.0

        # (이미지 중심까지 제곱거리, 현재 segmap 라벨, 객체). bbox 없으면 거리 inf → 맨 뒤.
        _info: list[tuple[float, int, Data_Ref]] = []
        for _o in _objs:
            _b = _bbox(_o)
            _d = (float("inf") if _b is None
                  else ((_b[0] + _b[2]) / 2.0 - _cx) ** 2 + ((_b[1] + _b[3]) / 2.0 - _cy) ** 2)
            _info.append((_d, self._label_in_bbox(segment, _b), _o))
        _info.sort(key=lambda _t: _t[0])

        # old 라벨 → 새 라벨(rank+1) LUT 로 한 번에 remap. 라벨 충돌 시 더 가까운 객체가 이긴다.
        _lut = np.zeros(int(segment.max()) + 1, np.uint8)
        _new: list[Data_Ref] = []                        # 정렬 순서 = 새 obj_id(_route info key)
        for _rank, (_d, _old, _o) in enumerate(_info):
            if _old > 0 and _lut[_old] == 0:
                _lut[_old] = np.uint8(_rank + 1)
            _new.append(Data_Ref(type="stem", info=dict(_o.info)))   # class_id 는 info["class_id"] 로 딸려옴

        return {"segment": _lut[segment], "object": _new}
