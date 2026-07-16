from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ....func.chroma._core import Accumulate_histogram
from ....func.chroma._space import Get_space, DEFAULT_SPACE
from ....func.cv.geom import Roi_to_mask
from .. import PROCESS_REGISTRY, Base_Process, UI, GRAY_IMAGE, BBOX


@PROCESS_REGISTRY.Register_module()
@dataclass
class Accumulate_Chroma_histogram(Base_Process, outputs=("c0_acc", "c1_acc"), category="색공간/누산"):
    """크로마 2채널을 누산 히스토그램(``c0_acc``/``c1_acc``)에 더해 갱신본을 낸다 (순수 reducer).

    누산은 ``func.chroma._core.Accumulate_histogram``. 누산기를 입력으로 받아 출력하므로 flow 의
    ``carry`` 가 cross-frame 누산을 만든다. ``chroma_image`` 가 없으면 이 프레임 스킵(누산기는 carry 로 유지).
    """

    space:     Annotated[str,  UI(label="색공간", tip="hsv / lab")] = DEFAULT_SPACE
    per_pixel: Annotated[bool, UI(label="픽셀별 누산")]              = False

    def __post_init__(self) -> None:
        self.space = Get_space(self.space)   # str → ChromaSpace (작업 state 없음 → stateless)

    def Run(
        self, chroma_image: np.ndarray | None = None,
        c0_acc: np.ndarray | None = None, c1_acc: np.ndarray | None = None,
        roi: BBOX | GRAY_IMAGE | None = None, **kwargs,
    ) -> dict:
        if chroma_image is None:
            return {}  # 크로마 이미지 없음 → 이 프레임 스킵 (누산기는 carry로 유지됨)

        _c0_acc, _c1_acc = Accumulate_histogram(
            chroma_image, self.space, c0_acc=c0_acc, c1_acc=c1_acc,
            per_pixel=self.per_pixel, selection=Roi_to_mask(roi, chroma_image.shape[:2]))
        return {"c0_acc": _c0_acc, "c1_acc": _c1_acc}
