"""도구 선언 — 편집기가 **무엇을 할 수 있는가**를 데이터로 적는다.

버튼·단축키·배타 그룹을 손으로 세 번 배선하면 셋이 조용히 어긋난다(툴바엔 있는데 단축키가 없는 식).
그래서 도구는 선언이고, 툴바와 단축키는 그 선언을 **읽어서** 만든다 — 도구를 하나 더하면 둘 다 따라온다.

``group`` 이 배타 축이다. 이미지 편집은 두 축의 곱이라(조작 × 모양) 그룹이 둘이고, 다른 편집기는 다른
축을 선언한다 — Base 는 축이 몇 개든 모른다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    """도구 하나.

    Attributes:
        key: 식별자 (``paint``·``brush`` …). 편집기 로직이 이걸로 분기한다.
        group: 배타 그룹 — 같은 그룹에선 한 번에 하나만 선택된다.
        icon: 툴바 버튼에 보일 글자/이모지.
        label: 사람이 읽는 이름 (툴팁 제목).
        shortcut: 단축키 (``V``·``B`` … 없으면 빈 문자열).
        tip: 툴팁 본문 — 이 도구가 무엇을 하는지.
    """

    key:      str
    group:    str
    icon:     str
    label:    str
    shortcut: str = ""
    tip:      str = ""

    def tooltip(self) -> str:
        """툴바 버튼에 붙일 툴팁 (단축키를 함께 보인다)."""
        _body = f"{self.label} — {self.tip}" if self.tip else self.label
        return f"{_body}  [{self.shortcut}]" if self.shortcut else _body
