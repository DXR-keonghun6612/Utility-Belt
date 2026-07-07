from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import cv2
import numpy as np

from ._space import Get_space, DEFAULT_SPACE
from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Convert_to_Chroma(Base_Process, outputs=("chroma_image",), category="색공간/변환"):
    """프레임을 ``space`` 로 옮겨 2채널 크로마 ``(H, W, 2)`` 를 뽑는다 (명도 버림).

    hsv=H·S / lab=a*·b*. 색공간 의존값은 ``_space.ChromaSpace`` 가 소유(→ ``README.md``).
    """

    space: Annotated[str, UI(label="색공간", tip="hsv=H·S / lab=a*·b*")] = DEFAULT_SPACE

    def __post_init__(self) -> None:
        self.space = Get_space(self.space)   # str → ChromaSpace (1회 정규화)

    def Run(self, frame: np.ndarray, **kwargs) -> dict:
        _c0, _c1 = self.space.channels
        _img = cv2.cvtColor(frame, self.space.cvt_code).astype(np.float32)
        return {"chroma_image": _img[..., (_c0, _c1)]}
