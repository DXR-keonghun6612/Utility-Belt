"""편집 undo/redo 스택 — 스택 인덱스 관리만 (스냅샷 생성/복원은 호출 측 콜백)."""

from __future__ import annotations

from typing import Callable


class Edit_history:
    """스냅샷 리스트 + 현재 인덱스로 undo/redo 를 관리하는 스택.

    Args:
        take: 현재 편집 상태의 스냅샷을 만들어 돌려주는 콜백 ``() -> snapshot``.
        apply: 스냅샷으로 편집 상태를 되돌리는 콜백 ``(snapshot) -> None``.
    """

    def __init__(self, take: Callable[[], object],
                 apply: Callable[[object], None]) -> None:
        self._take = take
        self._apply = apply
        self._stack: list = []
        self._idx = -1

    def reset(self) -> None:
        """이력을 현재 상태 한 칸으로 초기화한다 (stem 로드 직후)."""
        self._stack = [self._take()]
        self._idx = 0

    def commit(self) -> None:
        """현재 상태를 이력에 적재한다 (redo 꼬리는 버린다)."""
        del self._stack[self._idx + 1:]
        self._stack.append(self._take())
        self._idx = len(self._stack) - 1

    def undo(self) -> None:
        """직전 이력 상태로 되돌린다 (맨 앞이면 no-op)."""
        if self._idx <= 0:
            return
        self._idx -= 1
        self._apply(self._stack[self._idx])

    def redo(self) -> None:
        """취소했던 다음 이력 상태로 되돌린다 (맨 끝이면 no-op)."""
        if self._idx >= len(self._stack) - 1:
            return
        self._idx += 1
        self._apply(self._stack[self._idx])
