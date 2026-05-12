"""Parser Utility Logic (C/C++ 전용)."""
from pathlib import Path


def Normalize_type(type_str: str) -> str:
    """libclang 타입 문자열에서 불필요한 한정자를 제거하여 정규화함."""
    _t = type_str.strip()
    for qualifier in ("const ", "volatile ", "restrict ", "&", "*"):
        _t = _t.replace(qualifier, "").strip()
    return _t


def Is_system_header(path: str) -> bool:
    """시스템 헤더 경로인지 판별함."""
    from cchart.parser.constants import SYSTEM_HEADER_PREFIXES
    return any(path.startswith(prefix) for prefix in SYSTEM_HEADER_PREFIXES)


def Extract_namespace_parts(qualified_name: str) -> tuple[str, str]:
    """'ns::inner::ClassName' 형식에서 (namespace_path, class_name)을 분리함."""
    _parts = qualified_name.split("::")
    if len(_parts) == 1:
        return "", _parts[0]
    return "::".join(_parts[:-1]), _parts[-1]


def Make_file_key(file_path: Path, root: Path) -> str:
    """파일 경로를 root 기준 상대 경로 키로 변환함."""
    try:
        return str(file_path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(file_path.resolve())
