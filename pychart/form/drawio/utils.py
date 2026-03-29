"""utils.py: Draw.io XML 및 HTML 처리를 위한 범용 유틸리티."""

def Escape_str_for_xml(text: str) -> str:
    """제네릭 및 타입 힌트의 꺾쇠(<, >) 및 특수문자를 HTML 엔티티로 변환함.

    Args:
        text: 변환할 원본 문자열.

    Returns:
        str: XML/HTML 안전 문자열.
    """
    if not text:
        return ""
    # XML/HTML 예약어 치환 (순서 주의: &를 가장 먼저 치환)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
