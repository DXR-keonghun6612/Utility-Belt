"""attr 핸들러 — 인라인 값(scalar·list 등). meta 안에 직접 보관한다.

payload 는 ``Data_Ref.info["value"]`` 에 인라인. raw Path 면 텍스트로 읽어 값으로 삼고,
그 외엔 값 그대로 보관한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import HANDLER_REGISTRY
from ._base import Data_Ref, Handler


@HANDLER_REGISTRY.Register_module("attr")
class Attr_Handler(Handler):

    INLINE = True

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """meta(인라인) 요청의 최저 fallback — 스칼라·list·dict 등 파일 아닌 값 담당."""
        return 1 if not storage else 0

    @classmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        return ref.info.get("value")

    @classmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        _value = (src.read_text(encoding="utf-8").strip()
                  if isinstance(src, Path) else src)
        return Data_Ref(
            format=ref.format or ("attr", cls.Default_format()),
            info={**ref.info, "value": _value},
        )

    @classmethod
    def Default_format(cls) -> str:
        return "str"
