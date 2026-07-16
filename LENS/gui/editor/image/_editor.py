"""2D 라스터 편집기 — [`Editor_base`](../_base.py) 의 첫 서브클래스. 골격은 Base, 픽셀은 여기.

**이 파일은 도구를 조립하고 포인터를 흘릴 뿐이다.** 무엇을 어떻게 그리는지는 [`tool/`](tool/__init__.py)
이, 좌표가 무엇인지는 [`format/`](../format/__init__.py) 이 안다. 한때 여기 495줄에 상자·폴리곤·브러시·
핸들·기하가 다 있었고 같은 `tool("mode")` 스위치가 여섯 곳에서 반복됐다 — 도구 하나를 더하려면 여덟
군데를 고쳐야 해서, 폴리곤을 1급 데이터로 올릴 수가 없었다.

**도구는 산출물로 갈린다** — 영역([`_region`](tool/_region.py))이냐 픽셀([`_pixel`](tool/_pixel.py))이냐.
그래서 "어떤 데이터를 조준했나"가 곧 "어떤 도구가 붙나"이고, 그 판정은 도구가 스스로 든다(`Applies`) —
여기에 데이터 종류 if-체인이 없는 이유다.

`view` 만은 도구가 아니라 여기 산다. 아무것도 만들어 내지 않는 **중립 모드**라서다 — 조준이 없어도
클릭으로 객체를 고를 수 있어야 하므로 언제나 켜져 있고, 그 안에서 핸들을 잡는 일만 도구에 묻는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QToolButton, QWidget

from gui.widgets import Image_label, Snap_slider_row

from .._base import Editor_base
from .._tool import Tool
from . import _overlay
from .tool import Draw_tool, Pixel_tool, Region_tool

#: 핸들·다각형 닫기 판정 반경 (화면 px — 줌으로 나눠 원본 좌표로 환산한다).
_GRAB_PX = 12.0

#: 중립 모드 — 도구가 아니라 편집기가 든다 (아무것도 만들어 내지 않는다).
_VIEW = Tool("view", "mode", "👁", "보기", "V",
             "선택·핸들 조작 (캔버스를 안 건드린다)")


@dataclass
class Target:
    """편집기가 지금 조준한 것 — 호출 측(트리를 아는 계층)이 만들어 넘긴다.

    **무엇이 들었나가 어떤 도구가 붙는지를 정한다** — `bbox` 가 없으면 영역 도구가, `base` 가 없으면
    색 채우기가 조용히 사라진다(도구의 `Applies`/`Enabled` 가 그 판정을 든다).

    Attributes:
        raster: 편집할 2D 배열. **제자리에서** 고친다(트리가 든 그 배열).
        paint: 칠할 값 — 객체 라벨(obj_id+1) 또는 이진 mask 의 1.
        base: 색 채우기(magic wand)가 볼 배경 BGR. 없으면 그 모양이 꺼진다.
        bbox: 조준 객체의 상자 — [`format/bbox`](../format/bbox.py) 정준형 ``(2, D)``. 세 상태를 가른다:
            ``None`` = 영역 조작 자체가 없다(mask leaf) · 빈 것 = 아직 안 그렸다 · ``(2, D)`` = 있다.
        name: 조준 대상의 사람 이름 — 상태바에 보인다.
        key: 대상 식별 — 바뀌면 Base 가 이력을 비운다.
    """

    raster: np.ndarray
    paint:  int
    base:   np.ndarray | None = None
    bbox:   np.ndarray | None = None
    name:   str = ""
    key:    tuple = field(default=())


class Image_editor(Editor_base):
    """라스터 mask + 영역 편집기 (앱에 하나 — 대상만 갈아끼운다).

    Attributes:
        bbox_changed: 상자가 바뀜 (`format/bbox` 정준형) — 그리기·핸들·undo 모두 여기로 나간다.
        display_changed: 표시 옵션(밝기)이 바뀜 — 상위가 캔버스를 다시 그린다 (데이터는 안 바뀐다).
    """

    #: 도구가 선언한 버튼을 이어 붙인다 — 툴바·단축키·배타 그룹이 여기서 만들어진다.
    #: 순서가 곧 툴바 순서고, 그룹이 바뀌는 자리에 구분선이 선다 (mode … | shape …).
    TOOLS = (_VIEW,) + Region_tool.TOOLS + Pixel_tool.TOOLS

    bbox_changed    = Signal(object)
    display_changed = Signal()

    def __init__(self, parent=None) -> None:
        self._region = Region_tool(self)
        self._pixel = Pixel_tool(self)
        self._tools: tuple[Draw_tool, ...] = (self._region, self._pixel)
        self._owners: dict[str, Draw_tool] = {
            _t.key: _tool for _tool in self._tools for _t in _tool.TOOLS}
        self._grabbing: Draw_tool | None = None   # `view` 에서 핸들을 잡은 도구
        self._cursor: tuple[int, int] | None = None
        super().__init__(parent)

    # ── 골격 (Base 가 부른다) ──────────────────────────────────────────────────
    def _make_canvas(self) -> QWidget:
        return Image_label("표시할 데이터가 없습니다")

    def _build_status(self, row: QHBoxLayout) -> None:
        """표시 옵션 — 편집 잠금과 무관한 **보기 보정**이라 상태바에 산다(도구가 아니다)."""
        self._labels_btn = QToolButton()
        self._labels_btn.setText("🏷")
        self._labels_btn.setToolTip("객체 라벨 표시 — 상자 위에 obj_id · class_id 를 적는다")
        self._labels_btn.setCheckable(True)
        self._labels_btn.setChecked(True)
        self._labels_btn.setFixedSize(30, 26)
        self._labels_btn.clicked.connect(lambda _c: self.display_changed.emit())
        row.addWidget(self._labels_btn)

        # 밝기는 **끌어서 맞추는 값**이라 슬라이더고, 0(원본)에 **달라붙는다** — 손으로는 ±1 을 못 맞춘다.
        self._bright = Snap_slider_row(
            "밝기", -100, 100, 0, snaps=[0],
            tooltip="어두워 안 보이는 부분을 표시상으로만 들어올린다 "
                    "(저장 데이터·색 채우기 기준엔 영향 없음). 0 = 원본")
        self._bright.value_changed.connect(lambda _v: self.display_changed.emit())
        row.addWidget(self._bright)

    def _build_options(self, row: QHBoxLayout) -> None:
        for _tool in self._tools:
            _tool.build_options(row)

    def _install_shortcuts(self) -> None:
        super()._install_shortcuts()
        for _tool in self._tools:
            _tool.install_shortcuts()

    def _sync_options(self) -> None:
        for _tool in self._tools:
            _tool.sync_options()

    # ── 도구가 쓰는 서비스 ─────────────────────────────────────────────────────
    def pointer(self) -> tuple[int, int] | None:
        """마지막 포인터 위치 (원본 픽셀) — 미리보기가 "여기까지"를 그릴 때 쓴다.

        ``cursor`` 가 아닌 이유 — `QWidget.cursor()` 가 이미 있다(마우스 커서 **모양**을 내는 Qt 메서드).
        같은 이름을 쓰면 Qt 내부가 모양 대신 좌표를 받는다.
        """
        return self._cursor

    def grab_radius(self) -> float:
        """핸들·다각형 닫기 판정 반경 — **화면에서** 일정하게 (줌을 보정한다)."""
        _scale = self.canvas.effective_zoom() or 1.0
        return max(6.0, _GRAB_PX / _scale)

    def set_box(self, box: np.ndarray) -> None:
        """조준 객체의 상자를 갈아끼운다 — 그리기·핸들·폴리곤이 모두 여기로 모인다."""
        self._t.bbox = np.asarray(box, float)
        self.bbox_changed.emit(self._t.bbox.copy())
        self.preview.emit()

    def preview_box(self) -> np.ndarray | None:
        """지금 그리는 중인 상자 (아니면 조준 객체의 확정 상자) — 상위가 합성에 넘긴다."""
        _drawing = self._region.preview_box()
        if _drawing is not None:
            return _drawing
        return self._t.bbox if self._t is not None else None

    # ── 도구 조립 ─────────────────────────────────────────────────────────────
    def _owner(self, key: str) -> Draw_tool | None:
        """이 버튼을 든 도구 (``view`` 는 도구가 아니라 None)."""
        return self._owners.get(key)

    def _enabled(self, target, key: str) -> bool:
        _tool = self._owner(key)
        return True if _tool is None else _tool.Enabled(target, key)   # view 는 언제나

    def _tool_enabled(self, tool: Tool) -> bool:
        return self.armed() and self._enabled(self._t, tool.key)

    def _fallback(self, target, group: str) -> str:
        """이 그룹에서 지금 쓸 수 있는 첫 도구 (mode 면 ``view``, shape 면 ``brush``)."""
        return next(_t.key for _t in self.TOOLS
                    if _t.group == group and self._enabled(target, _t.key))

    def _on_tool(self, tool: Tool) -> None:
        """모양을 고르면 곧바로 그릴 수 있게 조작을 ``paint`` 로 (이미 칠하는 중이면 유지)."""
        if tool.group == "shape" and self.tool("mode") not in ("paint", "erase"):
            self._current["mode"] = "paint"

    def _on_aim(self, target) -> None:
        """못 쓰는 도구에 머물지 않는다 — 조준이 바뀌며 불가능해진 선택은 그 그룹의 첫 도구로 내린다.

        같은 라스터 안에서 **객체만 옮겨간 경우**는 이력이 유지되므로(그게 요점이다) 새 객체의 상자를
        baseline 으로 한 칸 적재한다 — 안 그러면 그 객체의 첫 영역 편집이 되돌아갈 곳을 못 찾는다.
        """
        if target is None:
            self._current["mode"] = "view"
        else:
            for _group in ("mode", "shape"):
                if not self._enabled(target, self.tool(_group)):
                    self._current[_group] = self._fallback(target, _group)

        _top = self._history.current()
        if target is not None and _top is not None and _top[1] != target.name:
            self._history.commit()

    def _aim_text(self) -> str:
        _t = self._t
        _what = _t.name or f"라벨 {_t.paint}"
        return f"조준: {_what}  (라벨 {_t.paint})"

    # ── 이력 — 라스터와 상자를 **함께** 든다 ────────────────────────────────────
    def _snapshot(self):
        """되돌릴 수 있는 만큼 담는다 — 픽셀만 담으면 영역 편집이 조용히 안 되돌려진다.

        **소유자(`name`)도 함께 담는다.** 이력의 단위는 라스터라(같은 라벨맵을 고치는 동안 객체를 옮겨
        다녀도 이력이 산다) 스택 안에는 *다른 객체를 겨눴을 때* 찍힌 칸이 섞인다 — 그 칸의 상자는 지금
        객체의 것이 아니므로 되돌리면 안 된다.
        """
        _t = self._t
        return (_t.raster.copy(), _t.name, None if _t.bbox is None else _t.bbox.copy())

    def _restore(self, snapshot) -> None:
        _raster, _owner, _box = snapshot
        self._t.raster[...] = _raster                # 제자리 — 트리가 든 배열과 같은 놈이다
        if _box is None or _owner != self._t.name:   # 남의 상자는 안 되돌린다
            return
        _now = self._t.bbox
        if _now is not None and np.array_equal(_box, _now):
            return
        self._t.bbox = _box.copy()
        self.bbox_changed.emit(_box.copy())

    # ── 표시 ──────────────────────────────────────────────────────────────────
    def show_labels(self) -> bool:
        """객체 라벨을 캔버스에 적을까 (상위가 합성에 넘길 텍스트를 정할 때 묻는다)."""
        return self._labels_btn.isChecked()

    def brightness(self) -> int:
        """표시 밝기 보정값 (상위가 합성 결과에 적용한다 — 데이터는 안 바뀐다)."""
        return self._bright.value()

    def decorate(self, canvas: np.ndarray) -> np.ndarray:
        """합성된 캔버스에 **지금 하려는 것**을 얹는다 (밝기 · 미리보기 · 커서 · 핸들).

        합성 결과는 매 그리기마다 새로 만들어지므로 제자리에 얹는다 (데이터가 아니라 표시본이다).
        붙는 도구 전부에게 묻는다 — 그리는 중이 아닌 도구는 스스로 아무것도 안 그린다.
        """
        _out = _overlay.brightness(canvas, self.brightness())
        if not self.armed():
            return _out
        for _tool in self._tools:
            if _tool.Applies(self._t):
                _tool.decorate(_out)
        return _out

    # ── 포인터 ────────────────────────────────────────────────────────────────
    def _interactive(self) -> bool:
        """조준이 없어도 이미지가 있으면 포인터를 받는다 — **view 모드의 pick(객체 고르기)** 때문.

        편집은 여전히 armed 여야 하지만, 클릭으로 객체를 고르는 건 편집 전 단계라 조준이 필요 없다.
        이미지가 떠 있으면(``source_size``) 흘려보낸다.
        """
        return self.armed() or self.canvas.source_size() is not None

    def _on_press(self, x: int, y: int) -> None:
        self._cursor = (x, y)
        if self.tool("mode") == _VIEW.key:
            self._view_press(x, y)
            return
        _tool = self._owner(self.tool("mode"))
        if _tool is not None:
            _tool.press(x, y)

    def _on_unarmed_press(self, x: int, y: int) -> None:
        """조준 없는 클릭 — view 면 pick 만 한다(고른 객체가 곧 조준이 된다). 편집 모드는 무시."""
        if self.tool("mode") == _VIEW.key:
            self._view_press(x, y)

    def _view_press(self, x: int, y: int) -> None:
        """보기 — 핸들을 잡거나, 아무도 안 잡으면 **거기 있는 것을 골라달라** 한다.

        **Shift 는 선택에 더한다** — 캔버스에서 여러 객체를 집어 바로 병합(`M`)하려면 트리로 손이 갈
        이유가 없어야 한다. Shift 중엔 핸들을 안 잡는다(모으는 중이지 고치는 중이 아니다).
        """
        _additive = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        if not _additive:
            for _tool in self._tools:
                if _tool.Applies(self._t) and _tool.grab(x, y):
                    self._grabbing = _tool
                    return
        self.picked.emit(x, y, _additive)         # 트리를 아는 상위가 답한다

    def _on_move(self, x: int, y: int) -> None:
        self._cursor = (x, y)
        _tool = self._grabbing or self._owner(self.tool("mode"))
        if _tool is not None:
            _tool.move(x, y)

    def _on_release(self, x: int, y: int) -> None:
        _tool = self._grabbing or self._owner(self.tool("mode"))
        self._grabbing = None
        if _tool is not None:
            _tool.release(x, y)

    def _on_right(self, x: int, y: int) -> None:
        """우클릭 — 도구가 **그리던 마지막 동작만** 취소한다. 안 받으면 진행 중 조작을 버린다."""
        _tool = self._owner(self.tool("mode"))
        if _tool is None or not _tool.right(x, y):
            self.clear_transient()

    def _clear_transient(self) -> None:
        self._grabbing = None
        self._cursor = None
        for _tool in self._tools:
            _tool.clear_transient()

    # ── 내부 ──────────────────────────────────────────────────────────────────
    @property
    def _t(self) -> Target:
        return self.target()
