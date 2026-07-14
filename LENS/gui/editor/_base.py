"""편집기 골격 — **무엇을 편집하는지 모르는 편집기.**

편집기가 하나뿐일 땐 라스터·픽셀·OpenCV 가 편집기 안에 뒤섞여 있었다. 그러면 3d points 나 시퀀스가
들어올 때 편집기를 **하나 더 짜야** 한다 — 도구 전환·이력·잠금·단축키·조준은 매번 똑같은데도.

그래서 그 다섯을 여기로 올린다. ``Editor_base`` 가 아는 것은:

- **도구** — 서브클래스가 [`Tool`](_tool.py) 로 선언하면 툴바 버튼과 단축키가 **선언에서** 만들어진다.
- **이력** — undo/redo 스택. 스냅샷의 **내용은 서브클래스가 정한다**(`_snapshot`/`_restore`).
- **잠금** — 백그라운드 작업 중엔 보기만 남긴다.
- **조준** — 무엇을 편집 중인가. 대상이 바뀌면(``target.key``) 이력을 비운다. **도구 선택은 유지한다** —
  객체를 옮겨 다니며 계속 칠하는 게 라벨링이라, 옮길 때마다 붓을 다시 고르게 하면 안 된다.
- **포인터** — 캔버스의 press/move/release/right 를 서브클래스 훅으로 흘린다.

모르는 것은 **좌표계와 값**이다 — numpy·cv2·`Data_Ref`·store 어느 것도 여기 없다. 그래서 캔버스가
2D 이미지든 3D 뷰포트든 타임라인이든 이 파일은 안 바뀐다.

## 캔버스 계약

`_make_canvas()` 가 돌려주는 위젯은 포인터를 **도메인 좌표**로 낸다 — 무슨 좌표인지는 Base 가 모르고
서브클래스만 안다(이미지면 원본 픽셀, 3d 면 ray hit …):

``mouse_pressed(x, y)`` · ``mouse_moved(x, y)`` · ``mouse_released(x, y)`` ·
``mouse_right_pressed(x, y)`` · ``set_interactive(bool)``
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._history import Edit_history
from ._tool import Tool


class Editor_base(QWidget):
    """도구·이력·잠금·조준을 든 편집기 골격 (무엇을 편집하는지는 서브클래스가 안다).

    Attributes:
        changed: 편집이 확정됨 — 상위가 영속화한다 (payload 는 서브클래스가 정한다).
        preview: 진행 중 표시가 바뀜 — 상위가 캔버스를 다시 그린다.
        picked: 캔버스에서 대상을 **골라달라** ``(x, y, additive)`` — 거기 무엇이 있는지는 상위가 안다
            (편집기는 트리를 모른다). ``additive`` 는 Shift 를 누른 채 고른 것 = 선택에 **더하기**.
    """

    #: 서브클래스가 선언하는 도구들 — 툴바 버튼·단축키·배타 그룹이 여기서 만들어진다.
    TOOLS: tuple[Tool, ...] = ()

    changed = Signal(object)
    preview = Signal()
    picked  = Signal(int, int, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._target = None
        self._hint = ""
        self._locked = False
        self._buttons: dict[str, QToolButton] = {}
        self._current: dict[str, str] = {}          # group → 선택된 tool key
        self._history = Edit_history(self._snapshot, self._restore)

        self.canvas = self._make_canvas()
        self._build()
        self._install_shortcuts()

        self.canvas.mouse_pressed.connect(self._press)
        self.canvas.mouse_moved.connect(self._move)
        self.canvas.mouse_released.connect(self._release)
        self.canvas.mouse_right_pressed.connect(self._right)
        self._sync()

    # ── 골격 ──────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        """세로 툴바 | (상태바 · 캔버스 · 옵션바) — 서브클래스는 슬롯만 채운다."""
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)
        _lay.addWidget(self._build_toolbar())

        _right = QVBoxLayout()
        _right.setContentsMargins(0, 0, 0, 0)
        _right.setSpacing(2)

        self._status = QHBoxLayout()
        self._aim_label = QLabel()
        self._aim_label.setStyleSheet("color: #aaa;")
        self._status.addWidget(self._aim_label)
        self._status.addStretch(1)
        self._build_status(self._status)             # 서브클래스 추가 (밝기 등)
        self._undo_btn = self._flat_button("↶", "실행취소  [Ctrl+Z]", self.undo)
        self._redo_btn = self._flat_button("↷", "다시실행  [Ctrl+Y]", self.redo)
        self._status.addWidget(self._undo_btn)
        self._status.addWidget(self._redo_btn)
        _right.addLayout(self._status)

        _right.addWidget(self.canvas, stretch=1)

        self._options = QHBoxLayout()
        self._build_options(self._options)           # 서브클래스 추가 (굵기·허용오차 등)
        self._options.addStretch(1)
        _right.addLayout(self._options)

        _lay.addLayout(_right, stretch=1)

    def _build_toolbar(self) -> QWidget:
        """`TOOLS` 선언 → 세로 툴바. 그룹이 바뀌는 자리에 구분선을 넣는다."""
        _bar = QWidget()
        _bar.setFixedWidth(38)
        _lay = QVBoxLayout(_bar)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(2)

        _groups: dict[str, QButtonGroup] = {}
        _prev = ""
        for _tool in self.TOOLS:
            if _prev and _tool.group != _prev:
                _line = QFrame()
                _line.setFrameShape(QFrame.Shape.HLine)
                _line.setStyleSheet("color: #444;")
                _lay.addWidget(_line)
            _prev = _tool.group

            if _tool.group not in _groups:
                _g = QButtonGroup(self)
                _g.setExclusive(True)
                _groups[_tool.group] = _g
                self._current[_tool.group] = _tool.key     # 그룹의 첫 도구가 기본값

            _b = QToolButton()
            _b.setText(_tool.icon)
            _b.setToolTip(_tool.tooltip())
            _b.setCheckable(True)
            _b.setFixedSize(32, 30)
            _b.clicked.connect(lambda _c=False, k=_tool.key: self.set_tool(k))
            _groups[_tool.group].addButton(_b)
            self._buttons[_tool.key] = _b
            _lay.addWidget(_b)

        _lay.addStretch(1)
        return _bar

    def _install_shortcuts(self) -> None:
        """도구 선언의 단축키 + 이력 단축키를 건다.

        ``WidgetWithChildren`` 컨텍스트라 편집기 안에 포커스가 있을 때만 먹는다 — 팝아웃이든 임베드든
        메인 창의 단축키와 안 부딪친다.
        """
        for _tool in self.TOOLS:
            if _tool.shortcut:
                self.bind(_tool.shortcut, lambda k=_tool.key: self.set_tool(k))
        self.bind("Ctrl+Z", self.undo)
        self.bind("Ctrl+Y", self.redo)

    def bind(self, seq: str, slot) -> None:
        """편집기 스코프 단축키를 건다 (서브클래스·호출 측이 더 얹을 수 있다)."""
        _sc = QShortcut(QKeySequence(seq), self)
        _sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        _sc.activated.connect(slot)

    @staticmethod
    def _flat_button(text: str, tip: str, slot) -> QToolButton:
        _b = QToolButton()
        _b.setText(text)
        _b.setToolTip(tip)
        _b.setFixedSize(30, 26)
        _b.clicked.connect(slot)
        return _b

    # ── 도구 ──────────────────────────────────────────────────────────────────
    def tool(self, group: str) -> str:
        """그룹에서 지금 선택된 도구 key."""
        return self._current.get(group, "")

    def set_tool(self, key: str) -> None:
        """도구를 고른다 — 진행 중이던 조작은 버린다 (도구가 바뀌면 그리던 것도 뜻을 잃는다)."""
        _tool = next((_t for _t in self.TOOLS if _t.key == key), None)
        if _tool is None or not self._tool_enabled(_tool):
            return
        self._current[_tool.group] = key
        self._on_tool(_tool)
        self.clear_transient()
        self._sync()

    # ── 조준 ──────────────────────────────────────────────────────────────────
    def aim(self, target, *, hint: str = "") -> None:
        """편집 대상을 갈아끼운다 — **도구 선택은 유지**하고, 대상이 바뀔 때만 이력을 비운다.

        Args:
            target: 새 대상 (``key`` 속성으로 동일성을 판정한다). 없으면 편집 불가.
            hint: 조준이 없을 때 사용자에게 보일 이유 — 조용히 안 먹는 편집기를 두지 않는다.
        """
        _switched = _key_of(target) != _key_of(self._target)
        self._target = target                       # 이력이 스냅샷을 **새 대상**으로 찍도록 먼저 바꾼다
        self._hint = hint
        if _switched:
            self._history.clear()
            if target is not None:
                self._history.reset()
        self.clear_transient()
        self._on_aim(target)
        self._sync()

    def target(self):
        """지금 조준한 대상 (없으면 None)."""
        return self._target

    def set_locked(self, locked: bool) -> None:
        """편집 잠금 (백그라운드 작업 중) — 보기·줌은 살리고 편집만 막는다."""
        self._locked = locked
        self.clear_transient()
        self._sync()

    def armed(self) -> bool:
        """편집할 수 있는 상태인가 (조준 있음 + 잠기지 않음)."""
        return self._target is not None and not self._locked

    # ── 이력 ──────────────────────────────────────────────────────────────────
    def commit(self) -> None:
        """지금 상태를 이력에 적재하고 ``changed`` 를 낸다 (편집 확정)."""
        if not self.armed():
            return
        self._history.commit()
        self._sync()
        self.changed.emit(self._target)

    def undo(self) -> None:
        if self.armed() and self._history.undo():
            self.clear_transient()
            self._sync()
            self.changed.emit(self._target)

    def redo(self) -> None:
        if self.armed() and self._history.redo():
            self.clear_transient()
            self._sync()
            self.changed.emit(self._target)

    # ── 표시 ──────────────────────────────────────────────────────────────────
    def _sync(self) -> None:
        """할 수 있는 것만 켠다 — **조용히 안 먹히는 버튼을 두지 않는다.**"""
        for _tool in self.TOOLS:
            _b = self._buttons[_tool.key]
            _b.setEnabled(self._tool_enabled(_tool))
            _b.setChecked(self.tool(_tool.group) == _tool.key)
        self._undo_btn.setEnabled(self.armed() and self._history.can_undo())
        self._redo_btn.setEnabled(self.armed() and self._history.can_redo())
        self._aim_label.setText(
            self._aim_text() if self.armed()
            else f"조준: 없음{'  — ' + self._hint if self._hint else ''}")
        self.canvas.set_interactive(self._interactive())
        self._sync_options()

    def decorate(self, canvas):
        """캔버스에 편집기 오버레이를 얹는다 (기본: 그대로 — 오버레이가 필요 없는 편집기도 있다)."""
        return canvas

    def clear_transient(self) -> None:
        """진행 중이던 조작(그리던 도형·드래그)을 버린다. 서브클래스가 자기 상태를 지운다."""
        self._clear_transient()
        self.preview.emit()

    # ── 포인터 (잠금·조준 검사를 여기서 한 번만 한다) ────────────────────────────
    def _press(self, x: int, y: int) -> None:
        if self.armed():
            self._on_press(x, y)
        else:
            self._on_unarmed_press(x, y)          # 조준 전이라도 선택(pick)은 열 수 있다

    def _move(self, x: int, y: int) -> None:
        if self.armed():
            self._on_move(x, y)

    def _release(self, x: int, y: int) -> None:
        if self.armed():
            self._on_release(x, y)

    def _right(self, x: int, y: int) -> None:
        if self.armed():
            self._on_right(x, y)

    # ── 서브클래스 훅 ──────────────────────────────────────────────────────────
    def _make_canvas(self) -> QWidget:
        """편집 대상을 보여줄 캔버스 (위 '캔버스 계약' 참조)."""
        raise NotImplementedError

    def _snapshot(self):
        """지금 편집 상태의 스냅샷 — 이력에 쌓을 값 (되돌릴 수 있는 만큼 담는다)."""
        raise NotImplementedError

    def _restore(self, snapshot) -> None:
        """스냅샷으로 편집 상태를 되돌린다."""
        raise NotImplementedError

    def _tool_enabled(self, tool: Tool) -> bool:
        """이 도구를 지금 쓸 수 있나 (기본: 조준이 있고 안 잠겼으면)."""
        return self.armed()

    def _interactive(self) -> bool:
        """캔버스가 포인터를 흘려보내야 하나 (기본: 편집 가능하면)."""
        return self.armed()

    def _aim_text(self) -> str:
        """상태바에 보일 조준 설명."""
        return "조준: 있음"

    def _build_status(self, row: QHBoxLayout) -> None:
        """상태바에 위젯을 얹는다 (밝기 등 — 기본 없음)."""

    def _build_options(self, row: QHBoxLayout) -> None:
        """옵션바에 위젯을 얹는다 (굵기·허용오차 등 — 기본 없음)."""

    def _sync_options(self) -> None:
        """현재 도구에 해당하는 옵션만 노출한다 (기본 없음)."""

    def _on_tool(self, tool: Tool) -> None:
        """도구가 바뀌었다 (기본 없음 — 축끼리 연동이 필요하면 서브클래스가 쓴다)."""

    def _on_aim(self, target) -> None:
        """조준이 바뀌었다 (기본 없음)."""

    def _clear_transient(self) -> None:
        """진행 중 조작 상태를 비운다 (기본 없음)."""

    def _on_press(self, x: int, y: int) -> None:
        """좌클릭 (조준·잠금 검사는 Base 가 이미 했다)."""

    def _on_unarmed_press(self, x: int, y: int) -> None:
        """조준이 **없을 때**의 좌클릭 — 기본 no-op. 편집기가 **비편집 상호작용(pick)** 을 열 수 있다.

        편집(paint/bbox)은 조준을 요구하지만, 클릭으로 대상을 **고르는** 건 조준 이전 단계다(고른 결과가
        곧 조준이 된다). 그 닭-달걀을 여기서 끊는다 — 안 그러면 트리에서 한 번 골라 조준을 만들기 전엔
        캔버스 클릭이 죽어 있다. 이 경로를 여는 편집기는 ``_interactive()`` 도 조준 없이 켜야 한다.
        """

    def _on_move(self, x: int, y: int) -> None:
        """포인터 이동."""

    def _on_release(self, x: int, y: int) -> None:
        """좌클릭 해제."""

    def _on_right(self, x: int, y: int) -> None:
        """우클릭."""


def _key_of(target) -> object:
    """조준 동일성 — ``key`` 가 바뀌면 다른 것을 편집 중이라 이력이 무의미해진다."""
    return None if target is None else getattr(target, "key", id(target))
