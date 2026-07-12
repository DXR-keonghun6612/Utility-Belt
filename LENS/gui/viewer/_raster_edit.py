"""mask 편집기 — **앱에 하나만 산다.** 노드를 고르면 그 대상으로 **조준**할 뿐이다.

예전엔 노드를 고를 때마다 편집기를 새로 만들었다. 그런데 편집 대상(``segment``)은 **프레임의 것**이고
객체는 그 안의 **라벨**일 뿐이라, 객체마다 편집기를 두면 같은 라스터의 사본이 여럿 생기고 — 객체를
옮길 때마다 **undo 이력과 편집 모드가 날아갔다**. 라벨링은 객체를 옮겨가며 계속 칠하는 작업인데.

그래서 편집기는 하나다:

- **툴바 상태(모드·모양·굵기·허용오차)는 계속 산다** — 객체를 옮겨도, stem 을 넘어가도.
- **undo 는 라스터 단위** — 조준한 라스터가 바뀌면(다른 stem·다른 leaf) 비운다. 같은 라스터를 고치는
  동안엔 객체를 옮겨 다녀도 이력이 유지된다.
- **조준(``Target.paint``)이 곧 "누구의 mask 인가"** — 객체를 고르면 그 라벨(obj_id+1)이 찍힌다.
  조준이 없으면 칠할 수 없다(누구 것인지 모르는 mask 는 만들 수 없다 — 조용히 아무 라벨이나 찍지 않는다).

라스터는 **제자리에서** 고친다 — ``Target.raster`` 는 트리가 든 바로 그 배열이라, 칠하면 그게 곧
데이터다(사본을 들고 나중에 합치는 옛 방식은 진실을 둘로 만들었다).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import Int_slider_row

from ._fill import magic_wand

_UNDO_LIMIT = 30


@dataclass
class Target:
    """편집기가 지금 조준한 것 — 호출 측(`Data_view`)이 트리를 보고 만든다.

    Attributes:
        raster: 편집할 2D 배열. **제자리에서** 고친다(트리가 든 그 배열).
        paint: 칠할 값 — 객체 라벨(obj_id+1) 또는 이진 mask 의 1.
        base: 색 채우기(magic wand)가 볼 배경 BGR (없으면 그 모드가 꺼진다).
        bbox: 객체를 조준했으면 그 상자(없으면 ``[]``). ``None`` 이면 bbox 모드 자체가 없다.
        key: 대상 식별 — 바뀌면 undo 이력을 비운다.
    """

    raster: np.ndarray
    paint:  int
    base:   np.ndarray | None = None
    bbox:   list | None = None
    key:    tuple = field(default=())


class Mask_editor(QWidget):
    """캔버스 위의 mask/bbox 편집기 (앱에 하나 — 대상만 갈아끼운다).

    Attributes:
        changed: 라스터가 확정 편집됨 ``(raster)`` — 상위가 store 에 저장한다.
        bbox_changed: 상자를 드래그로 그림 ``([x0,y0,x1,y1])``.
        preview: 진행 중 미리보기가 바뀜 — 상위가 캔버스를 다시 합성한다.
    """

    changed      = Signal(object)
    bbox_changed = Signal(object)
    preview      = Signal()

    def __init__(self, canvas, parent=None) -> None:
        """Args:
        canvas: ``Image_label`` — 마우스 신호를 여기서 받는다.
        """
        super().__init__(parent)
        self._canvas = canvas
        self._t: Target | None = None
        self._locked = False
        self._undo: list[np.ndarray] = []
        self._redo: list[np.ndarray] = []

        self._mode = "view"                     # view / paint / erase / bbox / wand
        self._shape = "brush"                   # brush / polygon / circle
        self._p0: tuple[int, int] | None = None
        self._box_p0: tuple[int, int] | None = None
        self._poly: list[tuple[int, int]] = []
        self._cursor: tuple[int, int] | None = None
        self._stroke = False

        self._build()
        canvas.mouse_pressed.connect(self._on_press)
        canvas.mouse_moved.connect(self._on_move)
        canvas.mouse_released.connect(self._on_release)
        canvas.mouse_right_pressed.connect(self._on_right)

    # ── 조준 ──────────────────────────────────────────────────────────────────
    def aim(self, target: Target | None, *, hint: str = "") -> None:
        """대상을 갈아끼운다 — **툴바 상태는 유지**하고, 라스터가 바뀔 때만 undo 를 비운다.

        Args:
            target: 새 조준 대상 (없으면 편집 불가 — 왜인지는 ``hint`` 로 보여준다).
            hint: 조준이 없을 때 사용자에게 보일 이유 ("segment 를 체크하세요" 등).
        """
        if target is None or self._t is None or target.key != self._t.key:
            self._undo.clear()
            self._redo.clear()
        self._t = target
        self._hint = hint
        self._clear_transient()
        if target is None:
            self._mode = "view"
        elif target.bbox is None and self._mode == "bbox":     # 못 그리는 모드에 머물지 않는다
            self._mode = "view"
        self._sync()

    def target(self) -> Target | None:
        return self._t

    def set_locked(self, locked: bool) -> None:
        """편집 잠금 (백그라운드 작업 중) — 보기는 유지하고 캔버스 편집만 막는다."""
        self._locked = locked
        self.setEnabled(not locked)
        self._sync()

    # ── 미리보기 ──────────────────────────────────────────────────────────────
    def preview_raster(self) -> np.ndarray | None:
        """진행 중 도형까지 얹은 라스터 (다각형·원을 그리는 중이면 사본, 아니면 원본)."""
        if self._t is None:
            return None
        if self._shape == "polygon" and len(self._poly) >= 3:
            return self._stamped(self._poly_mask(self._poly))
        if self._shape == "circle" and self._p0 and self._cursor:
            return self._stamped(self._circle_mask(self._p0, self._cursor))
        return self._t.raster

    def preview_box(self) -> list | None:
        """그리는 중인 상자 (드래그 중이 아니면 조준한 객체의 확정 상자)."""
        if self._box_p0 is not None and self._cursor is not None:
            _x0, _y0 = self._box_p0
            _x1, _y1 = self._cursor
            return [min(_x0, _x1), min(_y0, _y1), max(_x0, _x1), max(_y0, _y1)]
        return self._t.bbox if self._t else None

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(2)

        _row = QHBoxLayout()
        self._mode_btns: dict[str, QToolButton] = {}
        _mg = QButtonGroup(self)
        for _key, _text, _tip in (
                ("view",  "👁", "보기 — 캔버스를 안 건드린다"),
                ("paint", "✏", "그리기 — 조준한 객체의 라벨로 칠한다"),
                ("erase", "🧽", "지우기 — 배경(0)으로 만든다"),
                ("bbox",  "▭", "bbox — 드래그로 조준한 객체의 상자를 그린다"),
                ("wand",  "✨", "색 채우기 — 클릭한 색과 비슷한 영역을 한 번에 (magic wand)")):
            _b = QToolButton()
            _b.setText(_text)
            _b.setToolTip(_tip)
            _b.setCheckable(True)
            _b.clicked.connect(lambda _c=False, k=_key: self._set_mode(k))
            _mg.addButton(_b)
            self._mode_btns[_key] = _b
            _row.addWidget(_b)

        _row.addWidget(QLabel("│"))
        self._shape_btns: dict[str, QToolButton] = {}
        _sg = QButtonGroup(self)
        for _key, _text, _tip in (("brush", "🖌", "브러시 — 드래그로 칠한다"),
                                  ("polygon", "⬠", "다각형 — 클릭으로 점, 우클릭으로 확정"),
                                  ("circle", "◯", "원 — 중심에서 드래그")):
            _b = QToolButton()
            _b.setText(_text)
            _b.setToolTip(_tip)
            _b.setCheckable(True)
            _b.clicked.connect(lambda _c=False, k=_key: self._set_shape(k))
            _sg.addButton(_b)
            self._shape_btns[_key] = _b
            _row.addWidget(_b)

        _row.addWidget(QLabel("│"))
        self._aim_label = QLabel()
        self._aim_label.setStyleSheet("color: #888;")
        _row.addWidget(self._aim_label)

        _row.addStretch(1)
        self._undo_btn = QPushButton("↶")
        self._undo_btn.setToolTip("실행취소")
        self._undo_btn.clicked.connect(self.undo)
        self._redo_btn = QPushButton("↷")
        self._redo_btn.setToolTip("다시실행")
        self._redo_btn.clicked.connect(self.redo)
        _row.addWidget(self._undo_btn)
        _row.addWidget(self._redo_btn)
        _lay.addLayout(_row)

        self._size = Int_slider_row("굵기 / 반경", 1, 120, 12,
                                    tooltip="브러시 굵기 · 색 채우기 반경(클릭점 중심 원)")
        _lay.addWidget(self._size)
        self._tol = Int_slider_row("색 허용오차", 1, 120, 24,
                                   tooltip="색 채우기 — seed 색 대비 허용 범위 (클수록 넓게 번진다)")
        _lay.addWidget(self._tol)

        self._hint = ""
        self._sync()

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._clear_transient()
        self._sync()

    def _set_shape(self, shape: str) -> None:
        self._shape = shape
        self._clear_transient()
        if self._t is not None and self._mode not in ("paint", "erase"):
            self._mode = "paint"                 # 모양을 고르면 곧바로 그릴 수 있게
        self._sync()

    def _sync(self) -> None:
        """할 수 있는 것만 켠다 — **조용히 안 먹히는 버튼을 두지 않는다.**"""
        _t = self._t
        _armed = _t is not None and not self._locked
        _can_box = _armed and _t.bbox is not None
        _can_wand = _armed and _t.base is not None

        for _k in ("paint", "erase"):
            self._mode_btns[_k].setEnabled(_armed)
        self._mode_btns["bbox"].setEnabled(_can_box)
        self._mode_btns["wand"].setEnabled(_can_wand)
        for _k, _b in self._mode_btns.items():
            _b.setChecked(self._mode == _k)
        for _k, _b in self._shape_btns.items():
            _b.setChecked(self._shape == _k)
            _b.setEnabled(_armed)

        self._size.setVisible(self._mode != "view")
        self._tol.setVisible(self._mode == "wand")       # 색 채우기일 때만 의미가 있다
        self._canvas.set_interactive(_armed and self._mode != "view")
        self._undo_btn.setEnabled(bool(self._undo) and _armed)
        self._redo_btn.setEnabled(bool(self._redo) and _armed)
        self._aim_label.setText(
            f"조준: 라벨 {_t.paint}" if _t is not None
            else f"조준: 없음{'  — ' + self._hint if self._hint else ''}")

    def _clear_transient(self) -> None:
        self._p0 = None
        self._box_p0 = None
        self._poly = []
        self._cursor = None
        self._stroke = False
        self.preview.emit()

    # ── 편집 ──────────────────────────────────────────────────────────────────
    def _value(self) -> int:
        """칠할 값 — 지우기는 0(배경), 그리기는 **조준한 대상의 값**."""
        return 0 if self._mode == "erase" else int(self._t.paint)

    def _stamped(self, region: np.ndarray) -> np.ndarray:
        """``region`` 을 현재 값으로 찍은 **사본** (미리보기 — 원본은 안 건드린다)."""
        _out = self._t.raster.copy()
        _out[region > 0] = np.uint8(self._value())
        return _out

    def _apply(self, region: np.ndarray) -> None:
        """확정 — undo 를 쌓고 라스터를 제자리 갱신, ``changed`` 로 알린다."""
        if self._t is None or not region.any():
            return
        self._push_undo()
        self._t.raster[region > 0] = np.uint8(self._value())
        self._clear_transient()
        self._sync()
        self.changed.emit(self._t.raster)

    def _push_undo(self) -> None:
        self._undo.append(self._t.raster.copy())
        del self._undo[:-_UNDO_LIMIT]
        self._redo.clear()

    def undo(self) -> None:
        if not self._undo or self._t is None:
            return
        self._redo.append(self._t.raster.copy())
        self._t.raster[...] = self._undo.pop()     # 제자리 — 트리가 든 배열과 같은 놈이다
        self._clear_transient()
        self._sync()
        self.changed.emit(self._t.raster)

    def redo(self) -> None:
        if not self._redo or self._t is None:
            return
        self._undo.append(self._t.raster.copy())
        self._t.raster[...] = self._redo.pop()
        self._clear_transient()
        self._sync()
        self.changed.emit(self._t.raster)

    # ── 도형 ──────────────────────────────────────────────────────────────────
    def _blank(self) -> np.ndarray:
        return np.zeros(self._t.raster.shape[:2], np.uint8)

    def _brush_mask(self, a, b) -> np.ndarray:
        _m = self._blank()
        cv2.line(_m, a, b, 1, thickness=max(1, self._size.value()))
        return _m

    def _circle_mask(self, center, edge) -> np.ndarray:
        _m = self._blank()
        _r = int(round(float(np.hypot(edge[0] - center[0], edge[1] - center[1]))))
        if _r > 0:
            cv2.circle(_m, center, _r, 1, -1)
        return _m

    def _poly_mask(self, pts) -> np.ndarray:
        _m = self._blank()
        cv2.fillPoly(_m, [np.array(pts, np.int32)], 1)
        return _m

    # ── 마우스 ────────────────────────────────────────────────────────────────
    def _idle(self) -> bool:
        return self._t is None or self._locked or self._mode == "view"

    def _on_press(self, x: int, y: int) -> None:
        if self._idle():
            return
        if self._mode == "bbox":
            self._box_p0 = (x, y)
            self._cursor = (x, y)
            self.preview.emit()
            return
        if self._mode == "wand":
            if self._t.base is not None:
                _region = magic_wand(self._t.base, (x, y),
                                     self._tol.value(), self._size.value())
                if _region is not None:
                    self._apply(_region)
            return
        if self._shape == "brush":
            self._stroke = True
            self._p0 = (x, y)
            self._push_undo()
            self._t.raster[self._brush_mask((x, y), (x, y)) > 0] = np.uint8(self._value())
            self.preview.emit()
        elif self._shape == "circle":
            self._p0 = (x, y)
            self._cursor = (x, y)
        elif self._shape == "polygon":
            self._poly.append((x, y))
            self._cursor = (x, y)
            self.preview.emit()

    def _on_move(self, x: int, y: int) -> None:
        if self._idle() or self._mode == "wand":
            return
        self._cursor = (x, y)
        if self._mode == "bbox":
            if self._box_p0 is not None:
                self.preview.emit()
            return
        if self._stroke and self._p0 is not None:      # 브러시 — 지나간 자리를 즉시 칠한다
            self._t.raster[self._brush_mask(self._p0, (x, y)) > 0] = np.uint8(self._value())
            self._p0 = (x, y)
        self.preview.emit()

    def _on_release(self, x: int, y: int) -> None:
        if self._idle() or self._mode == "wand":
            return
        if self._mode == "bbox":
            if self._box_p0 is None:
                return
            _x0, _y0 = self._box_p0
            _box = [min(_x0, x), min(_y0, y), max(_x0, x), max(_y0, y)]
            self._box_p0 = None
            if _box[2] - _box[0] < 2 or _box[3] - _box[1] < 2:   # 클릭 오인 방지
                self.preview.emit()
                return
            self._t.bbox = _box
            self.bbox_changed.emit(_box)
            self.preview.emit()
            return
        if self._stroke:                               # 브러시 — 이미 칠했다. 확정만.
            self._stroke = False
            self._p0 = None
            self._sync()
            self.changed.emit(self._t.raster)
            return
        if self._shape == "circle" and self._p0 is not None:
            self._apply(self._circle_mask(self._p0, (x, y)))

    def _on_right(self, x: int, y: int) -> None:
        """우클릭 — 다각형이면 **확정**(3점 이상) 또는 마지막 점 취소, 그 외엔 진행 상태 취소."""
        if not self._idle() and self._shape == "polygon" and self._poly:
            if len(self._poly) >= 3:
                self._apply(self._poly_mask(self._poly))
            else:
                self._poly.pop()
                self.preview.emit()
            return
        self._clear_transient()
