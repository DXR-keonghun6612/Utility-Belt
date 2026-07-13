"""gui/editor — 편집기 계층. 골격(`Editor_base`)과 대상별 편집기(`image/`)를 가른다.

골격은 도구·이력·잠금·조준·단축키를 알고 **좌표계와 값은 모른다** — 그래서 3d points·시퀀스 편집기가
들어와도 골격은 안 바뀐다. 계약은 [`_base.py`](_base.py), 설계는 [`README.md`](README.md).
"""

from ._base import Editor_base
from ._history import Edit_history
from ._tool import Tool

__all__ = ["Editor_base", "Edit_history", "Tool"]
