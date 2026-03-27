def R_brackets(text: str) -> str:
    """제네릭 및 타입 힌트의 꺾쇠를 HTML 엔티티로 변환함."""
    return text.replace("<", "&lt;").replace(">", "&gt;")
