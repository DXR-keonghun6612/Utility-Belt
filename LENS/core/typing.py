"""횡단 공유 타입 — 어느 단계(meta/process/sampling)에도 속하지 않고 둘 이상이 공유하는 타입 정의.

두 종류를 담는다:

- **타입 별칭** (``BBOX``·``GRAY_IMAGE``) — 여러 단계가 공유하는 도메인 타입.
- **인자 표시 메타** (``Arg_Info`` + 축약 생성자 ``Arg``) — ``__init__`` 파라미터/dataclass 필드에
  ``Annotated[type, Arg_Info(...)]`` 로 부착하는 표시 힌트. GUI(``gui/form``)가 읽어 위젯을 만든다.
  계산 계층은 이 값을 쓰지 않는다 — 순수 데이터(Qt 비의존)일 뿐이다.

값(상수)은 타입이 아니라 [`constant.py`](constant.py) 에 둔다. 이 모듈은 **primitive** 다 —
활용부(form 등)가 여기에 맞추지, 그 반대가 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any

from numpy import dtype, ndarray, uint8

# ── 타입 별칭 ──────────────────────────────────────────────────────────────────

BBOX       = tuple[int, int, int, int]
GRAY_IMAGE = ndarray[tuple[int, int], dtype[uint8]]


# ── 인자 표시 메타 ─────────────────────────────────────────────────────────────

@dataclass
class Arg_Info:
    """Annotated 로 인자/필드에 붙는 GUI 표시 메타 (form 이 읽는 실체).

    사용처는 직접 쓰기보다 축약 생성자 ``Arg`` 를 쓴다 — 이 긴 이름은 여기 정의부에만 나온다.
    """

    label: str          = ""
    tip:   str          = ""
    min:   float | None = field(default=None, compare=False)
    max:   float | None = field(default=None, compare=False)
    step:  float | None = field(default=None, compare=False)
    kind:  str          = ""  # "path" 등 특수 위젯


def Arg(tp: Any, label: str = "", *, tip: str = "", min: float | None = None,
        max: float | None = None, step: float | None = None, kind: str = "") -> Any:
    """``Annotated[tp, Arg_Info(...)]`` 축약 — 필드 선언을 짧고 한 줄에 담기 위한 생성자.

    예: ``close_size: Arg(int, "CLOSE 커널 크기 (px)", min=1, max=21) = 3``.
    ``get_type_hints(..., include_extras=True)`` 시점에 평가돼 ``Annotated`` 를 돌려준다
    (사용 모듈이 ``Arg`` 를 import 하고 있어야 함).
    """
    return Annotated[tp, Arg_Info(label, tip, min, max, step, kind)]
