"""segmap 핸들러 — 단일채널 정수 클래스 ID 라벨맵 (png 파일).

``image`` 의 **특화**다 — png I/O(cv2 로드/저장·None 체크)는 ``Image_Handler`` 를 상속해
그대로 쓰고, 의미 차이(픽셀값이 색이 아니라 클래스 ID 인 단일채널 (H,W) 라벨맵)만 변주한다:
Load 는 항상 uint8 (H,W) 로 디코드(다채널이면 첫 채널)해 process 가 마스크로 다루고
(``rle`` 과 동형 payload), Save 도 단일채널·uint8 로 정돈해 쓴다.

확장자 ``png`` 는 ``image`` 가 이미 점유하므로 **추론용 ``Extensions`` 를 비운다** — 같은 png
라도 색 이미지인지 라벨맵인지 추론 불가하니 ``type: segmap`` 으로 명시해야 한다. 대신
``File_Handler`` 가 ``Extensions()[0]`` 으로 파생하던 기본 format 을 ``png`` 로 직접 지정한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from . import HANDLER_REGISTRY
from .image import Image_Handler


@HANDLER_REGISTRY.Register_module("segmap")
class Segmap_Handler(Image_Handler):

    @classmethod
    def _Read(cls, path: Path) -> Any:
        _img = super()._Read(path)          # cv2 로드 + None 체크 재사용
        if _img.ndim == 3:                  # 다채널로 저장됐으면 첫 채널만 (라벨은 단일채널)
            _img = _img[..., 0]
        return _img.astype(np.uint8)

    @classmethod
    def _Write(cls, data: Any, path: Path) -> None:
        _map = np.asarray(data).astype(np.uint8)
        if _map.ndim == 3:                  # 단일채널 보장
            _map = _map[..., 0]
        super()._Write(_map, path)          # cv2 저장 + 실패 체크 재사용

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        return 0                            # png·ndarray 는 image 와 구분 불가 → 항상 type 명시(상속 override)

    @classmethod
    def Extensions(cls) -> tuple[str, ...]:
        return ()                           # png 는 image 가 점유 → 추론 안 함(type 명시 필요)

    @classmethod
    def Default_format(cls) -> str:
        return "png"                        # Extensions 비어 파생 불가 → 직접 지정
