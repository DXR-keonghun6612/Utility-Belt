"""Parser Utility Logic (C/C++ 전용)."""
from __future__ import annotations
from pathlib import Path

from .constants import SYSTEM_HEADER_PREFIXES


def Normalize_type(type_str: str) -> str:
    """libclang 타입 문자열에서 불필요한 한정자를 제거하여 정규화합니다."""
    _t = type_str.strip()
    for _qualifier in ("const ", "volatile ", "restrict ", "&", "*"):
        _t = _t.replace(_qualifier, "").strip()
    return _t


def Is_system_header(path: str) -> bool:
    """시스템 헤더 경로인지 판별합니다."""
    return any(path.startswith(_prefix) for _prefix in SYSTEM_HEADER_PREFIXES)


def Extract_namespace_parts(qualified_name: str) -> tuple[str, str]:
    """``ns::inner::ClassName`` 형식에서 ``(namespace_path, class_name)``을 분리합니다."""
    _parts = qualified_name.split("::")
    if len(_parts) == 1:
        return "", _parts[0]
    return "::".join(_parts[:-1]), _parts[-1]


def Make_file_key(file_path: Path, root: Path) -> str:
    """파일 경로를 ``root`` 기준 상대 경로 키로 변환합니다.

    Notes:
        ``root`` 외부 파일이면 절대 경로를 그대로 반환합니다.
    """
    try:
        return str(file_path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(file_path.resolve())


def Make_node_id(file_key: str, namespace_path: str, name: str) -> str:
    """METHODOLOGY §4.1의 노드 ID 규칙으로 식별자를 생성합니다.

    Format::

        {file_key}::{namespace_path}::{name}

    ``namespace_path``가 비어있으면 ``{file_key}::{name}``.
    """
    if namespace_path:
        return f"{file_key}::{namespace_path}::{name}"
    return f"{file_key}::{name}"
