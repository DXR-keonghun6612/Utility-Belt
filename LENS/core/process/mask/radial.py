"""반경 두께 측정 — 외곽/내곽 반경으로 hollowness 를 낸다 (중심 구멍 유무 구분).

``Center_distance`` 와 같은 **측정→attr** 유닛(측정은 정본/Run, 거르기는 ``Attr_gate`` 가 Sample 에서).
mask 를 centroid 기준 (r,θ) 로 풀어(:func:`polar.mask_to_polar`) 각 θ 의 외곽 ``r_outer``·내곽
``r_inner`` 를 얻고, 두께 ``t = r_outer - r_inner`` (외곽선에서 무게중심 쪽 재료 두께)로 hollowness 를
잰다 — 외곽 실루엣이 같아도 중심에 구멍이 있으면(링) hollowness 가 크고, 꽉 찬 형상은 0 에 가깝다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, GRAY_IMAGE
from ..utils.polar import mask_to_polar


@PROCESS_REGISTRY.Register_module()
@dataclass
class Radial_thickness(Base_Process, outputs=("hollowness",), category="마스크/형상"):
    """외곽/내곽 반경으로 hollowness(중심 구멍 비율)를 ``hollowness`` attr 로 낸다.

    ``hollowness = mean(r_inner) / mean(r_outer)`` ∈ [0, 1) — 0=꽉 참(내곽≈0), 1 에 가까울수록
    얇은 링(중심 구멍 큼). 외곽 실루엣이 같아도 구멍 유무를 이 스칼라로 구분한다. mask 가 없거나
    비면 스킵(``{}``). ``resolution`` 은 θ bin 수(각도 해상도).
    """

    resolution: Annotated[int, UI(label="θ bin 수 (각도 해상도)", min=16, max=1024)] = 256

    def Run(self, mask: GRAY_IMAGE | None = None, **kwargs) -> dict:
        if mask is None or not np.any(mask):
            return {}                                    # 위치 정보 없음 → 스킵
        _r_out, _r_in = mask_to_polar(np.asarray(mask), self.resolution)
        _mean_out = float(np.mean(_r_out))
        if _mean_out <= 0:
            return {}
        _hollow = float(np.clip(np.mean(_r_in) / _mean_out, 0.0, 1.0))
        return {"hollowness": _hollow}
