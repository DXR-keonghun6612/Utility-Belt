from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE
from ....func.cv.filter import Close_gaps


@PROCESS_REGISTRY.Register_module()
@dataclass
class Close_edge(Base_Process, outputs=("edge",), category="필터/기본"):
    """끊긴 edge 를 morphology CLOSE 로 이어 닫는다 — ``func.cv.filter.Close_gaps``.

    ``size`` px 이하 틈을 메운다. 결과가 비면 빈 dict("스킵").
    """

    size: Annotated[int, UI(label="CLOSE 커널 크기 (px)", min=1, max=21,
                            tip="이 값 이하의 edge 틈을 메움")] = 5

    def Run(self, edge: GRAY_IMAGE, **kwargs) -> dict:
        _e = Close_gaps(edge, self.size)
        return {"edge": _e} if _e.any() else {}
