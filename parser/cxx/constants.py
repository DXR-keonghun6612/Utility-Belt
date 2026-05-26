"""C/C++ Parser/Linker 공유 상수.

Notes:
    이전의 ``STEREOTYPE_LOCAL / EXTERNAL / SYSTEM`` 상수는
    plan/data-model.md에 따라 ``Module_Info.origin`` (Literal) 어휘로
    통일되어 본 모듈에서 제거되었다.
"""
from __future__ import annotations
from typing import Final


# 의존성 분석에서 제외할 C/C++ 기본 타입 및 자주 등장하는 STL 컨테이너
IGNORED_TYPES: Final[set[str]] = {
    "void", "int", "char", "bool", "float", "double",
    "long", "short", "unsigned", "signed",
    "size_t", "ptrdiff_t", "nullptr_t", "auto",
    "std::string", "std::vector", "std::map", "std::set",
    "std::unique_ptr", "std::shared_ptr", "std::weak_ptr",
    "std::optional", "std::variant", "std::pair",
}

# 분석에서 제외할 시스템 헤더 접두사
SYSTEM_HEADER_PREFIXES: Final[tuple[str, ...]] = (
    "/usr/", "/usr/local/", "/opt/",
)

# 03_linker가 외부 stub 노드 ID를 만들 때 사용하는 prefix
PREFIX_STUB: Final[str] = "stub::"

# 언어 식별자
LANGUAGE: Final[str] = "cxx"
