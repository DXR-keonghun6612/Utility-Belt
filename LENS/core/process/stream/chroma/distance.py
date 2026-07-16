from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ....func.chroma._space import Get_space, DEFAULT_SPACE
from ....func.chroma._core import Distance_map
from .. import PROCESS_REGISTRY, Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Chroma_distance(Base_Process, outputs=("dist",), category="색공간/거리"):
    """배경 크로마 모델(params 4키) 대비 정규화 편차 맵 ``dist`` 를 만든다 (색공간 무관).

    계산은 ``func.chroma._core.Distance_map``. 모델 4키가 없거나(배경모델 flow 선행 필요) 픽셀별 모델
    크기가 프레임과 다르면 빈 dict("스킵").
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

        _dist = Distance_map(frame, self.space, mean=(mean_c0, mean_c1),
                             std=(std_c0, std_c1), sigma_floor=self.sigma_floor)
        return {"dist": _dist} if _dist is not None else {}
