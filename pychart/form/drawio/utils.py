"""utils.py: Draw.io XML 및 HTML 처리를 위한 범용 유틸리티."""
import re


def R_brackets(text: str) -> str:
    """제네릭 및 타입 힌트의 꺾쇠(<, >)를 HTML 엔티티로 변환함.

    Args:
        text: 변환할 원본 문자열.

    Returns:
        str: 변환된 문자열.
    """
    return text.replace("<", "&lt;").replace(">", "&gt;")


def Type_highlight(
    type_hint: str, builtin_types: set[str], color: str = "#0066CC"
) -> str:
    """타입 힌트 내의 사용자 정의 타입을 정규표현식으로 찾아 강조함.

    Args:
        type_hint: HTML 엔티티로 변환된 타입 힌트 문자열.
        builtin_types: 강조에서 제외할 내장 타입 집합.
        color: 사용자 정의 타입에 적용할 Hex 색상 코드.

    Returns:
        str: 사용자 정의 타입에 HTML 강조 태그가 적용된 문자열.
    """
    def _replacer(match: re.Match) -> str:
        word = match.group(0)
        if word in builtin_types:
            return word
        return f"<b><font color='{color}'>#{word}</font></b>"

    return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", _replacer, type_hint)
