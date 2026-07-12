"""gui/viewer — LEAF type 별 **표현·편집** 레지스트리 (core 의 ``HANDLER_REGISTRY`` 와 짝).

handler 가 "이 값을 어떻게 디스크에 담나"를 정하면, 뷰어는 "이 값을 어떻게 그리고 고치나"를 정한다.
**새 handler 를 떨구면 뷰어 하나만 더하면 UI 가 따라온다** — 이 파일도 안 고친다(아래 import 한 줄뿐).

계약·설계는 [`_base.py`](_base.py), 구조는 [`README.md`](README.md).
"""

from ._base import BRANCH, VIEWERS, Node_viewer, Register, Viewer_for
from . import attr, data, obj, raster      # noqa: F401  (등록 트리거)

__all__ = ["Node_viewer", "Register", "Viewer_for", "VIEWERS", "BRANCH"]
