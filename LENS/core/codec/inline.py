"""inline codec — 사이드카 안에 사는 값. **읽을 바이트가 없다.**

값은 이미 ``Data_Ref.info["value"]`` 에 앉아 있다 — 그 사이드카를 읽은 건 `Structure` 고, 여기는 꺼내
줄 뿐이다. 그래서 `Load` 에 I/O 가 한 줄도 없다.

**포맷이 여럿인데 codec 이 하나인 이유** — codec 은 *어느 I/O 모듈이 읽나* 로 갈리는데(cv2 · numpy ·
yaml · 사이드카), 인라인은 그 모듈이 "사이드카" 하나다. 한때 ``polygon``·``rle`` 이 각자 codec 이었지만
그 파일들엔 I/O 가 0 이었다 — 들고 있던 건 구조 변환(``Decode_polygon``)뿐이라 **codec 인 척하는
통과문**이었다. 구조가 갈리는 곳은 [`../format`](../format) 이지 입출력이 아니다.

파일 codec 은 ``format[1]`` 이 곧 확장자지만(png·npy·yaml), 인라인은 **구조 이름**(``rle``·``polygon``·
``bbox``) 또는 **파이썬 타입**(``str``·``int``…)이다. `Load` 가 이 이름으로 디스패치되니, 도메인이 쓰는
구조 이름은 모두 여기 `Formats()` 에 있어야 한다 — 없으면 그 leaf 를 `store.Resolve` 가 못 푼다.

**bbox 는 `Save` 를 안 탄다** — 소비처(gui·store·stream)가 ``Data_Ref`` 를 직접 지어 Push 하고, 읽을
때만 `store.Resolve` → `Load` 를 탄다. 그래서 여기서 bbox format 을 지키는 특수처리는 필요 없다(지킬
`Save` 경로가 없다). `Save` 는 여전히 담는 값의 파이썬 타입으로 format 을 정한다.
"""

from __future__ import annotations

from numbers import Integral, Real
from pathlib import Path
from typing import Any

from . import CODEC_REGISTRY
from ._base import Inline_Codec
from ..schema import Data_Ref


def Python_type(value: Any) -> str | None:
    """값의 파이썬 타입 이름 (= 인라인 format). 인라인으로 담을 수 없는 타입이면 None.

    ``numbers`` ABC 로 본다 — numpy 스칼라(``np.float64``·``np.int64``)도 그대로 걸리게(process 가 내는
    측정값이 대개 그것이다). ``bool`` 은 int 가 아니라고 본다(파이썬만 그렇게 취급한다).

    **구조(``rle``·``polygon`` 의 dict)는 여기서 None 이 나온다** — 파이썬 타입이 그 구조의 이름이 아니다.
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


@CODEC_REGISTRY.Register_module("inline")
class Value_Codec(Inline_Codec):
    """사이드카 인라인 값의 read/write — 스칼라도 구조도 같은 자리에 산다."""

    @classmethod
    def Formats(cls) -> tuple[str, ...]:
        return ("str", "int", "float", "list", "rle", "polygon", "bbox")

    @classmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        """값을 **그대로** 낸다 — 구조를 뭉개지 않는다.

        한때 ``polygon`` codec 이 여기서 ``Decode_polygon`` 을 불러 배열을 냈다(도메인의 대표 포맷).
        그 순간 폴리곤은 영영 배열이라 편집기가 꼭짓점을 볼 수 없었다 — 무엇으로 읽을지는 도메인이
        **나중에 고른다**.
        """
        return ref.info.get("value")

    @classmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        """raw ``Path`` 면 텍스트로 읽어 값으로, 그 외엔 값 그대로 인라인 보관한다.

        **파이썬 값이면 그 타입이 format 의 진실이다** — 서술자에 뭐라 적혀 있든 지금 담는 값이 이긴다.
        **구조(dict)면 파이썬 타입이 그 이름이 아니므로** 서술자의 포맷을 존중한다(도메인이 이미 그
        구조로 맞춰 넘겼다). 개념(첫 칸)은 요청한 대로 보존하되, ``"attr"`` 은 개념이 아니라 옛 등록
        이름이라 빈 칸으로 되돌린다(ingest spec ``type: attr`` 이 그리 들어온다).
        """
        _value = src.read_text(encoding="utf-8").strip() if isinstance(src, Path) else src
        _concept = ref.format[0] if ref.format and ref.format[0] != "attr" else ""
        _stored = ref.format[1] if len(ref.format) > 1 else ""
        _type = Python_type(_value)
        return Data_Ref(format=(_concept, _type or _stored),
                        info={**ref.info,
                              "value": list(_value) if _type == "list" else _value})
