"""Serialization helpers — Data_Schema ↔ yaml/json.

plan/caching.md: 확장자 기반 자동 직렬화(python_toolbox의 ``file`` 모듈 활용).
역직렬화 시 클래스 디스패치는 ``type`` 필드(클래스명)와 Registry로 수행.

본 모듈은 단계 yaml의 ``meta`` + ``body`` 구조를 다루는 얇은 래퍼이며,
구체적인 무효화 로직은 `core.hashing`에 위치한다.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from python_toolbox import Data_Schema
from python_toolbox.file import Read_from, Write_to


TYPE_KEY: str = "type"
META_KEY: str = "meta"
BODY_KEY: str = "body"


def Embed_type(obj: Data_Schema) -> dict:
    """``Data_Schema.Serialize()`` 결과 최상위에 클래스명을 ``type`` 키로 부착.

    Notes:
        중첩된 ``Data_Schema``는 ``Serialize()`` 내부 재귀로 이미 dict화되어
        원본 타입 정보가 손실된다. 중첩까지 type 마커가 필요하면 별도
        visitor를 도입한다 (TODO: 필요해지면 확장).
    """
    _d = obj.Serialize()
    _d[TYPE_KEY] = obj.__class__.__name__
    return _d


def Save_stage(
    path: Path | str,
    body: dict | Data_Schema,
    meta: dict | None = None,
    encoding: str = "UTF-8",
) -> None:
    """단계 출력을 ``{meta, body}`` 형태의 yaml/json으로 저장.

    Args:
        path: 저장 경로. 확장자(.yaml/.yml/.json)에 따라 포맷 자동 결정.
        body: 단계 본문. ``Data_Schema``면 ``Embed_type``으로 변환.
        meta: 단계 메타 (해시·schema_version 등). 생략 가능.
        encoding: 텍스트 인코딩.
    """
    _body = Embed_type(body) if isinstance(body, Data_Schema) else body
    _payload = {META_KEY: meta or {}, BODY_KEY: _body}
    Write_to(Path(path), _payload, encoding)


def Load_stage(
    path: Path | str, encoding: str = "UTF-8"
) -> tuple[dict, Any] | None:
    """단계 출력 yaml/json을 ``(meta, body)`` 튜플로 로드.

    Returns:
        성공 시 ``(meta dict, body dict)``, 파일이 없거나 읽기 실패 시 ``None``.
    """
    _ok, _data = Read_from(Path(path), encoding)
    if not _ok or not isinstance(_data, dict):
        return None
    return _data.get(META_KEY, {}), _data.get(BODY_KEY)


def Stage_path(
    output_root: Path | str, stage: str, key: str, ext: str = "yaml"
) -> Path:
    """단계 결과의 표준 경로 산출.

    구조::

        {output_root}/debug/{stage}/{key}.{ext}

    예: ``debug/01_parser/src__core__widget.cpp.yaml``.

    Args:
        output_root: 출력 루트 디렉토리.
        stage: 단계 식별자 (예: ``"01_parser"``).
        key: 파일별/디렉토리별 키 (구분자는 ``__``로 정규화).
        ext: 파일 확장자 (yaml/yml/json).
    """
    return Path(output_root) / "debug" / stage / f"{key}.{ext}"
