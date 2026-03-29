"""constants.py: Parser 및 Linker에서 사용하는 전역 상수 정의."""
from typing import Final

# 아키텍처 분석에서 제외할 인프라/메타 모듈 정의 (Extractor에서 사용)
IGNORED_MODULES: Final[set[str]] = {
    "typing", "abc", "enum", "dataclasses", "__future__", 
    "typing_extensions", "collections.abc", "ast", "pathlib", "argparse"
}

# 의존성 분석(Edge 생성)에서 제외할 파이썬 내장 및 메타 타입 정의 (Linker에서 사용)
IGNORED_TYPES: Final[set[str]] = {
    # Built-ins (Python 표준 내장 타입)
    "int", "str", "float", "bool", "list", "dict", "tuple", "set", "bytes", 
    "complex", "range", "slice", "type", "object", "None", "self", "Any",
    # Typing Module (Generic 타입 및 메타 정보)
    "Optional", "Union", "List", "Dict", "Tuple", "Set", "Iterable", "Iterator", 
    "Generator", "Callable", "Type", "TypeVar", "Generic", "ClassVar", "Final", 
    "Literal", "Annotated", "Protocol", "RuntimeCheckable", "TypeGuard", "AnyStr",
    # Framework/Library Meta (Dataclass 및 기타 메타 키워드)
    "InitVar", "field", "dataclass"
}
