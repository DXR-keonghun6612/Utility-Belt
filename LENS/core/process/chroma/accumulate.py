from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ._space import Get_space, DEFAULT_SPACE
from ..utils.mask import Roi_to_mask
from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, GRAY_IMAGE, BBOX


@PROCESS_REGISTRY.Register_module()
@dataclass
class Accumulate_Chroma_histogram(Base_Process, outputs=("c0_acc", "c1_acc"), category="색공간/누산"):
    """크로마 2채널을 누산 히스토그램(``c0_acc``/``c1_acc``)에 더해 갱신본을 낸다 (순수 reducer).

    누산기를 입력으로 받아 출력 → flow 의 ``carry`` 로 cross-frame 누산(첫 프레임 ``None``→생성).
    ``per_pixel`` 로 전역(1-D)/픽셀별(``(H,W,B)``) 선택, ``roi`` 픽셀만 누산. 배경은 ``README.md``.
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

        _b0, _b1 = self.space.bins
        _c0 = np.clip(chroma_image[..., 0], 0, _b0 - 1).astype(np.int32)
        _c1 = np.clip(chroma_image[..., 1], 0, _b1 - 1).astype(np.int32)
        _sel = Roi_to_mask(roi, _c0.shape)

        if self.per_pixel:
            if c0_acc is None:
                _H, _W = _c0.shape
                c0_acc = np.zeros((_H, _W, _b0), dtype=np.uint16)
                c1_acc = np.zeros((_H, _W, _b1), dtype=np.uint16)
            # 픽셀별: 각 (y,x)는 마지막 축의 자기 bin 하나만 증가 → take/put_along_axis로 처리.
            # 인덱스 그리드(yy/xx) 캐시가 불필요해 process 무상태 + 프레임당 그리드 할당도 없다.
            _i0, _i1 = _c0[..., None], _c1[..., None]
            _inc0 = np.uint16(1) if _sel is None else _sel[..., None].astype(np.uint16)
            np.put_along_axis(c0_acc, _i0, np.take_along_axis(c0_acc, _i0, -1) + _inc0, axis=-1)
            np.put_along_axis(c1_acc, _i1, np.take_along_axis(c1_acc, _i1, -1) + _inc0, axis=-1)
        else:
            if c0_acc is None:
                c0_acc = np.zeros(_b0, dtype=np.float64)
                c1_acc = np.zeros(_b1, dtype=np.float64)
            if _sel is not None:
                _c0, _c1 = _c0[_sel], _c1[_sel]
            c0_acc += np.bincount(_c0.ravel(), minlength=_b0)[:_b0]
            c1_acc += np.bincount(_c1.ravel(), minlength=_b1)[:_b1]

        return {"c0_acc": c0_acc, "c1_acc": c1_acc}
