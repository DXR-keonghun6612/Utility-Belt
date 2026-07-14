"""docs codec — 중첩 구조(dict/list) ↔ yaml/json 파일.

``id_map`` 처럼 구조화된 문서를 파일 payload 로 다룰 때. 실제 직렬화는 ``python_toolbox.file``(확장자
디스패치)이 소유하므로 여기선 그 입출력만 감싼다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from python_toolbox.file import Read_from, Write_to

from . import CODEC_REGISTRY
from ._base import File_Codec


@CODEC_REGISTRY.Register_module("docs")
class Docs_Codec(File_Codec):

    @classmethod
    def Formats(cls) -> tuple[str, ...]:
        return ("yaml", "yml", "json")

    @classmethod
    def _Read(cls, path: Path) -> Any:
        _ok, _data = Read_from(path)          # python_toolbox 는 (성공?, 값) 튜플을 준다
        return _data if _ok else None

    @classmethod
    def _Write(cls, data: Any, path: Path) -> None:
        Write_to(path, data)
