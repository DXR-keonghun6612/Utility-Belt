"""Process 추상 베이스 + 공통 Config + 출력 헬퍼."""

from __future__ import annotations
from typing import Any, ClassVar

from abc import ABC, abstractmethod
from dataclasses import dataclass

from numpy import ndarray, dtype, uint8


BBOX = tuple[int, int, int, int]
GRAY_IMAGE = ndarray[tuple[int, int], dtype[uint8]]


@dataclass
class Base_Process(ABC):
    """시퀀스 단위 batch process 추상 베이스.

    시퀀스에 놓이는 process 는 group context(dict)를 받아 결과를 dict 로 반환한다.
    Session 이 context.update(result) 로 누적하므로, 다운스트림은 공통 key 로
    필요한 입력을 집어간다 (경량 블랙보드). 연결 자체는 강제하지 않고 사용자/GUI 가
    key 를 맞춘다.

    frame 단위 연산은 자체 시그니처(Run(**inputs) -> value)로 두고,
    Frame_batch_process 가 group 전체 프레임에 매핑해 batch 계약으로 끌어올린다.

    Attributes:
        name: 출력 결과 key 기본값으로 사용되는 식별자.
        OUTPUTS: Run 이 context 에 내보내는 결과 key 목록 (GUI 배선 표시용).
    """

    name: str = ""
    OUTPUTS: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def Run(self, *arg, **kwarg: Any) -> dict[str, Any]: ...
