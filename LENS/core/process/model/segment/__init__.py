"""segment — 프레임 객체 bbox 를 backend 로 분할하는 정책 프로세스.

``_base.py`` 의 ``Base_segment`` (모델 무관 기본 정책) 위에, ``with_hole.py`` 의
``Segment_with_hole`` (구멍 보존 특화)가 실제 등록되는 프로세스다. backend(``model``:
``encode``/``run`` 프리미티브, 예 ``Sam3_runner``)는 config 로 주입 — 교체 시 정책은 그대로 둔다.
"""

from .with_hole import Segment_with_hole

__all__ = ["Segment_with_hole"]
