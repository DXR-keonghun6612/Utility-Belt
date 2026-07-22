"""도메인 계약 — **무엇을 담는 데이터인가** (I/O 는 안 한다).

읽기/쓰기는 포맷이 든다([`../codec`](../codec)) — 도메인이 드는 건 그 위의 **정책**이다:

- ``FORMATS``   — 이 도메인에 **유효한 포맷 집합**. 벗어나면 조용히 넘기지 않고 실패한다.
- ``Normalize`` — 실어 온 값의 **의미 보정** (예: mask 는 3채널 png 로 저장돼 있어도 단일채널이 뜻).
  같은 png 라도 사진이면 그대로, 마스크면 단일채널로 — 그 차이가 도메인 의미라 여기 산다.
  **구조를 바꾸지 않는다** — 폴리곤 dict 는 그대로 통과한다(배열로 뭉개지 않는다).
- ``To``        — 값을 이 도메인의 **어떤 포맷 구조로** (저장할 때). 시작점이 여럿이고 도착지가 하나라
  도착지가 든다. 단 **고르는 것**만 여기고 계산은 [`../../format`](../../format) 이 든다.
- ``Claims``    — spec 이 도메인을 안 줄 때 값+맥락으로 자기가 담당하는지 (우선순위; 0 = 미매칭).
- ``Blank``     — "빈 것"의 표현 (gui 가 빈 캔버스로 나서 그리기 시작하는 자리).

**대표 포맷(정준형)은 없다.** 한때 도메인마다 포맷 하나를 대표로 정해 ``Load`` 가 전부 그리로 뭉갰다 —
그래서 ``(mask, polygon)`` 을 읽으면 배열이 나왔고, 폴리곤은 자기 구조를 지킬 수가 없었다. 이제 각 포맷은
자기 구조로 살고, 도메인은 **필요할 때 골라서** 변환한다.

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
    def Normalize(cls, value: Any) -> Any:
        """실어 온 값의 **의미 보정** — 구조는 그대로 두고 뜻만 맞춘다 (기본: 무보정).

        포맷 변환이 아니다 — 그건 `To` 다. 여기가 하는 건 "이 도메인에서 이 구조는 이런 모양이어야
        한다"뿐이다(3채널 png 로 저장된 라벨맵 → 단일채널).
        """
        return value

    @classmethod
    def To(cls, value: Any, fmt: str) -> Any:
        """값을 이 도메인의 ``fmt`` 구조로 (기본: 의미 보정만 — 포맷이 하나뿐인 도메인).

        **시작점이 여럿이고 도착지가 하나라 도착지가 든다** — 같은 mask 를 배열로도 폴리곤 dict 로도
        받지만, 그것이 다 "그 객체가 덮는 픽셀"이라는 걸 아는 건 도메인뿐이다. 단 **고르는 것**만
        여기고(채울까 그을까) 계산은 [`../../format`](../../format) 이 든다.

        Args:
            value: 생산자가 낸 값 — 배열일 수도, 이미 그 포맷의 구조일 수도 있다.
            fmt: 담을 포맷 (``FORMATS`` 중 하나 — 호출 측이 `Validate` 를 이미 했다).
        """
        return cls.Normalize(value)

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
