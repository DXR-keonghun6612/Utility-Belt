"""pixel 도구 — 산출물은 **라스터의 픽셀** (좌표를 남기지 않는다).

[`_region`](_region.py) 이 "여기가 그 객체다"라고 영역을 말한다면, 여기는 그 말을 **픽셀에 새긴다**.
도구가 이 둘뿐인 이유가 그것이다 — 편집기가 만들어 내는 것은 영역 아니면 픽셀이고, 손짓이 몇 개든 그
둘 중 하나로 떨어진다.

**칠하기는 두 축의 곱이다** — 조작(`paint`/`erase`)이 칠할지 지울지를, 모양(`brush`/`lasso`/`circle`/
`fill`)이 어떤 도형으로 칠할지를 정한다. 그래서 "색 비슷한 영역을 **지우기**"(erase × fill)가 조합으로
공짜로 나온다. 한때 `fill`(magic wand)을 조작 축으로 올린 적이 있는데, 그 순간 곱이 깨져 지울 수 없게
됐다 — **축을 잘못 고르면 기능이 조용히 사라진다.** 그래서 버튼을 여섯 개 들어도 도구는 하나다(곱을
도구 경계로 가르면 그 곱이 깨진다).

**올가미는 폴리곤을 소비할 뿐이다** — 꼭짓점을 찍는 손짓은 [`format/polygon.Draft`](../../format/polygon.py)
가 소유하고([`_region`](_region.py) 도 같은 것을 쓴다), 여기서는 그것을 [`_raster`](../_raster.py) 로 채워
찍고 **버린다**. 같은 폴리곤이 저 쪽에선 저장될 좌표가 되고 여기선 픽셀이 되는 것 — 그것이 데이터
생성과 활용이 갈리는 지점이다.

라스터는 **제자리에서** 고친다 — `Target.raster` 는 트리가 든 바로 그 배열이라 칠하면 그게 곧 데이터다
(사본을 들고 나중에 합치면 진실이 둘이 된다). 대신 이력이 사본을 든다.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSpinBox, QWidget

from ...format import polygon as _poly
from ..._tool import Tool
from .. import _overlay, _raster
from ._base import Draw_tool
from ._fill import magic_wand


class Pixel_tool(Draw_tool):
    """조준한 라스터를 칠하고 지운다 (조작 × 모양의 곱)."""

    TOOLS = (
        Tool("paint", "mode", "✏", "그리기", "D",
             "고른 모양으로 조준한 객체의 라벨을 칠한다"),
        Tool("erase", "mode", "🧽", "지우기", "E",
             "고른 모양으로 지운다 (배경 0 으로)"),
        Tool("brush",  "shape", "🖌", "브러시", "B",
             "드래그로 자유롭게 칠한다 (반경 = 굵기)"),
        Tool("lasso",  "shape", "⬠", "올가미", "P",
             "꼭짓점을 클릭하고 첫 점 근처를 클릭해 닫는다 — 그 안을 칠한다 (우클릭 = 마지막 점 취소)"),
        Tool("circle", "shape", "◯", "원", "C",
             "중심을 클릭한 뒤 한 번 더 클릭해 반지름을 정한다 (우클릭 = 중심 취소)"),
        Tool("fill",   "shape", "🪣", "색 채우기", "F",
             "클릭점 반경 원 안에서 색이 비슷한 영역을 채운다 (magic wand — 지우기와도 곱해진다)"),
    )

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._p0: tuple[int, int] | None = None   # 원 중심 / 브러시 직전 점
        self._lasso = _poly.Draft()               # 올가미 — 그리는 손짓은 format 이 안다
        self._stroke = False                      # 브러시 드래그 중

    @classmethod
    def Enabled(cls, target, key: str) -> bool:
        if key == "fill":
            return cls.Applies(target) and target.base is not None  # 색을 볼 배경이 없으면 못 채운다
        return cls.Applies(target)

    def install_shortcuts(self) -> None:
        self._e.bind("[", lambda: self._size.set_value(self._size.value() - 2))
        self._e.bind("]", lambda: self._size.set_value(self._size.value() + 2))

    # ── 옵션 ──────────────────────────────────────────────────────────────────
    def build_options(self, row: QHBoxLayout) -> None:
        self._size = _spin("굵기", 1, 200, 12, "브러시 반경(px)  [ / ] 로 -/+", self._redraw)
        self._radius = _spin("채우기 반경", 1, 500, 30,
                             "색 채우기를 가둘 원형 ROI 반경(px) — 굵기와 독립", self._redraw)
        self._tol = _spin("허용", 0, 255, 24,
                          "색 채우기 허용오차 — 클수록 넓게 번진다", None)
        for _w in (self._size, self._radius, self._tol):
            row.addWidget(_w)

    def sync_options(self) -> None:
        _painting = self._active()
        _shape = self._e.tool("shape")
        self._size.setVisible(_painting and _shape == "brush")
        self._radius.setVisible(_painting and _shape == "fill")
        self._tol.setVisible(_painting and _shape == "fill")

    def _redraw(self, _value=None) -> None:
        self._e.preview.emit()                    # 굵기·반경이 바뀌면 커서 원도 바뀐다

    # ── 포인터 ────────────────────────────────────────────────────────────────
    def press(self, x: int, y: int) -> None:
        _shape = self._e.tool("shape")
        if _shape == "brush":
            self._stroke = True
            self._p0 = (x, y)
            self._stamp(self._brush_at((x, y), (x, y)))       # 클릭 한 번도 점을 찍는다
            self._e.preview.emit()
        elif _shape == "circle":
            self._press_circle(x, y)
        elif _shape == "lasso":
            self._press_lasso(x, y)
        elif _shape == "fill":
            self._press_fill(x, y)

    def _press_circle(self, x: int, y: int) -> None:
        if self._p0 is None:
            self._p0 = (x, y)                     # 중심
            self._e.preview.emit()
            return
        self._stamp(_raster.circle(self._shape(), self._p0,        # 반지름 확정
                                   _distance((x, y), self._p0)))
        self._e.clear_transient()
        self._e.commit()

    def _press_lasso(self, x: int, y: int) -> None:
        if self._lasso.closes_at((x, y), self._e.grab_radius()):
            self._stamp(_raster.polygon(self._shape(), self._lasso.points()))
            self._e.clear_transient()
            self._e.commit()
            return
        self._lasso.add((x, y))
        self._e.preview.emit()

    def _press_fill(self, x: int, y: int) -> None:
        _region = magic_wand(self._e.target().base, (x, y),
                             self._tol.value(), self._radius.value())
        if _region is not None:                   # 한 번 클릭 = 한 채우기
            self._stamp(_region)
            self._e.commit()

    def move(self, x: int, y: int) -> None:
        if self._stroke and self._p0 is not None:  # 지나간 자리를 즉시 칠한다
            self._stamp(self._brush_at(self._p0, (x, y)))
            self._p0 = (x, y)
        self._e.preview.emit()

    def release(self, x: int, y: int) -> None:
        if self._stroke:
            self._stroke = False
            self._p0 = None
            self._e.commit()                      # 스트로크 하나 = 이력 한 칸

    def right(self, x: int, y: int) -> bool:
        """그리는 중 **마지막 동작만** 취소한다 (확정하지 않는다)."""
        _shape = self._e.tool("shape")
        if _shape == "lasso" and self._lasso:
            self._lasso.undo()
            self._e.preview.emit()
            return True
        if _shape == "circle" and self._p0 is not None:
            self._p0 = None
            self._e.preview.emit()
            return True
        return False

    def clear_transient(self) -> None:
        self._p0 = None
        self._lasso.clear()
        self._stroke = False

    # ── 표시 ──────────────────────────────────────────────────────────────────
    def decorate(self, canvas: np.ndarray) -> None:
        if not self._active():
            return
        _shape, _cursor = self._e.tool("shape"), self._e.pointer()
        if _shape == "lasso" and self._lasso:
            _overlay.preview_polygon(canvas, self._lasso.trace(_cursor))
        elif _shape == "circle" and self._p0 and _cursor:
            _overlay.preview_circle(canvas, self._p0, _distance(_cursor, self._p0))
        elif _shape in ("brush", "fill") and _cursor:
            _overlay.cursor(canvas, _cursor,
                            self._size.value() if _shape == "brush" else self._radius.value())

    # ── 픽셀 ──────────────────────────────────────────────────────────────────
    def _active(self) -> bool:
        return self._e.tool("mode") in ("paint", "erase")

    def _shape(self) -> tuple[int, ...]:
        """찍을 라스터의 크기 — region 은 언제나 이 크기로 난다."""
        return self._e.target().raster.shape

    def _brush_at(self, a, b) -> np.ndarray:
        # 굵기 스핀은 **반경**이다(커서 원도 그 반지름으로 그린다) — 그런데 ``brush`` 는 그 값을
        # 선 굵기(=지름)로 쓰는 cv2.line 이라, 2 를 곱해 지름으로 넘겨야 커서와 실제 칠이 맞는다.
        return _raster.brush(self._shape(), a, b, self._size.value() * 2)

    def _value(self) -> int:
        """찍을 값 — 지우기는 0(배경), 그리기는 **조준한 대상의 라벨**."""
        return 0 if self._e.tool("mode") == "erase" else int(self._e.target().paint)

    def _stamp(self, region: np.ndarray | None) -> None:
        """영역을 현재 값으로 **제자리** 찍는다 (이력 적재는 호출 측이 `commit` 으로)."""
        if region is not None and region.any():
            self._e.target().raster[region > 0] = np.uint8(self._value())


def _distance(point, center) -> int:
    """두 점 사이 거리 (px) — 원의 반지름."""
    return int(round(float(np.hypot(point[0] - center[0], point[1] - center[1]))))


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
    _w.value = _spin_box.value                    # type: ignore[attr-defined]
    _w.set_value = _spin_box.setValue             # type: ignore[attr-defined]
    return _w
