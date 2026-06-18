"""프레임 파일 목록에서 H·S 픽셀을 누적해 세션 배경 통계를 산출하는 batch process."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from ... import config_registry
from .. import pipeline_registry
from ...dataloader._base import CATEGORIZE_FILE_LIST
from ..frame.extract_hs import Extract_hs_process, Extract_hs_config
from ..frame.load_frame import Load_frame_process
from ..utils.color import HS_stats
from .frame_batch import Frame_batch_process


NAME = "aggregate_hs"


# ── Config ────────────────────────────────────────────────────────────────────

@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Aggregate_hs_config(Extract_hs_config):
    """H·S 누적 통계 파라미터.

    Attributes:
        threshold: 프레임별 inlier 판정 HS 거리 임계값.
        min_pixels: 프레임별 유효 inlier 픽셀 최솟값.
        sigma_floor: std 하한. 색상 변동이 적은 세션의 과적합 방지.
    """

    config_type: str = f"{NAME}_config"
    object_type: str = NAME

    sigma_floor: float = field(default=1.0, metadata={"ui": {
        "label": "sigma 하한",
        "tip": "추정된 std가 이 값보다 작으면 하한으로 클리핑",
        "min": 0.1, "max": 5.0, "step": 0.1,
    }})


# ── Process ───────────────────────────────────────────────────────────────────

@pipeline_registry.Register_module(NAME)
@dataclass
class Aggregate_hs_process(Frame_batch_process):
    """Frame_batch_process 의 특수 구현 — H·S 픽셀 누적 통계 산출.

    inner processes: [load_frame → extract_hs]
    super().Run() 이 프레임별 h/s 배열을 수집하고, Run 에서 집계한다.
    is_flatten=True 로 class_name 없이 프레임을 평탄화해 순회한다.
    이미지는 extract_hs 단계로 _prev 가 교체되는 순간 자연 해제된다.
    """

    name:        str   = NAME
    is_flatten:  bool  = True
    threshold:   float = 2.0
    min_pixels:  int   = 100
    sigma_floor: float = 1.0

    # bg_roi(배경 ROI)는 선택적 SHARE_IN — Frame_Meta(data_path["bg_roi"]) 파일이 있으면
    # load_frame 이 프레임별로 로드하고, 고정 시점이면 share 로 1회 주입해 대체한다.
    # bg_stats 는 전 프레임 공통 상수라 share 로 내보낸다.
    INPUTS:    ClassVar[tuple[str, ...]] = ("frames",)
    OUTPUTS:   ClassVar[tuple[str, ...]] = ()
    SHARE_IN:  ClassVar[tuple[str, ...]] = ("bg_roi",)
    SHARE_OUT: ClassVar[tuple[str, ...]] = ("bg_stats",)

    def __post_init__(self) -> None:
        super().__post_init__()
        self._inners = [
            Load_frame_process(),
            Extract_hs_process(threshold=self.threshold, min_pixels=self.min_pixels),
        ]

    def Run(
        self, share: dict, frames: CATEGORIZE_FILE_LIST, **context
    ) -> tuple[dict, dict]:
        """전 프레임 H·S 픽셀을 누적해 세션 배경 통계를 산출한다.

        inner [load_frame → extract_hs] 가 프레임별 h/s 배열을 만들고, 여기서 concat 해
        단일 HS_stats 로 집계한다. 배경 ROI 는 선택적이다 — Frame_Meta 에 bg_roi 파일이
        있으면 프레임마다 load_frame 이 로드해 쓰고, 고정 시점이면 share 의 bg_roi 가
        모든 프레임을 덮어쓴다. 둘 다 없으면 extract_hs 가 빈 결과를 내 해당 프레임은
        집계에서 제외된다.

        Args:
            share:  실행 공유 상수. bg_roi 가 주입돼 있으면 전 프레임 공통 적용.
            frames: dataloader 가 만든 CATEGORIZE_FILE_LIST.
            **context: 잔여 context(미사용).

        Returns:
            (context_out, share_out). context 는 비우고, share_out 에 bg_stats 를 싣는다.
        """
        _ctx_out, _ = super().Run(share=share, frames=frames)

        _h_list = [a for a in _ctx_out.get("h", []) if a is not None]
        _s_list = [a for a in _ctx_out.get("s", []) if a is not None]
        if not _h_list:
            return {}, {}

        _h = np.concatenate(_h_list)
        _s = np.concatenate(_s_list)

        return {}, {"bg_stats": HS_stats(
            mean_h = float(_h.mean()),
            mean_s = float(_s.mean()),
            std_h  = max(float(_h.std()), self.sigma_floor),
            std_s  = max(float(_s.std()), self.sigma_floor),
        )}
