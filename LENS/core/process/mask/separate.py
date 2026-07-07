from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from ...data.handler import Data_Ref
from ..utils.mask import Roi_to_mask
from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, GRAY_IMAGE, BBOX


@PROCESS_REGISTRY.Register_module()
@dataclass
class Split_objects(Base_Process, outputs=("segment", "object"), category="마스크/분리"):
    """이진 mask 를 연결 요소로 쪼개 인스턴스 ``segment`` 맵 + ``object`` 리스트를 만든다.

    한 번의 ``connectedComponents`` 로 (H,W) 라벨맵(픽셀=obj_id+1, 0=배경, ``segmap`` 저장)과
    요소별 bbox 객체(컨테이너 ``Data_Ref``) 리스트를 낸다. ``min_area``/``merge_gap``/``bbox_gap``/``mask_reverse``/``roi``
    옵션·``class_id`` 규칙·저장 방식은 ``README.md``. 결과가 비면 빈 dict("스킵").
    """

    min_area:     Annotated[int,  UI(label="최소 객체 면적 (px²)", min=0, max=100000)] = 200
    mask_reverse: Annotated[bool, UI(label="mask 반전 (배경→전경)")]                   = False
    merge_gap:    Annotated[int,  UI(label="bbox 중심 병합 거리 (px, 0=끄기)",
                                     tip="bbox 중심점 거리가 이 값 이하면 한 객체로 묶음", min=0, max=999)] = 0
    bbox_gap:     Annotated[float, UI(label="bbox 확대/축소 비율 (-1~1)",
                                      tip="원본 대비 (0.1=10% 확대, -0.1=축소)",
                                      min=-1.0, max=1.0, step=0.05)]                  = 0.0

    def _scale_bbox(self, x0: float, y0: float, x1: float, y1: float,
                    w: int, h: int) -> list[float]:
        """bbox 를 ``bbox_gap`` 비율로 확대/축소하고 이미지 범위 ``[0,w]×[0,h]`` 로 클램프한다."""
        if self.bbox_gap:
            _dx = (x1 - x0) * self.bbox_gap / 2.0
            _dy = (y1 - y0) * self.bbox_gap / 2.0
            x0, x1 = x0 - _dx, x1 + _dx
            y0, y1 = y0 - _dy, y1 + _dy
        return [float(min(max(x0, 0.0), w)), float(min(max(y0, 0.0), h)),
                float(min(max(x1, 0.0), w)), float(min(max(y1, 0.0), h))]

    @staticmethod
    def _center_dist(a: list[int], b: list[int]) -> float:
        """두 bbox(XYXY) 중심점 사이 유클리드 거리."""
        _ax, _ay = (a[0] + a[2]) / 2.0, (a[1] + a[3]) / 2.0
        _bx, _by = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
        return ((_ax - _bx) ** 2 + (_ay - _by) ** 2) ** 0.5

    @classmethod
    def _cluster_bbox(cls, boxes: list[list[int]], gap: int) -> list[list[int]]:
        """bbox 중심점 거리 <= gap 인 것끼리 union-find 로 묶어 인덱스 그룹 리스트를 만든다."""
        _parent = list(range(len(boxes)))

        def _find(_x: int) -> int:
            while _parent[_x] != _x:
                _parent[_x] = _parent[_parent[_x]]
                _x = _parent[_x]
            return _x

        if gap > 0:
            for _i in range(len(boxes)):
                for _j in range(_i + 1, len(boxes)):
                    if cls._center_dist(boxes[_i], boxes[_j]) <= gap:
                        _parent[_find(_i)] = _find(_j)

        _groups: dict[int, list[int]] = {}
        for _i in range(len(boxes)):
            _groups.setdefault(_find(_i), []).append(_i)
        return list(_groups.values())

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

        _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(
            _bin.astype(np.uint8), connectivity=8)
        _ih, _iw = _lbl.shape[:2]               # 이미지 크기 (bbox 클램프용)

        # 면적 통과한 컴포넌트 — (label, bbox[XYXY])
        _comps: list[tuple[int, list[int]]] = []
        for _i in range(1, _n):  # 0 = 배경 라벨
            if int(_stats[_i, cv2.CC_STAT_AREA]) < self.min_area:
                continue
            _x = int(_stats[_i, cv2.CC_STAT_LEFT])
            _y = int(_stats[_i, cv2.CC_STAT_TOP])
            _w = int(_stats[_i, cv2.CC_STAT_WIDTH])
            _h = int(_stats[_i, cv2.CC_STAT_HEIGHT])
            _comps.append((_i, [_x, _y, _x + _w, _y + _h]))

        if not _comps:
            return {}

        # bbox 거리 <= merge_gap 인 컴포넌트끼리 한 객체로 묶음 (segment 조각은 그대로, id 공유)
        _clusters = self._cluster_bbox([_b for _, _b in _comps], self.merge_gap)

        _seg  = np.zeros(_lbl.shape, dtype=np.uint8)    # 인스턴스 라벨맵 (0 = 배경)
        _objs: list[Data_Ref] = []                      # obj_id = 리스트 순번(_route 의 info key)
        for _grp in _clusters:
            _oid     = len(_objs)
            _labels  = [_comps[_j][0] for _j in _grp]
            _seg[np.isin(_lbl, _labels)] = np.uint8(_oid + 1)   # 묶인 조각 모두 같은 id
            _boxes   = [_comps[_j][1] for _j in _grp]
            _x0 = min(_b[0] for _b in _boxes); _y0 = min(_b[1] for _b in _boxes)
            _x1 = max(_b[2] for _b in _boxes); _y1 = max(_b[3] for _b in _boxes)   # 합집합 bbox
            _objs.append(Data_Ref(type="stem", info={
                "class_id": Data_Ref(type="attr", info={"value": _cls}),
                "bbox":     Data_Ref(type="attr", format="xyxy",
                                     info={"value": self._scale_bbox(
                                         _x0, _y0, _x1, _y1, _iw, _ih)}),
            }))

        return {"segment": _seg, "object": _objs}
