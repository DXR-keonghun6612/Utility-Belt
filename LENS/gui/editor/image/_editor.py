"""2D 라스터 편집기 — [`Editor_base`](../_base.py) 의 첫 서브클래스. 골격은 Base, 픽셀은 여기.

**편집은 두 축의 곱이다** — 조작(`paint`/`erase`)이 칠할지 지울지를, 모양(`brush`/`polygon`/`circle`/
`fill`)이 어떤 도형으로 칠할지를 정한다. 그래서 "색 비슷한 영역을 **지우기**"(erase × fill)가 조합으로
공짜로 나온다. 한때 `fill`(magic wand)을 조작 축으로 올린 적이 있는데, 그 순간 곱이 깨져 지울 수 없게 됐다.

`view`·`bbox` 는 mask 를 안 건드리는 별도 조작이라 모양을 참조하지 않는다.

라스터는 **제자리에서** 고친다 — `Target.raster` 는 트리가 든 바로 그 배열이라 칠하면 그게 곧 데이터다
(사본을 들고 나중에 합치면 진실이 둘이 된다). 대신 이력이 사본을 든다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QToolButton,
    QWidget,
)

from gui.widgets import Image_label, Snap_slider_row

from .._base import Editor_base
from .._tool import Tool
from . import _geom, _overlay
from ._fill import magic_wand

#: 핸들·다각형 닫기 판정 반경 (화면 px — 줌으로 나눠 원본 좌표로 환산한다).
_GRAB_PX = 12.0


@dataclass
class Target:
    """편집기가 지금 조준한 것 — 호출 측(트리를 아는 계층)이 만들어 넘긴다.

    Attributes:
        raster: 편집할 2D 배열. **제자리에서** 고친다(트리가 든 그 배열).
        paint: 칠할 값 — 객체 라벨(obj_id+1) 또는 이진 mask 의 1.
        base: 색 채우기(magic wand)가 볼 배경 BGR. 없으면 그 모양이 꺼진다.
        bbox: 객체를 조준했으면 그 상자(빈 리스트 = 아직 안 그림). ``None`` 이면 bbox 조작 자체가 없다.
        name: 조준 대상의 사람 이름 — 상태바에 보인다.
        key: 대상 식별 — 바뀌면 Base 가 이력을 비운다.
    """

    raster: np.ndarray
    paint:  int
    base:   np.ndarray | None = None
    bbox:   list | None = None
    name:   str = ""
    key:    tuple = field(default=())


class Image_editor(Editor_base):
    """라스터 mask + bbox 편집기 (앱에 하나 — 대상만 갈아끼운다).

    Attributes:
        bbox_changed: 상자가 바뀜 ``([x0,y0,x1,y1])`` — 그리기·핸들 드래그·undo 모두 여기로 나간다.
        display_changed: 표시 옵션(밝기)이 바뀜 — 상위가 캔버스를 다시 그린다 (데이터는 안 바뀐다).
    """

    TOOLS = (
        Tool("view",  "mode", "👁", "보기",   "V",
             "선택·bbox 핸들 조작 (캔버스를 안 건드린다)"),
        Tool("bbox",  "mode", "▭", "bbox",   "R",
             "드래그로 조준한 객체의 상자를 그린다"),
        Tool("paint", "mode", "✏", "그리기", "D",
             "고른 모양으로 조준한 객체의 라벨을 칠한다"),
        Tool("erase", "mode", "🧽", "지우기", "E",
             "고른 모양으로 지운다 (배경 0 으로)"),
        Tool("brush",   "shape", "🖌", "브러시", "B",
             "드래그로 자유롭게 칠한다 (반경 = 굵기)"),
        Tool("polygon", "shape", "⬠", "다각형", "P",
             "꼭짓점을 클릭하고 첫 점 근처를 클릭해 닫는다 (우클릭 = 마지막 점 취소)"),
        Tool("circle",  "shape", "◯", "원",     "C",
             "중심을 클릭한 뒤 한 번 더 클릭해 반지름을 정한다 (우클릭 = 중심 취소)"),
        Tool("fill",    "shape", "🪣", "색 채우기", "F",
             "클릭점 반경 원 안에서 색이 비슷한 영역을 채운다 (magic wand — 지우기와도 곱해진다)"),
    )

    bbox_changed    = Signal(object)
    display_changed = Signal()

    def __init__(self, parent=None) -> None:
        self._p0: tuple[int, int] | None = None       # 원 중심 / bbox 드래그 시작점
        self._poly: list[tuple[int, int]] = []        # 다각형 꼭짓점
        self._cursor: tuple[int, int] | None = None   # 커서 미리보기 위치
        self._stroke = False                          # 브러시 드래그 중
        self._anchor: tuple[int, int] | None = None   # 코너 드래그 — 고정될 반대 코너
        self._edge: str | None = None                 # 변 중점 드래그 중인 변
        self._edge_box: list | None = None            # 변 드래그 시작 시점의 상자
        self._dragged = False                         # 핸들 드래그로 실제 이동이 있었나
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

    def show_labels(self) -> bool:
        """객체 라벨을 캔버스에 적을까 (상위가 합성에 넘길 텍스트를 정할 때 묻는다)."""
        return self._labels_btn.isChecked()

    def _build_options(self, row: QHBoxLayout) -> None:
        self._size = _spin("굵기", 1, 200, 12, "브러시 반경(px)  [ / ] 로 -/+", self._redraw)
        self._radius = _spin("채우기 반경", 1, 500, 30,
                             "색 채우기를 가둘 원형 ROI 반경(px) — 굵기와 독립", self._redraw)
        self._tol = _spin("허용", 0, 255, 24,
                          "색 채우기 허용오차 — 클수록 넓게 번진다", None)
        for _w in (self._size, self._radius, self._tol):
            row.addWidget(_w)

    def _install_shortcuts(self) -> None:
        super()._install_shortcuts()
        self.bind("[", lambda: self._size.set_value(self._size.value() - 2))
        self.bind("]", lambda: self._size.set_value(self._size.value() + 2))

    def _sync_options(self) -> None:
        """현재 도구에 **의미 있는 옵션만** 보인다 — 안 먹는 입력칸을 두지 않는다."""
        _painting = self.tool("mode") in ("paint", "erase")
        _shape = self.tool("shape")
        self._size.setVisible(_painting and _shape == "brush")
        self._radius.setVisible(_painting and _shape == "fill")
        self._tol.setVisible(_painting and _shape == "fill")

    def _interactive(self) -> bool:
        """조준이 없어도 이미지가 있으면 포인터를 받는다 — **view 모드의 pick(객체 고르기)** 때문.

        편집(paint/bbox)은 여전히 armed 여야 하지만(그건 ``_on_press`` 가 든다), 클릭으로 객체를 고르는
        건 편집 전 단계라 조준이 필요 없다. 이미지가 떠 있으면(``source_size``) 흘려보낸다.
        """
        return self.armed() or self.canvas.source_size() is not None

    def _on_unarmed_press(self, x: int, y: int) -> None:
        """조준 없는 클릭 — view 모드면 pick 만 한다(고른 객체가 곧 조준이 된다). 편집 모드는 무시."""
        if self.tool("mode") not in ("paint", "erase", "bbox"):
            self._view_press(x, y)

    def _tool_enabled(self, tool: Tool) -> bool:
        if not self.armed():
            return False
        if tool.key == "bbox":
            return self._t.bbox is not None          # 상자를 가질 수 없는 대상(mask leaf)
        if tool.key == "fill":
            return self._t.base is not None          # 색을 볼 배경이 없으면 채울 수 없다
        return True

    def _on_tool(self, tool: Tool) -> None:
        """모양을 고르면 곧바로 그릴 수 있게 조작을 ``paint`` 로 (이미 칠하는 중이면 유지)."""
        if tool.group == "shape" and self.tool("mode") not in ("paint", "erase"):
            self._current["mode"] = "paint"

    def _on_aim(self, target) -> None:
        """못 쓰는 도구에 머물지 않는다 — 조준이 바뀌며 불가능해진 조작은 ``view`` 로 내린다.

        같은 라스터 안에서 **객체만 옮겨간 경우**는 이력이 유지되므로(그게 요점이다) 새 객체의 상자를
        baseline 으로 한 칸 적재한다 — 안 그러면 그 객체의 첫 bbox 편집이 되돌아갈 곳을 못 찾는다.
        """
        _mode = self.tool("mode")
        if target is None or (_mode == "bbox" and target.bbox is None):
            self._current["mode"] = "view"
        elif self.tool("shape") == "fill" and target.base is None:
            self._current["shape"] = "brush"

        _top = self._history.current()
        if target is not None and _top is not None and _top[1] != target.name:
            self._history.commit()

    def _aim_text(self) -> str:
        _t = self._t
        _what = _t.name or f"라벨 {_t.paint}"
        return f"조준: {_what}  (라벨 {_t.paint})"

    # ── 이력 — 라스터와 bbox 를 **함께** 든다 ───────────────────────────────────
    def _snapshot(self):
        """되돌릴 수 있는 만큼 담는다 — 픽셀만 담으면 상자 편집이 조용히 안 되돌려진다.

        **소유자(`name`)도 함께 담는다.** 이력의 단위는 라스터라(같은 라벨맵을 고치는 동안 객체를 옮겨
        다녀도 이력이 산다) 스택 안에는 *다른 객체를 겨눴을 때* 찍힌 칸이 섞인다 — 그 칸의 bbox 는 지금
        객체의 것이 아니므로 되돌리면 안 된다.
        """
        _t = self._t
        return (_t.raster.copy(), _t.name, None if _t.bbox is None else list(_t.bbox))

    def _restore(self, snapshot) -> None:
        _raster, _owner, _bbox = snapshot
        self._t.raster[...] = _raster                # 제자리 — 트리가 든 배열과 같은 놈이다
        if _bbox is not None and _owner == self._t.name and _bbox != self._t.bbox:
            self._t.bbox = list(_bbox)
            self.bbox_changed.emit(list(_bbox))

    # ── 표시 ──────────────────────────────────────────────────────────────────
    def brightness(self) -> int:
        """표시 밝기 보정값 (상위가 합성 결과에 적용한다 — 데이터는 안 바뀐다)."""
        return self._bright.value()

    def decorate(self, canvas: np.ndarray) -> np.ndarray:
        """합성된 캔버스에 **지금 하려는 것**을 얹는다 (밝기 · 미리보기 도형 · 커서 · 핸들).

        합성 결과는 매 그리기마다 새로 만들어지므로 제자리에 얹는다 (데이터가 아니라 표시본이다).
        """
        _out = _overlay.brightness(canvas, self.brightness())
        if not self.armed():
            return _out

        _mode, _shape = self.tool("mode"), self.tool("shape")
        if _mode in ("paint", "erase"):
            if _shape == "polygon" and self._poly:
                _overlay.preview_polygon(
                    _out, self._poly + ([self._cursor] if self._cursor else []))
            elif _shape == "circle" and self._p0 and self._cursor:
                _overlay.preview_circle(_out, self._p0, self._radius_to(self._cursor))
            elif _shape in ("brush", "fill") and self._cursor:
                _overlay.cursor(_out, self._cursor,
                                self._size.value() if _shape == "brush"
                                else self._radius.value())
        elif _mode == "view" and self._t.bbox:
            _overlay.handles(_out, _geom.corners(self._t.bbox),
                             _geom.edge_midpoints(self._t.bbox))
        return _out

    def preview_box(self) -> list | None:
        """지금 그리는 중인 상자 (아니면 조준한 객체의 확정 상자) — 상위가 합성에 넘긴다."""
        if self.tool("mode") == "bbox" and self._p0 and self._cursor:
            return _geom.rect_from(self._p0, self._cursor)
        return self._t.bbox if self._t is not None else None

    # ── 포인터 ────────────────────────────────────────────────────────────────
    def _on_press(self, x: int, y: int) -> None:
        _mode = self.tool("mode")
        if _mode in ("paint", "erase"):
            self._paint_press(x, y)
        elif _mode == "bbox":
            self._p0 = (x, y)
            self._cursor = (x, y)
            self.preview.emit()
        else:
            self._view_press(x, y)

    def _paint_press(self, x: int, y: int) -> None:
        _shape = self.tool("shape")
        if _shape == "brush":
            self._stroke = True
            self._p0 = (x, y)
            self._stamp(self._brush_region((x, y), (x, y)))       # 클릭 한 번도 점을 찍는다
            self.preview.emit()
        elif _shape == "circle":
            if self._p0 is None:
                self._p0 = (x, y)                                 # 중심
                self._cursor = (x, y)
                self.preview.emit()
            else:                                                 # 반지름 확정
                self._stamp(self._circle_region(self._p0, (x, y)))
                self.clear_transient()
                self.commit()
        elif _shape == "polygon":
            if len(self._poly) >= 3 and _geom.near(self._poly[0], (x, y), self._grab()):
                self._stamp(self._poly_region(self._poly))        # 첫 점 근처 → 닫는다
                self.clear_transient()
                self.commit()
            else:
                self._poly.append((x, y))
                self._cursor = (x, y)
                self.preview.emit()
        elif _shape == "fill":
            _region = magic_wand(self._t.base, (x, y),
                                 self._tol.value(), self._radius.value())
            if _region is not None:                               # 한 번 클릭 = 한 채우기
                self._stamp(_region)
                self.commit()

    def _view_press(self, x: int, y: int) -> None:
        """보기 — bbox 핸들을 잡거나, 아무것도 안 잡히면 **거기 있는 것을 골라달라** 한다.

        **Shift 는 선택에 더한다** — 캔버스에서 여러 객체를 집어 바로 병합(`M`)하려면 트리로 손이 갈
        이유가 없어야 한다. Shift 중엔 핸들을 안 잡는다(모으는 중이지 고치는 중이 아니다).
        """
        _additive = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        _box = self._t.bbox if self._t is not None else None   # 조준 없이 pick 만 할 때는 핸들이 없다
        if _box and not _additive:
            _i = _geom.hit_corner(_box, x, y, self._grab())
            if _i is not None:
                self._anchor = _geom.corners(_box)[(_i + 2) % 4]  # 반대 코너를 고정
                self._dragged = False
                return
            _edge = _geom.hit_edge(_box, x, y, self._grab())
            if _edge is not None:
                self._edge = _edge
                self._edge_box = list(_box)                       # 시작 시점 상자 = 고정 좌표원
                self._dragged = False
                return
        self.picked.emit(x, y, _additive)                         # 트리를 아는 상위가 답한다

    def _on_move(self, x: int, y: int) -> None:
        _mode = self.tool("mode")
        self._cursor = (x, y)
        if _mode in ("paint", "erase"):
            if self._stroke and self._p0 is not None:             # 지나간 자리를 즉시 칠한다
                self._stamp(self._brush_region(self._p0, (x, y)))
                self._p0 = (x, y)
            self.preview.emit()
        elif _mode == "bbox":
            if self._p0 is not None:
                self.preview.emit()
        elif self._anchor is not None:                            # 코너 — 양축 리사이즈
            self._set_box(_geom.rect_from(self._anchor, (x, y)))
        elif self._edge is not None:                              # 변 중점 — 한 축만
            self._set_box(_geom.edge_resize(self._edge_box, self._edge, x, y))

    def _on_release(self, x: int, y: int) -> None:
        _mode = self.tool("mode")
        if _mode in ("paint", "erase") and self._stroke:
            self._stroke = False
            self._p0 = None
            self.commit()                                         # 스트로크 하나 = 이력 한 칸
        elif _mode == "bbox" and self._p0 is not None:
            _box = _geom.rect_from(self._p0, (x, y))
            self._p0 = None
            if _box[2] - _box[0] >= 2 and _box[3] - _box[1] >= 2:  # 클릭 오인 방지
                self._set_box(_box)
                self.commit()
                self.set_tool("view")                             # 한 번 그리면 보기로 복귀
            else:
                self.preview.emit()
        elif self._anchor is not None or self._edge is not None:
            _moved = self._dragged
            self._anchor = self._edge = self._edge_box = None
            self._dragged = False
            if _moved:
                self.commit()

    def _on_right(self, x: int, y: int) -> None:
        """우클릭 — **그리는 중 마지막 동작만** 취소한다 (확정하지 않는다)."""
        _shape = self.tool("shape")
        if self.tool("mode") in ("paint", "erase"):
            if _shape == "polygon" and self._poly:
                self._poly.pop()
                self.preview.emit()
                return
            if _shape == "circle" and self._p0 is not None:
                self._p0 = None
                self.preview.emit()
                return
        self.clear_transient()

    def _clear_transient(self) -> None:
        self._p0 = None
        self._poly = []
        self._cursor = None
        self._stroke = False
        self._anchor = None
        self._edge = None
        self._edge_box = None
        self._dragged = False

    # ── 픽셀 ──────────────────────────────────────────────────────────────────
    @property
    def _t(self) -> Target:
        return self.target()

    def _value(self) -> int:
        """찍을 값 — 지우기는 0(배경), 그리기는 **조준한 대상의 라벨**."""
        return 0 if self.tool("mode") == "erase" else int(self._t.paint)

    def _stamp(self, region: np.ndarray | None) -> None:
        """영역을 현재 값으로 **제자리** 찍는다 (이력 적재는 호출 측이 `commit` 으로)."""
        if region is not None and region.any():
            self._t.raster[region > 0] = np.uint8(self._value())

    def _blank(self) -> np.ndarray:
        return np.zeros(self._t.raster.shape[:2], np.uint8)

    def _brush_region(self, a, b) -> np.ndarray:
        _m = self._blank()
        cv2.line(_m, a, b, 1, thickness=max(1, self._size.value()))
        return _m

    def _circle_region(self, center, edge) -> np.ndarray:
        _m = self._blank()
        _r = self._radius_to(edge, center)
        if _r > 0:
            cv2.circle(_m, center, _r, 1, -1)
        return _m

    def _poly_region(self, points) -> np.ndarray:
        _m = self._blank()
        cv2.fillPoly(_m, [np.array(points, np.int32)], 1)
        return _m

    def _radius_to(self, point, center=None) -> int:
        _c = center or self._p0
        return int(round(float(np.hypot(point[0] - _c[0], point[1] - _c[1]))))

    # ── bbox ──────────────────────────────────────────────────────────────────
    def _set_box(self, box: list) -> None:
        self._t.bbox = [float(_v) for _v in box]
        self._dragged = True
        self.bbox_changed.emit(list(self._t.bbox))
        self.preview.emit()

    def _grab(self) -> float:
        """핸들·다각형 닫기 판정 반경 — **화면에서** 일정하게 (줌을 보정한다)."""
        _scale = self.canvas.effective_zoom() or 1.0
        return max(6.0, _GRAB_PX / _scale)

    def _redraw(self, _value=None) -> None:
        self.preview.emit()                          # 굵기·반경이 바뀌면 커서 원도 바뀐다


def _spin(label: str, lo: int, hi: int, value: int, tip: str, on_change) -> QWidget:
    """라벨 + 스핀박스 한 칸 (툴바에 얹을 만큼 좁게) — 정확한 수를 넣는 값에 쓴다."""
    _w = QWidget()
    _lay = QHBoxLayout(_w)
    _lay.setContentsMargins(0, 0, 0, 0)
    _lay.setSpacing(3)
    _lay.addWidget(QLabel(label))
    _spin_box = QSpinBox()
    _spin_box.setRange(lo, hi)
    _spin_box.setValue(value)
    _spin_box.setFixedWidth(64)
    if on_change is not None:
        _spin_box.valueChanged.connect(on_change)
    _lay.addWidget(_spin_box)
    _w.setToolTip(tip)
    _w.value = _spin_box.value                       # type: ignore[attr-defined]
    _w.set_value = _spin_box.setValue               # type: ignore[attr-defined]
    return _w
