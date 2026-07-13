"""편집 undo/redo 스택 — **스냅샷의 내용은 편집기가 정한다** (여기는 인덱스만 든다).

이력이 스냅샷을 만들 줄 알면 편집기 타입마다 이력이 하나씩 생긴다(라스터용·포인트용·시퀀스용).
그래서 만들기·되돌리기를 콜백으로 받고, 여기는 **언제 쌓고 어디로 돌아가는지**만 안다 — 그러면 무엇을
편집하든 이력은 하나다.
"""
from __future__ import annotations

from typing import Callable

_LIMIT = 30


class Edit_history:
    """스냅샷 스택 + 현재 인덱스로 undo/redo 를 관리한다.

    Args:
        take: 현재 편집 상태의 스냅샷을 만들어 돌려주는 콜백 ``() -> snapshot``.
        apply: 스냅샷으로 편집 상태를 되돌리는 콜백 ``(snapshot) -> None``.
        limit: 보관할 최대 스냅샷 수 (넘으면 오래된 것부터 버린다).
    """

    def __init__(self, take: Callable[[], object],
                 apply: Callable[[object], None], limit: int = _LIMIT) -> None:
        self._take = take
        self._apply = apply
        self._limit = limit
        self._stack: list = []
        self._idx = -1

    def reset(self) -> None:
        """이력을 현재 상태 한 칸으로 초기화한다 (조준 대상이 바뀐 직후)."""
        self._stack = [self._take()]
        self._idx = 0

    def clear(self) -> None:
        """이력을 완전히 비운다 (조준할 대상이 없어졌을 때 — 되돌릴 곳도 없다)."""
        self._stack = []
        self._idx = -1

    def commit(self) -> None:
        """현재 상태를 이력에 적재한다 (redo 꼬리는 버린다)."""
        if self._idx < 0:                      # reset 없이 커밋 — 첫 칸을 만든다
            self.reset()
            return
        del self._stack[self._idx + 1:]
        self._stack.append(self._take())
        if len(self._stack) > self._limit:
            del self._stack[0]
        self._idx = len(self._stack) - 1

    def current(self):
        """지금 서 있는 스냅샷 (이력이 비었으면 None) — 편집기가 "이 칸이 누구 것인가"를 볼 때 쓴다."""
        return self._stack[self._idx] if self._idx >= 0 else None

    def can_undo(self) -> bool:
        return self._idx > 0

    def can_redo(self) -> bool:
        return 0 <= self._idx < len(self._stack) - 1

    def undo(self) -> bool:
        """직전 상태로 되돌린다 (맨 앞이면 no-op). 되돌렸으면 True."""
        if not self.can_undo():
            return False
        self._idx -= 1
        self._apply(self._stack[self._idx])
        return True

    def redo(self) -> bool:
        """취소했던 다음 상태로 되돌린다 (맨 끝이면 no-op). 되돌렸으면 True."""
        if not self.can_redo():
            return False
        self._idx += 1
        self._apply(self._stack[self._idx])
        return True
