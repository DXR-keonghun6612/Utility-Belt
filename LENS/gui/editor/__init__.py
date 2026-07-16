"""gui/editor — 편집기 계층. 골격(`Editor_base`)·좌표 데이터(`format/`)·대상별 편집기(`image/`)를 가른다.

골격은 도구·이력·잠금·조준·단축키를 알고 **좌표계와 값은 모른다**. [`format/`](format/__init__.py) 은
좌표 데이터의 표현(bbox·polygon)을 numpy 로 **차원 무지하게** 든다 — 둘 다 3d points·시퀀스 편집기가
들어와도 안 바뀐다. 바뀌는 건 `image/` 처럼 캔버스·렌더에 묶인 층뿐이다.

계약은 [`_base.py`](_base.py), 설계는 [`README.md`](README.md).
"""

from ._base import Editor_base
from ._history import Edit_history
from ._tool import Tool

__all__ = ["Editor_base", "Edit_history", "Tool"]
