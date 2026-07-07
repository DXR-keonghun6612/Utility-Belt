from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from ._space import Get_space, DEFAULT_SPACE
from ._core import Channel_delta
from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Chroma_distance(Base_Process, outputs=("dist",), category="색공간/거리"):
    """배경 크로마 모델(params 4키) 대비 정규화 편차 맵 ``dist`` 를 만든다 (색공간 무관).

    ``d = √((Δc0/σ0)² + (Δc1/σ1)²)``. 모델이 스칼라(전역)/``(H,W)``(픽셀별)든 브로드캐스팅으로 공용.
    순환 채널 wrap 보정·``sigma_floor``·용례는 ``README.md``. 모델 없으면 빈 dict("스킵").
    """

    space:       Annotated[str,   UI(label="색공간", tip="hsv / lab")]                       = DEFAULT_SPACE
    sigma_floor: Annotated[float, UI(label="σ 하한 (잡음 억제)", min=0.1, max=20.0, step=0.1)] = 1.0

    def __post_init__(self) -> None:
        self.space = Get_space(self.space)   # str → ChromaSpace

    def Run(
        self, frame: np.ndarray,
        mean_c0=None, mean_c1=None, std_c0=None, std_c1=None, **kwargs
    ) -> dict:
        if mean_c0 is None or mean_c1 is None or std_c0 is None or std_c1 is None:
            return {}  # 배경 모델 미생성 (robust_chroma_stats flow 먼저 실행 필요)

        _m0 = np.asarray(mean_c0, np.float32)
        _m1 = np.asarray(mean_c1, np.float32)
        _s0 = np.maximum(np.asarray(std_c0, np.float32), self.sigma_floor)
        _s1 = np.maximum(np.asarray(std_c1, np.float32), self.sigma_floor)
        # 픽셀별(배열) 모델이면 프레임과 크기가 같아야 한다 (정적 카메라 가정)
        for _a in (_m0, _m1, _s0, _s1):
            if _a.ndim and _a.shape != frame.shape[:2]:
                return {}

        _ch0, _ch1 = self.space.channels
        _b0, _b1   = self.space.bins
        _cir0, _cir1 = self.space.circular
        _img = cv2.cvtColor(frame, self.space.cvt_code).astype(np.float32)
        _c0, _c1 = _img[..., _ch0], _img[..., _ch1]

        _d0 = Channel_delta(_c0, _m0, _cir0, _b0)
        _d1 = Channel_delta(_c1, _m1, _cir1, _b1)
        _d  = np.sqrt((_d0 / _s0) ** 2 + (_d1 / _s1) ** 2)
        return {"dist": _d.astype(np.float32)}
