"""constants.py: C/C++ Parser 및 Linker에서 사용하는 전역 상수 정의."""
from typing import Final

# 의존성 분석에서 제외할 C/C++ 기본 타입
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

# UML 스테레오타입
STEREOTYPE_LOCAL = "«local»"
STEREOTYPE_EXTERNAL = "«external»"
STEREOTYPE_SYSTEM = "«system»"

PREFIX_STUB = "stub:"
