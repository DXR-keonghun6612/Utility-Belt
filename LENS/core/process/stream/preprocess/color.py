from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from ...func.cv.color import (Clahe, Equalize_histogram, Flatten_brightness,
                              Stretch_contrast)
from .. import PROCESS_REGISTRY, Base_Process, UI, IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Normalize_color(Base_Process, outputs=("norm_image",), category="전처리/색보정"):
    """조명 정규화 — 명도를 상수로 덮어 밝기 경계를 지운다(``func.cv.color.Flatten_brightness``).

    색 경계만 남으므로 뒤따르는 ``detect_edge`` 의 입력(``norm_image``)이 된다.
    """

    value: Annotated[int, UI(label="고정 명도 (V)", min=1, max=255,
                             tip="HSV V 채널을 이 값으로 덮어 밝기 변화를 제거")] = 255

    def Run(self, frame: np.ndarray, **kwargs) -> dict:
        return {"norm_image": Flatten_brightness(frame, self.value)}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Normalize_histogram(Base_Process, outputs=("norm_frame",), category="전처리/히스토그램"):
    """BGR 각 채널을 독립적으로 히스토그램 정규화한다 — ``method`` 로 네 방식 중 선택.

    계산은 ``func.cv.color`` 의 채널별 primitive — 입력은 **채널 무관 ``IMAGE``** 라 gray·3ch·4ch 를
    한 유닛이 받고, 채널 수는 primitive 가 런타임에 구분한다(4ch 는 alpha 보존). 원본 ``frame`` 을
    덮지 않도록 결과는 별도 port ``norm_frame`` 으로 낸다(저장 폴더 = leaf 이름이라, ``frame`` 이면
    원본 payload 를 덮어쓴다. 다른 폴더에 남기려면 라우팅 spec 의 ``as`` 로 leaf 별칭을 준다).

    - **minmax** — 각 채널 min–max → ``[0,255]`` 선형 스트레칭 (``Stretch_contrast`` 0/100).
    - **percentile** — ``low``/``high`` 백분위로 clip 후 스트레칭 (이상치 강건).
    - **equalize** — 채널별 ``cv2.equalizeHist`` (CDF 균등화, 비선형).
    - **clahe** — 타일 단위 대비제한 적응 평활화 (``clip_limit``/``tile``).
    """

    method: Annotated[str, UI(label="정규화 방식",
                             tip="minmax / percentile / equalize / clahe")] = "clahe"
    low:    Annotated[float, UI(label="하단 백분위 (percentile)", min=0.0, max=49.0, step=0.5,
                               tip="percentile 방식에서 하단 clip 백분위")]      = 1.0
    high:   Annotated[float, UI(label="상단 백분위 (percentile)", min=51.0, max=100.0, step=0.5,
                               tip="percentile 방식에서 상단 clip 백분위")]      = 99.0
    clip_limit: Annotated[float, UI(label="CLAHE 대비 제한", min=0.5, max=8.0, step=0.5)] = 2.0
    tile:       Annotated[int,   UI(label="CLAHE 타일 격자 (n×n)", min=1, max=32)]        = 8

    def Run(self, frame: IMAGE, **kwargs) -> dict:
        if self.method == "minmax":
            _out = Stretch_contrast(frame)
        elif self.method == "percentile":
            _out = Stretch_contrast(frame, self.low, self.high)
        elif self.method == "equalize":
            _out = Equalize_histogram(frame)
        elif self.method == "clahe":
            _out = Clahe(frame, self.clip_limit, self.tile)
        else:                                           # 조용한 fallback 금지 — 오타를 드러낸다
            raise ValueError(
                f"알 수 없는 method {self.method!r} (minmax/percentile/equalize/clahe)")
        return {"norm_frame": _out}
