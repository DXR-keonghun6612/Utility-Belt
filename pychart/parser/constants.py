"""constants.py: Python Parser 및 Linker에서 사용하는 전역 상수 정의."""
from typing import Final

IGNORED_FILES: Final[set[str]] = {
    "setup.py"
}

IGNORED_MODULES: Final[set[str]] = {
    "sys", "os", "typing", "abc", "enum", "dataclasses", "__future__",
    "typing_extensions", "collections.abc", "ast", "pathlib", "argparse"
}

IGNORED_TYPES: Final[set[str]] = {
    "int", "str", "float", "bool", "list", "dict", "tuple", "set", "bytes",
    "complex", "range", "slice", "type", "object", "None", "self", "Any",
    "Optional", "Union", "List", "Dict", "Tuple", "Set", "Iterable", "Iterator",
    "Generator", "Callable", "Type", "TypeVar", "Generic", "ClassVar", "Final",
    "Literal", "Annotated", "Protocol", "RuntimeCheckable", "TypeGuard", "AnyStr",
    "InitVar", "field", "dataclass"
}

TYPE_ANY = "Any"
TYPE_UNKNOWN = "Unknown"

# UML 스테레오타입
STEREOTYPE_ENUM = "«enumeration»<br>"
STEREOTYPE_DATACLASS = "«dataclass»<br>"
STEREOTYPE_FUNC = "«function»<br>"
STEREOTYPE_LOCAL = "«local»"
STEREOTYPE_EXTERNAL = "«external»"

PREFIX_STUB = "stub:"