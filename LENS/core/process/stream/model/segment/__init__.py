"""segment — 프레임 객체 bbox 를 backend 로 분할하는 정책 프로세스.

``_base.py`` 의 ``Segment`` (모델 무관 plain box→best mask)가 등록되는 프로세스다. backend
(``model``: ``encode``/``run`` 프리미티브, 예 [`Sam3_runner`](../torch/_sam3.py))는 config 로 주입 — 교체 시 정책은
그대로 둔다. 영역 제거(구멍/슬릿)는 downstream process 로 조합한다.
"""

from ._base import Segment

__all__ = ["Segment"]
