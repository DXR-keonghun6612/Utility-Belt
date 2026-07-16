"""region 도구 — 산출물은 **영역** (픽셀을 안 건드린다).

영역을 만드는 손짓 전부가 여기 산다 — 빈 곳을 **드래그**하면 상자, **꼭짓점**을 찍어 닫으면 그 폴리곤,
`view` 에서 **핸들**을 잡으면 고친다. 셋이 다른 도구가 아닌 이유는 산출물이 같기 때문이다: 어느 쪽이든
"여기가 그 객체다"라고 말하는 영역 하나다. 도구를 산출물로 가르면 [`_pixel`](_pixel.py) 과 이 파일 둘로
끝나고, 손짓이 늘어도 파일이 안 는다.

**기하가 한 줄도 없다.** 정준형·히트판정·확정 전 상태(`Draft`)는 [`format/bbox`](../../format/bbox.py) 와
[`format/polygon`](../../format/polygon.py) 이 이미 다 안다 — 이 파일은 포인터를 그 둘에 **배선**할 뿐이다.
그래서 3d 편집기가 생겨도 옮겨야 할 지식이 여기 없다(있는 건 Qt·cv2 에 묶인 배선뿐).

**영역을 가질 수 없는 대상에는 안 붙는다**(`Applies`) — mask leaf 처럼 객체가 아닌 것을 겨눴을 때 버튼이
켜져 있으면, 눌러도 아무 일이 없는 조용한 버튼이 된다.
"""
from __future__ import annotations

import numpy as np

from ...format import bbox, polygon
from ..._tool import Tool
from .. import _overlay
from ._base import Draw_tool

#: 드래그가 상자로 인정되는 최소 변 길이 (px) — 이보다 얇으면 클릭 오인으로 본다.
_MIN_SIDE = 2

#: 영역 다각형 → 상자를 변 길이의 이 비율만큼 키운다 — SAM3 에 여유 맥락을 준다 ("살짝 크게").
_REGION_MARGIN = 0.06

#: 그 확장의 축당 최소치 (px) — 얇은 영역이 안 커지는 것을 막는다.
_MIN_MARGIN = 2.0


