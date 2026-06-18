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
    """process 추상 베이스 — 2채널 블랙보드 계약.

    파이프라인은 두 개의 dict 채널로 흐른다:
      - context: 데이터 산출물(frames, 프레임별 결과 리스트 등). 프로세스마다 갱신.
      - share:   실행 내내 유지되는 공유 상수(save_root, bg_roi, bg_stats 등).
                 주입 1회 후 모든 프레임/batch 에 동일하게 전달.

    계층별 시그니처:
      - sequence-level process (TOP_LEVEL=True; frame_batch / aggregate_hs / share):
            Run(share, **context) -> (context_out, share_out)
        Session 이 context/share 두 채널을 각각 update 한다.
      - frame process (inner; TOP_LEVEL=False):
            Run(meta, **kwargs) -> dict
        sequence process 가 프레임마다 매핑한다. share 값은 kwargs 로 투명 전달.

    연결은 강제하지 않고 key 일치로 이뤄진다(경량 블랙보드). GUI 는 아래 ClassVar 로
    배선을 표시한다.

    Attributes:
        name:      출력 결과 key 기본값으로 사용되는 식별자.
        TOP_LEVEL: 시퀀스 최상위 process 여부(=2채널 튜플 반환). False 면 inner frame process.
        INPUTS/OUTPUTS:   context 채널에서 소비/생산하는 key (GUI 표시용).
        SHARE_IN/SHARE_OUT: share 채널에서 소비/생산하는 key (GUI 표시용).
    """

    name: str = ""
    TOP_LEVEL: ClassVar[bool]            = False
    INPUTS:    ClassVar[tuple[str, ...]] = ()
    OUTPUTS:   ClassVar[tuple[str, ...]] = ()
    SHARE_IN:  ClassVar[tuple[str, ...]] = ()
    SHARE_OUT: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def Run(self, *arg, **kwarg: Any) -> Any: ...
