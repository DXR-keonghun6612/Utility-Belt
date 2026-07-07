from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from ..utils.mask import Make_morph_kernel, Fill_contours
from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Close_edge(Base_Process, outputs=("edge",), category="엣지/기본"):
    """끊긴 edge 를 morphology CLOSE 로 이어 닫는다 (``size`` px 이하 틈을 메움).

    CLOSE vs OPEN 근거는 ``README.md``. 결과가 비면 빈 dict("스킵").
    """

    size: Annotated[int, UI(label="CLOSE 커널 크기 (px)", min=1, max=21,
                            tip="이 값 이하의 edge 틈을 메움")] = 5

    def Run(self, edge: GRAY_IMAGE, **kwargs) -> dict:
        _e = cv2.morphologyEx(edge, cv2.MORPH_CLOSE, Make_morph_kernel(self.size))
        if not _e.any():
            return {}
        return {"edge": _e}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Fill_edge(Base_Process, outputs=("mask",), category="엣지/기본"):
    """닫힌 edge 윤곽(``RETR_EXTERNAL``) 내부를 채워 객체 raw mask 를 만든다.

    ``min_area`` 미만 윤곽은 버리고(0=끄기), ``border_gap`` 은 경계에 잘린 객체를 이어 닫는다
    (원리는 ``README.md``). 결과가 비면 빈 dict("스킵").
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
class Edge_blob(Base_Process, outputs=("blob",), category="엣지/기본"):
    """edge 윤곽을 채워 **제외용 blob** 을 별도 port(``blob``)로 낸다 (``min_area``/``max_area`` 로 크기 범위).

    ``fill_edge`` 와 같은 채움을 다른 역할로 — ``combine_mask`` (subtract)로 mask 에서 뺀다(용례는 ``README.md``).
    결과가 비면 빈 dict("스킵").
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
class Remove_edge_holes(Base_Process, outputs=("mask",), category="엣지/구멍"):
    """SAM 등이 메운 ``mask`` 에서 **edge 로 갇힌 구멍·슬릿**을 다시 뚫는다 (경계-재건 방식).

    프레임 ``edge`` 를 mask 내부로 국한해 장벽으로 삼아 mask 를 절단하고, mask 경계 띠에 닿는
    연결성분만 부품 몸통으로 본다 — edge loop 에 갇혀 경계에서 못 닿는 영역이 구멍/슬릿이다.
    contour 채움과 달리 절단+연결성이라 얇은 슬릿에 강하고, 부품 표면·반사광 edge 는 영역을
    가두지 못해 몸통에 흡수된다(가짜 구멍 X). 완전히 갇힌 작은 반사광 blob 만 ``min_area`` 로 걸러
    되메운다. 다객체 프레임도 한 번에(각 몸통이 경계에 닿음). 결과가 비면 빈 dict("스킵").

    - **boundary_margin** — mask 를 이만큼 침식한 안쪽만 내부 edge 로 본다(외곽 실루엣 edge 제외,
      바깥 띠는 재건 seed 로 남긴다). 너무 크면 얇은 부품을 통째 seed 로 봐 구멍을 못 뚫는다.
    - **close_size** — 내부 edge 의 끊긴 틈을 이 크기로 CLOSE 해 장벽을 잇는다(슬릿 끝 닫힘).
    - **min_area** — 이보다 작은 갇힌 영역은 반사광 잡음으로 보고 되메운다(0=끄기).
    """

    boundary_margin: Annotated[int, UI(label="외곽 제외 침식 (px)", min=0, max=50)]        = 3
    close_size:      Annotated[int, UI(label="edge 틈 잇기 CLOSE (px)", min=1, max=21)]     = 5
    min_area:        Annotated[int, UI(label="최소 구멍 면적 (px², 0=끄기)", min=0, max=100000)] = 80

    def Run(self, mask: GRAY_IMAGE, edge: GRAY_IMAGE, **kwargs) -> dict:
        _m = mask > 0
        # 내부 edge 만 장벽으로 (외곽 실루엣 edge 는 침식으로 제외)
        _interior = (cv2.erode(_m.astype(np.uint8), Make_morph_kernel(self.boundary_margin)) > 0
                     if self.boundary_margin else _m)
        _barrier = cv2.morphologyEx(((edge > 0) & _interior).astype(np.uint8),
                                    cv2.MORPH_CLOSE, Make_morph_kernel(self.close_size)) > 0
        _walk = _m & ~_barrier                                 # mask 를 edge 로 절단
        _band = _m & ~_interior                                # 경계 띠(edge 없는 재건 seed)

        _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(_walk.astype(np.uint8))
        _enclosed = np.ones(_n, dtype=bool)
        _enclosed[0] = False                                   # 배경 라벨
        _band_labels = np.unique(_lbl[_band])
        _enclosed[_band_labels[_band_labels > 0]] = False      # 경계 띠에 닿는 성분 = 몸통
        if self.min_area:                                      # 작은 갇힘 = 반사광 → 되메움
            _enclosed &= _stats[:, cv2.CC_STAT_AREA] >= self.min_area

        _refined = _m & ~_enclosed[_lbl]                       # 갇힌 구멍/슬릿 제거
        if not _refined.any():
            return {}
        return {"mask": (_refined.astype(np.uint8) * 255)}
