"""select — object 선택/게이트 유닛.

``Center_distance``(측정: 중심거리 → attr) + ``Attr_gate``(범용 게이트: ctx 값 조건으로 unit 스킵).
gate 는 Stage 엔진 공유 덕에 Run·Sample 어디서든 동작한다 — 자세한 설계는 [`README.md`](README.md).
"""

from .center import Center_distance
from .gate import Attr_gate

__all__ = ["Center_distance", "Attr_gate"]
