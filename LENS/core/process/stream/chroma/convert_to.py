from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ...func.chroma._core import To_chroma
from ...func.chroma._space import Get_space, DEFAULT_SPACE
from .. import PROCESS_REGISTRY, Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Convert_to_Chroma(Base_Process, outputs=("chroma_image",), category="색공간/변환"):
    """프레임을 ``space`` 로 옮겨 2채널 크로마 ``(H, W, 2)`` 를 뽑는다 — ``func.chroma._core.To_chroma``.

    hsv=H·S / lab=a*·b*. 색공간 의존값은 ``_space.ChromaSpace`` 가 소유.
    """

    space: Annotated[str, UI(label="색공간", tip="hsv=H·S / lab=a*·b*")] = DEFAULT_SPACE

    def __post_init__(self) -> None:
        self.space = Get_space(self.space)   # str → ChromaSpace (1회 정규화)

    def Run(self, frame: np.ndarray, **kwargs) -> dict:
        return {"chroma_image": To_chroma(frame, self.space)}
