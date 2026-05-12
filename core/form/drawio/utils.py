"""utils.py: Draw.io XML 및 HTML 처리를 위한 범용 유틸리티."""


def Escape_str_for_xml(text: str) -> str:
    """제네릭 및 타입 힌트의 꺾쇠(<, >) 및 특수문자를 HTML 엔티티로 변환함."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