class Region_tool(Draw_tool):
    """조준한 객체의 영역을 그리고 고친다 (드래그 = 상자 · 꼭짓점 = 폴리곤)."""

    TOOLS = (
        Tool("bbox", "mode", "▭", "bbox", "R",
             "드래그로 조준한 객체의 상자를 그린다"),
        Tool("region", "mode", "⬡", "영역 다각형", "G",
             "다각형으로 영역을 감싸면 그 (살짝 큰) 상자를 조준 객체에 준다 — SAM3 flow 가 정제한다"),
    )

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._box = bbox.Draft()          # 드래그로 그리는 중 · 핸들로 고치는 중
        self._poly = polygon.Draft()      # 꼭짓점을 찍는 중

    @classmethod
    def Applies(cls, target) -> bool:
        return target is not None and target.bbox is not None

    # ── 포인터 ────────────────────────────────────────────────────────────────
    def press(self, x: int, y: int) -> None:
        if self._e.tool("mode") == "bbox":
            self._box.start((x, y))
            self._e.preview.emit()
        else:
            self._press_polygon(x, y)

    def move(self, x: int, y: int) -> None:
        if self._e.tool("mode") == "view":
            self._drag_handle(x, y)       # 핸들은 **즉시** 반영한다 (잡은 것이 따라와야 하니까)
        elif self._box or self._poly:
            self._e.preview.emit()        # 새로 그리는 중엔 미리보기만 — 확정은 release·닫기에서

    def release(self, x: int, y: int) -> None:
        if self._e.tool("mode") == "bbox":
            self._finish_draw(x, y)
        elif self._box:
            self._finish_handle()

    def right(self, x: int, y: int) -> bool:
        if self._e.tool("mode") == "region" and self._poly:
            self._poly.undo()             # 마지막 꼭짓점만 취소 (그리던 것 전체를 안 버린다)
            self._e.preview.emit()
            return True
        return False

    def clear_transient(self) -> None:
        self._box.clear()
        self._poly.clear()

    # ── 상자 — 드래그로 그리기 ────────────────────────────────────────────────
    def _finish_draw(self, x: int, y: int) -> None:
        _new = self._box.at((x, y))
        self._box.clear()
        if _new is None:
            return
        if bool(np.any(_new[1] - _new[0] < _MIN_SIDE)):
            self._e.preview.emit()        # 클릭 오인 — 상자를 안 만든다
            return
        self._commit(_new)

    # ── 상자 — 핸들로 고치기 (`view` 모드) ──────────────────────────────────────
    def grab(self, x: int, y: int) -> bool:
        return self._box.grab(self._target_box(), (x, y), self._e.grab_radius())

    def _drag_handle(self, x: int, y: int) -> None:
        _new = self._box.drag((x, y))
        if _new is not None:
            self._e.set_box(_new)

    def _finish_handle(self) -> None:
        _moved = self._box.moved()
        self._box.clear()
        if _moved:
            self._e.commit()              # 눌렀다 놓기만 했으면 이력에 빈 칸을 안 쌓는다

    # ── 폴리곤 — 꼭짓점으로 감싸기 ────────────────────────────────────────────
    def _press_polygon(self, x: int, y: int) -> None:
        if self._poly.closes_at((x, y), self._e.grab_radius()):
            self._finish_polygon()
            return
        self._poly.add((x, y))
        self._e.preview.emit()

    def _finish_polygon(self) -> None:
        """그린 폴리곤의 외접 상자를 살짝 키워 조준 객체의 영역으로 준다.

        SAM3 는 이 상자를 프롬프트로 읽어(기존 ``segment`` flow) 영역을 정제한다 — 라이브 추론이 아니라
        평소 배치 run 이 한다. 그래서 편집기는 모델을 모르고 **상자만** 낸다(드래그와 같은 산출물).
        """
        _height, _width = self._e.target().raster.shape[:2]
        _grown = bbox.grow(polygon.bounds(self._poly.points()),
                           _REGION_MARGIN, _MIN_MARGIN, (_width, _height))
        self._e.clear_transient()
        self._commit(_grown)

    def _commit(self, box: np.ndarray) -> None:
        self._e.set_box(box)
        self._e.commit()
        self._e.set_tool("view")          # 한 번 그리면 보기로 복귀 (바로 핸들을 잡게)

    # ── 표시 ──────────────────────────────────────────────────────────────────
    def decorate(self, canvas: np.ndarray) -> None:
        _mode = self._e.tool("mode")
        if _mode == "region" and self._poly:
            _overlay.preview_polygon(canvas, self._poly.trace(self._e.pointer()))
        elif _mode == "view":
            _current = self._target_box()
            if _current is not None and _current.size > 0:
                _overlay.handles(canvas, bbox.corners(_current), _face_centers(_current))

    def preview_box(self) -> np.ndarray | None:
        """지금 **그리는 중인** 상자 (아니면 ``None`` — 확정 상자는 `Target` 이 든다)."""
        _cursor = self._e.pointer()
        if self._e.tool("mode") == "bbox" and self._box and _cursor is not None:
            return self._box.at(_cursor)
        return None

    # ── 내부 ──────────────────────────────────────────────────────────────────
    def _target_box(self) -> np.ndarray | None:
        _t = self._e.target()
        return _t.bbox if _t is not None else None


def _face_centers(box: np.ndarray) -> np.ndarray:
    """면 핸들의 중심들만 ``(2D, D)`` — 축·쪽은 히트 판정이 쓰고 그리는 쪽은 위치만 필요하다."""
    return np.array([_center for _center, _, _ in bbox.faces(box)], float)
