"""utils.py: Draw.io XML 및 HTML 처리를 위한 범용 유틸리티."""

def R_brackets(text: str) -> str:
    """제네릭 및 타입 힌트의 꺾쇠(<, >)를 HTML 엔티티로 변환함.

    Args:
        text: 변환할 원본 문자열.

    Returns:
        str: 변환된 문자열.
    """
    return text.replace("<", "&lt;").replace(">", "&gt;")
