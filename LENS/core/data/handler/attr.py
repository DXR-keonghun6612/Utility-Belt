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

    @classmethod
    def Load(
        cls, root: str, stem: str | None, name: str, ref: Data_Ref,
        *, obj_id: str | None = None
    ) -> Any:
        return ref.info.get("value")

    @classmethod
    def Save(
        cls, root: str, stem: str | None, name: str, ref: Data_Ref, src: Any,
        *, obj_id: str | None = None
    ) -> Data_Ref:
        _value = (src.read_text(encoding="utf-8").strip()
                  if isinstance(src, Path) else src)
        return Data_Ref(
            type=ref.type,
            format=ref.format or cls.Default_format(),
            info={**ref.info, "value": _value},
        )

    @classmethod
    def Default_format(cls) -> str:
        return "str"
