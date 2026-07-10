"""docs 핸들러 — 구조화 문서(dict/list)를 yaml/json 파일로 저장·로드.

``id_map`` 처럼 **중첩 구조**(dict/list)를 파일 payload 로 다룰 때 쓴다 — 인라인 attr(스칼라·meta 안에
보관)과 달리 디스크 파일(yaml/json)로 나간다. 실제 직렬화는 ``python_toolbox.file``(확장자 디스패치)이
소유하므로 여기선 그 입출력만 감싼다. ``Route`` 시 ``format``(yaml/json) 을 주거나, spec 없이 storage
요청이면 ``Claims`` 로 dict/list 를 이 핸들러가 집는다(스칼라는 attr 인라인).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from python_toolbox.file import Read_from, Write_to

from . import HANDLER_REGISTRY
from ._base import File_Handler


@HANDLER_REGISTRY.Register_module("docs")
class Docs_Handler(File_Handler):

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """파일(storage) 요청의 **중첩 구조(dict/list)** 담당 — 스칼라 인라인(attr)과 구분."""
        return 3 if (storage and isinstance(value, (dict, list))) else 0

    @classmethod
    def _Read(cls, path: Path) -> Any:
        _ok, _data = Read_from(path)          # python_toolbox 는 (성공?, 값) 튜플을 준다
        return _data if _ok else None

    @classmethod
    def _Write(cls, data: Any, path: Path) -> None:
        Write_to(path, data)

    @classmethod
    def Default_format(cls) -> str:
        return "yaml"

    @classmethod
    def Extensions(cls) -> tuple[str, ...]:
        return ("yaml", "yml", "json")
