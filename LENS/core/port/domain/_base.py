"""도메인 계약 — **무엇을 담는 데이터인가** (I/O 는 안 한다).

읽기/쓰기는 포맷이 든다([`../codec`](../codec)) — 도메인이 드는 건 그 위의 **정책**이다:

- ``FORMATS``      — 이 도메인에 **유효한 포맷 집합**. 벗어나면 조용히 넘기지 않고 실패한다.
- ``Canonicalize`` — 포맷이 실어 온 값을 이 도메인의 **정준형**으로 (예: segmap = 단일채널 uint8 라벨맵).
  같은 png 라도 사진이면 그대로, 라벨맵이면 단일채널로 — 그 차이가 **도메인 의미**라 여기 산다.
- ``Claims``       — spec 이 도메인을 안 줄 때 값+맥락으로 자기가 담당하는지 (우선순위; 0 = 미매칭).
- ``Blank``        — "빈 것"의 표현 (gui 가 빈 캔버스로 나서 그리기 시작하는 자리).

도메인은 **상태가 없다**(classmethod). 새 도메인(3D points 등)은 파일 하나로 붙고, 그 도메인이 쓰는 포맷
codec 이 이미 있으면(npy 등) I/O 는 재사용된다 — 그게 이 분리의 요점이다.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar


class Domain(ABC):
    """데이터 도메인 하나 — 유효 포맷 + 정준형 + 정책 (상태 없음)."""

    #: 이 도메인에 유효한 포맷 이름들 (``format[1]``). 첫 항목이 기본 포맷.
    FORMATS: ClassVar[tuple[str, ...]] = ()

    #: 확장자로 이 도메인을 **추론해도 되는가** — 같은 확장자를 여러 도메인이 쓰면(png = 사진/마스크/
    #: 라벨맵) 추론이 곧 조용한 선택이라, 애매한 쪽은 False 로 두고 ``type`` 명시를 요구한다.
    INFERABLE: ClassVar[bool] = False

    @classmethod
    def Default_format(cls) -> str:
        """포맷 미지정 시 기본 — ``FORMATS`` 의 첫 항목."""
        return cls.FORMATS[0] if cls.FORMATS else ""

    @classmethod
    def Validate(cls, fmt: str, *, name: str) -> None:
        """이 포맷이 도메인에 유효한지 — 아니면 **실패**(조용한 fallback 없음).

        Raises:
            ValueError: 이 도메인이 안 쓰는 포맷일 때.
        """
        if fmt not in cls.FORMATS:
            raise ValueError(
                f"도메인 '{name}' 에 포맷 '{fmt}' 는 유효하지 않다 "
                f"(가능: {', '.join(cls.FORMATS) or '없음'})")

    @classmethod
    def Canonicalize(cls, value: Any) -> Any:
        """포맷이 실어 온 값 → 이 도메인의 정준형 (기본은 그대로)."""
        return value

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """spec 이 도메인을 안 줄 때, 이 value+맥락을 담당하는 우선순위 (0 = 미매칭).

        ``storage`` = 파일 요청(``to: storage``), ``params`` = 위치 없는 dataset-wide 출력. 같은 ndarray
        라도 맥락으로 mask(인라인)/image(파일)/array(params)를 가른다.
        """
        return 0

    @classmethod
    def Can_visualize(cls) -> bool:
        """이미지로 시각화 가능한지 (GUI 데이터 트리·오버레이용)."""
        return False

    @classmethod
    def Blank(cls, *, size: tuple[int, int] | None = None) -> Any:
        """이 도메인의 **빈 payload** — 곧바로 편집(그리기)을 시작할 수 있는 영값.

        Raises:
            NotImplementedError: 이 도메인이 빈 객체 생성을 지원하지 않을 때 (조용한 기본값 없음).
        """
        raise NotImplementedError(f"{cls.__name__} 은 빈 객체 생성을 지원하지 않습니다")
