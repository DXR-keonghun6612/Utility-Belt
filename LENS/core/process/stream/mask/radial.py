"""반경 두께 측정 — 외곽/내곽 반경으로 hollowness 를 낸다 (중심 구멍 유무 구분).

``Center_distance`` 와 같은 **측정→attr** 유닛(측정은 정본/Run, 거르기는 ``Attr_gate`` 가 Sample 에서).
계산·근거는 :func:`func.mask.polar.Hollowness`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from ...func.mask.polar import Hollowness
from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Radial_thickness(Base_Process, outputs=("hollowness",), category="마스크/형상"):
    """hollowness(중심 구멍 비율)를 ``hollowness`` attr 로 낸다 — ``func.mask.polar.Hollowness``.

    mask 가 없거나 비면 스킵(``{}``). ``resolution`` 은 θ bin 수(각도 해상도).
    """

    resolution: Annotated[int, UI(label="θ bin 수 (각도 해상도)", min=16, max=1024)] = 256

    def Run(self, mask: GRAY_IMAGE | None = None, **kwargs) -> dict:
        if mask is None:
            return {}
        _hollow = Hollowness(mask, self.resolution)
        return {"hollowness": _hollow} if _hollow is not None else {}
