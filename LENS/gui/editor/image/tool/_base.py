"""그리기 도구 계약 — **무엇을 만들어 내는가**로 가른 편집의 단위.

한때 `Image_editor` 가 도구를 전부 들고 `tool("mode")` 스위치를 여섯 곳(`_on_press`·`_on_move`·
`_on_release`·`_on_right`·`decorate`·`_sync_options`)에서 반복했다. 도구를 하나 더하려면 거기에
`_tool_enabled`·`_on_aim` 까지 여덟 군데를 고쳐야 했고 — 그래서 폴리곤을 1급 데이터로 올릴 수가 없었다.

**도구는 산출물로 갈린다** — 손짓이 아니라. 편집기가 내놓는 것은 둘뿐이라 도구도 둘이다:

| 도구 | 산출물 | 손짓 |
|---|---|---|
| [`_region`](_region.py) | 영역 — "여기가 그 객체다" | 드래그 → 상자 · 꼭짓점 → 폴리곤 · 핸들 |
| [`_pixel`](_pixel.py) | 픽셀 — 라스터에 새긴 것 | 브러시 · 원 · 색채우기 · 올가미 × 칠/지움 |

손짓으로 갈랐으면 bbox·polygon·brush·lasso… 로 파일이 계속 늘고, `erase × lasso` 같은 **곱**이 도구
경계에 걸려 조용히 사라진다. 산출물로 가르면 손짓이 몇 개든 둘 안에서 는다.

## 도구가 드는 것과 안 드는 것

- **기하를 모른다.** 정준형·히트 판정·확정 전 상태(`Draft`)는 [`format/`](../../format/__init__.py) 이
  소유한다 — 도구는 그것을 포인터에 **배선**할 뿐이라, 3d 편집기가 생겨도 옮길 지식이 여기 없다.
- **데이터를 소유하지 않는다.** 데이터는 `Target` 이 들고 이력도 그것을 찍으므로, 도구는 **진행 중
  상호작용 상태만** 든다 — 그래서 도구를 갈아끼워도 이력이 산다.
- **"내가 붙나"를 스스로 안다**(`Applies`/`Enabled`). "어떤 데이터를 조준했나"가 곧 "어떤 도구가
  붙나"라, 그 판정을 편집기의 if-체인이 아니라 도구가 든다.

편집기가 주는 것은 [`_editor.py`](../_editor.py) `Image_editor` 의 공개면뿐이다 — `target`·`commit`·
`set_box`·`preview`·`tool`·`set_tool`·`pointer`·`grab_radius`·`clear_transient`·`bind`.

## view 모드 — 핸들은 도구가, 고르기는 편집기가

`view` 는 캔버스를 안 건드리는 중립 모드라 **언제나 붙는다**(조준이 없어도 클릭으로 객체를 고른다).
그 안에서 *기존 산출물의 핸들을 잡는 것*은 각 도구의 일이므로(상자 코너 · 뒤엔 폴리곤 꼭짓점) `grab`
으로 묻고, 아무도 안 잡으면 그제야 "여기 뭐가 있냐"고 상위에 묻는다.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QHBoxLayout

from ..._tool import Tool


class Draw_tool:
    """그리기 도구 하나 — 툴바 버튼 선언 + 포인터 상호작용 + 자기 미리보기.

    서브클래스는 `TOOLS` 와 `Applies` 를 선언하고, 해당되는 훅만 채운다 (모두 기본값이 있다).
    """

    #: 이 도구가 선언하는 툴바 버튼들 — 편집기가 이어 붙여 툴바·단축키를 만든다.
    TOOLS: tuple[Tool, ...] = ()

    def __init__(self, editor) -> None:
        """Args:
            editor: 이 도구를 든 `Image_editor` — 조준·이력·캔버스 서비스를 여기서 받는다.
        """
        self._e = editor

    # ── 이 대상에 붙나 ────────────────────────────────────────────────────────
    @classmethod
    def Applies(cls, target) -> bool:
        """이 도구가 이 대상에 붙나 — **데이터가 도구를 고른다**.

        Args:
            target: 지금 조준한 `Target` (없으면 ``None``).
        """
        return target is not None

    @classmethod
    def Enabled(cls, target, key: str) -> bool:
        """개별 버튼을 지금 쓸 수 있나 (기본: 도구가 붙으면 전부).

        한 도구가 버튼을 여럿 들고 그중 일부만 조건부일 때 덮어쓴다 — 예: 색 채우기는 볼 배경이 있어야
        한다(`Pixel_tool`).

        Args:
            target: 지금 조준한 `Target` (없으면 ``None``).
            key: 판정할 버튼의 `Tool.key`.
        """
        return cls.Applies(target)

    # ── 포인터 (편집기가 **현재 모드를 든 도구에만** 흘린다) ──────────────────────
    def press(self, x: int, y: int) -> None:
        """좌클릭 (조준·잠금 검사는 편집기가 이미 했다)."""

    def move(self, x: int, y: int) -> None:
        """포인터 이동 — `grab` 으로 잡은 도구가 있으면 모드와 무관하게 그 도구가 받는다."""

    def release(self, x: int, y: int) -> None:
        """좌클릭 해제."""

    def right(self, x: int, y: int) -> bool:
        """우클릭 — 처리했으면 ``True``. ``False`` 면 편집기가 진행 중 조작을 버린다."""
        return False

    def grab(self, x: int, y: int) -> bool:
        """`view` 모드에서 **기존 산출물의 핸들**을 잡았나 (잡았으면 이후 move/release 를 받는다)."""
        return False

    # ── 표시 ──────────────────────────────────────────────────────────────────
    def decorate(self, canvas: np.ndarray) -> None:
        """합성 캔버스에 **지금 하려는 것**을 얹는다 (in-place — 표시본이라 버려진다).

        붙는 도구 전부가 불린다. 그리는 중이 아니면 아무것도 안 그리도록 자기 상태로 가른다.
        """

    def clear_transient(self) -> None:
        """진행 중이던 조작(그리던 도형·드래그)을 버린다."""

    # ── 배선 (편집기 구성 때 한 번) ─────────────────────────────────────────────
    def build_options(self, row: QHBoxLayout) -> None:
        """옵션바에 이 도구의 위젯을 얹는다 (굵기·허용오차 등)."""

    def sync_options(self) -> None:
        """현재 도구에 **의미 있는 옵션만** 보인다 — 안 먹는 입력칸을 두지 않는다."""

    def install_shortcuts(self) -> None:
        """도구 전용 단축키를 건다 (버튼 단축키는 `TOOLS` 선언에서 이미 만들어진다)."""
