"""value codec — 파이썬 값 그대로 인라인 (``str``·``int``·``float``·``list``).

format 이름이 곧 **파이썬 타입**이다 — ``("", "str")``·``("bbox", "list")``. 값에 개념이 없으면 도메인
칸(첫 칸)이 비고, 있으면 개념이 찬다(``bbox``). 개념은 **표현**(gui viewer)이 가르는 것이라 I/O 가 같다 —
그래서 개념을 더해도 이 codec 은 안 고친다.
"""

from __future__ import annotations

from numbers import Integral, Real
from pathlib import Path
from typing import Any

from . import CODEC_REGISTRY
from ._base import Inline_Codec
from ...schema import Data_Ref


def Python_type(value: Any) -> str | None:
    """값의 파이썬 타입 이름 (= 인라인 format). 인라인으로 담을 수 없는 타입이면 None.

    ``numbers`` ABC 로 본다 — numpy 스칼라(``np.float64``·``np.int64``)도 그대로 걸리게(process 가 내는
    측정값이 대개 그것이다). ``bool`` 은 int 가 아니라고 본다(파이썬만 그렇게 취급한다).
    """
    if isinstance(value, str):
        return "str"
    if isinstance(value, (list, tuple)):
        return "list"
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return "int"
    if isinstance(value, Real):
        return "float"
    return None


def Inline(value: Any, concept: str = "") -> Data_Ref:
    """파이썬 값 → 인라인 LEAF 서술자 — ``format = (개념, 파이썬 타입)``.

    Raises:
        TypeError: 인라인으로 담을 파이썬 타입이 아닐 때 (조용히 문자열로 만들지 않는다).
    """
    _type = Python_type(value)
    if _type is None:
        raise TypeError(f"인라인으로 담을 수 없는 값: {value.__class__.__name__}")
    return Data_Ref(format=(concept, _type),
                    info={"value": list(value) if _type == "list" else value})


@CODEC_REGISTRY.Register_module("value")
class Value_Codec(Inline_Codec):

    @classmethod
    def Formats(cls) -> tuple[str, ...]:
        return ("str", "int", "float", "list")

    @classmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        return ref.info.get("value")

    @classmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        """raw ``Path`` 면 텍스트로 읽어 값으로, 그 외엔 값 그대로 인라인 보관한다.

        **format(파이썬 타입)은 값이 정한다** — 서술자에 뭐라 적혀 있든 지금 담는 값의 타입이 진실이다.
        개념(첫 칸)은 요청한 대로 보존한다(``bbox`` 로 요청했으면 ``bbox`` 로 남는다). 단 ``"attr"`` 은
        개념이 아니라 옛 등록 이름이라 빈 칸으로 되돌린다(ingest spec ``type: attr`` 이 그리 들어온다).
        """
        _value = src.read_text(encoding="utf-8").strip() if isinstance(src, Path) else src
        _concept = ref.format[0] if ref.format and ref.format[0] != "attr" else ""
        return Data_Ref(format=Inline(_value, _concept).format,
                        info={**ref.info, "value": _value})
