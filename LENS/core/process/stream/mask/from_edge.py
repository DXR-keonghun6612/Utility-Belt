"""edge 를 입력으로 받아 **mask 를 만드는/고치는** 연산 (연산 도메인 = mask).

입력이 edge 일 뿐 산출·변형 대상은 mask 다 — ``fill/blob`` 은 edge 윤곽을 채워 mask 를 만들고,
``remove_edge_holes`` 는 edge 를 장벽으로 mask 를 깎는다. edge 자체를 만드는 필터(canny·close)는
``stream/filter``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE
from ....func.cv.filter import Fill_contours
from ....func.mask.enclosure import Carve_enclosed


@PROCESS_REGISTRY.Register_module()
@dataclass
class Fill_edge(Base_Process, outputs=("mask",), category="마스크/엣지채움"):
    """닫힌 edge 윤곽(``RETR_EXTERNAL``) 내부를 채워 객체 raw mask 를 만든다.

    채움·``border_gap`` 의 원리는 ``func.cv.filter.Fill_contours``. 결과가 비면 빈 dict("스킵").
    """

    min_area:   Annotated[int, UI(label="최소 윤곽 면적 (px², 0=끄기)", min=0, max=100000)] = 0
    border_gap: Annotated[int, UI(label="경계 틈 잇기 (px, 0=끄기)",
                                  tip="경계에 잘린 객체 edge 를 이 폭 이하로 이어 닫음", min=0, max=199)] = 0

    def Run(self, edge: GRAY_IMAGE, **kwargs) -> dict:
        _out = Fill_contours(edge, min_area=self.min_area, border_gap=self.border_gap)
        if not _out.any():
            return {}
        return {"mask": _out}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Edge_blob(Base_Process, outputs=("blob",), category="마스크/엣지채움"):
    """edge 윤곽을 채워 **제외용 blob** 을 별도 port(``blob``)로 낸다 (``min_area``/``max_area`` 로 크기 범위).

    ``fill_edge`` 와 같은 채움(``func.cv.filter.Fill_contours``)이되 결과를 객체 mask 가 아니라 뺄 영역으로
    본다. 크기 범위로 고른 blob 을 ``combine_mask``(subtract)에 이어 mask 에서 떼어낸다 — port 이름이
    달라 같은 체인에서 ``fill_edge`` 와 충돌하지 않는다. 결과가 비면 빈 dict("스킵").
    """

    min_area:   Annotated[int, UI(label="최소 blob 면적 (px², 0=하한없음)", min=0, max=1000000)] = 500
    max_area:   Annotated[int, UI(label="최대 blob 면적 (px², 0=상한없음)", min=0, max=1000000)] = 0
    border_gap: Annotated[int, UI(label="경계 틈 잇기 (px, 0=끄기)",
                                  tip="경계에 잘린 윤곽을 이 폭 이하로 이어 닫음", min=0, max=199)] = 0

    def Run(self, edge: GRAY_IMAGE, **kwargs) -> dict:
        _blob = Fill_contours(edge, min_area=self.min_area,
                              max_area=self.max_area or None, border_gap=self.border_gap)
        if not _blob.any():
            return {}
        return {"blob": _blob}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Remove_edge_holes(Base_Process, outputs=("mask",), category="마스크/구멍"):
    """SAM 등이 메운 ``mask`` 에서 **edge 로 갇힌 구멍·슬릿**을 다시 뚫는다 (경계-재건 방식).

    알고리즘·인자 의미는 ``func.mask.enclosure.Carve_enclosed``. 결과가 비면 빈 dict("스킵").
    """

    boundary_margin: Annotated[int, UI(label="외곽 제외 침식 (px)", min=0, max=50)]        = 3
    close_size:      Annotated[int, UI(label="edge 틈 잇기 CLOSE (px)", min=1, max=21)]     = 5
    min_area:        Annotated[int, UI(label="최소 구멍 면적 (px², 0=끄기)", min=0, max=100000)] = 80

    def Run(self, mask: GRAY_IMAGE, edge: GRAY_IMAGE, **kwargs) -> dict:
        _out = Carve_enclosed(mask, edge, boundary_margin=self.boundary_margin,
                              close_size=self.close_size, min_area=self.min_area)
        return {"mask": _out} if _out is not None else {}
