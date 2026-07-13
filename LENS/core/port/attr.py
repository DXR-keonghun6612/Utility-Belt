"""attr — **인라인 값**의 실체화. 파일이 아니라 ``Data_Ref.info["value"]`` 에 값이 그대로 산다.

LEAF format 은 ``(개념, 파이썬 타입)`` 이다. 인라인 값은 **대개 개념이 없다** — 그냥 문자열이고 정수다:
``("", "str")`` · ``("", "int")`` · ``("", "float")`` · ``("", "list")``. 도메인 개념이 있을 때만 첫 칸이
찬다: ``("bbox", "list")`` — 첫 칸이 원소 규약(int 4개)을 말하고, 둘째 칸은 그저 파이썬 타입이다.
원소 타입은 **검사하지 않는다** — ``bbox`` 에 문자열 리스트를 넣는 건 넣는 쪽 문제다.

예전엔 이 전부가 ``("attr", <아무 문자열>)`` 이었다 — 타입 자리에 타입이 아닌 걸 적은 것이다(값이 list
인데 detail 은 ``"str"``). 이제 **파이썬 타입이 곧 detail** 이고, 개념은 첫 칸으로 나온다.

**개념을 더해도 이 파일을 안 고친다.** ``port`` 는 등록된 파일 핸들러(image·segmap·array·rle)만 첫 칸으로
디스패치하고 **거기 없는 첫 칸은 전부 여기로 보낸다**(빈 칸이든 ``bbox`` 든). 인라인은 파이썬 값을 그대로
두는 일이라 개념별로 다를 I/O 가 없다 — 개념이 갈리는 곳은 **표현**(`gui/viewer/attr.py`)이다.
"""

from __future__ import annotations

from numbers import Integral, Real
from pathlib import Path
from typing import Any

from . import HANDLER_REGISTRY
from ..schema import Data_Ref
from ._base import Handler


def Python_type(value: Any) -> str | None:
    """값의 파이썬 타입 이름 (= 인라인 detail). 인라인으로 담을 수 없는 타입이면 None.

    ``numbers`` ABC 로 본다 — numpy 스칼라(``np.float64``·``np.int64``)도 그대로 걸리게(process 가
    내는 측정값이 대개 그것이다). ``bool`` 은 int 가 아니라고 본다(파이썬만 그렇게 취급한다).
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

    Args:
        value: 인라인으로 담을 값 (str·int·float·list).
        concept: 도메인 개념 (``bbox`` 등). 없으면 첫 칸이 빈다 — "그냥 파이썬 값" 이라는 뜻.

    Returns:
        ``Data_Ref`` — ``format=(concept, 파이썬 타입)``, ``info={"value": …}``.

    Raises:
        TypeError: 인라인으로 담을 파이썬 타입이 아닐 때 (조용히 문자열로 만들지 않는다).
    """
    _type = Python_type(value)
    if _type is None:
        raise TypeError(f"인라인으로 담을 수 없는 값: {value.__class__.__name__}")
    return Data_Ref(format=(concept, _type),
                    info={"value": list(value) if _type == "list" else value})


@HANDLER_REGISTRY.Register_module("attr")
class Attr_Handler(Handler):
    """인라인 핸들러 — 파일 핸들러가 아무도 안 맡는 값은 전부 여기로 온다 (파일 I/O 없음)."""

    INLINE = True

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """meta(인라인) 요청의 최저 fallback — 파일이 아닌 파이썬 값(스칼라·list) 담당."""
        return 1 if not storage and Python_type(value) is not None else 0

    @classmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        return ref.info.get("value")

    @classmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        """raw ``Path`` 면 텍스트로 읽어 값으로, 그 외엔 값 그대로 인라인 보관한다.

        **detail 은 값이 정한다** — 서술자에 뭐라 적혀 있든 지금 담는 값의 파이썬 타입이 진실이다.
        개념(첫 칸)은 요청한 대로 보존한다(``bbox`` 로 요청했으면 ``bbox`` 로 남는다). 단 ``"attr"``
        은 개념이 아니라 이 핸들러의 등록 이름이라 빈 칸으로 되돌린다 — ingest spec(``type: attr``)이
        그 이름으로 들어오기 때문이다.
        """
        _value = (src.read_text(encoding="utf-8").strip()
                  if isinstance(src, Path) else src)
        _concept = ref.format[0] if ref.format and ref.format[0] != "attr" else ""
        return Data_Ref(format=Inline(_value, _concept).format,
                        info={**ref.info, "value": _value})
