"""이미지 뷰 인터랙션 컨트롤러 — 조작(view/bbox/paint/erase) × 모양(brush/polygon/circle) (설계는 README).

mask 편집은 두 축의 곱이다: 조작(``mode`` 의 paint/erase)이 칠할지 지울지를, 모양(``shape``)이
어떤 도형으로 칠할지를 정한다 — 6가지 조합(그리기/지우기 × 브러시/다각형/원). ``view``/``bbox`` 는
mask 편집과 무관한 별도 조작이라 ``shape`` 를 참조하지 않는다.

진행 중 transient 상태는 컨트롤러가 소유, 영속 상태는 editor 백레퍼런스(``self._ed``)로 읽는다.
"""

from __future__ import annotations

from gui.verify._helpers import _bbox_of, _corners, _rect_from


class Draw_controller:
    """편집 조작/모양 + 마우스 인터랙션 컨트롤러 (editor 백레퍼런스로 동작).

    Attributes:
        mode: 현재 조작 (``view`` / ``bbox`` / ``paint`` / ``erase``).
        shape: mask 편집 모양 (``brush`` / ``polygon`` / ``circle``) — paint/erase 일 때만 쓰인다.
    """

    def __init__(self, editor) -> None:
        """Args: editor: 백레퍼런스(``Stem_editor``) — anns·view·mode_btns 등 영속 상태 접근."""
        self._ed = editor
        self.mode = "view"
        self.shape = "brush"
        self._p0: tuple[int, int] | None = None      # bbox 첫 점 / 원 중심
        self._cursor: tuple[int, int] | None = None  # 미리보기용 현재 커서
        self._anchor: tuple[int, int] | None = None  # 코너 드래그 시 고정될 반대 코너
        self._dragged = False                        # 코너 드래그로 실제 이동이 있었는지
        self._stroke_active = False                  # 브러시 스트로크(드래그) 진행 중
        self._poly: list[tuple[int, int]] = []       # 다각형 그리는 중 찍은 꼭짓점

    def _clear_transient(self) -> None:
        """진행 중 그리기 상태(bbox/원/다각형/스트로크/코너)를 모두 비운다."""
        self._p0 = None
        self._cursor = None
        self._anchor = None
        self._dragged = False
        self._stroke_active = False
        self._poly = []

    def reset(self) -> None:
        """조작/모양/진행 상태를 초기화한다 (stem 로드 직후 — UI 갱신은 호출 측이 한다)."""
        self.mode = "view"
        self.shape = "brush"
        self._clear_transient()

    def set_mode(self, mode: str) -> None:
        """조작을 바꾼다 (view / bbox / paint / erase) — 진행 중 상태를 리셋한다.

        모양(``shape``)은 유지한다 — 그리기/지우기를 오가도 도형 선택은 그대로 둔다.
        """
        self.mode = mode
        self._clear_transient()
        if self._ed._mode_btns.get(mode) is not None:
            self._ed._mode_btns[mode].setChecked(True)
        self._ed._refresh_image()

    def set_shape(self, shape: str) -> None:
        """mask 편집 모양을 바꾼다 (brush / polygon / circle) — 진행 중 상태를 리셋한다.

        보기/bbox 모드에서 모양을 고르면 곧바로 그릴 수 있게 ``paint`` 로 전환한다
        (이미 paint/erase 면 그 조작을 유지한다).
        """
        self.shape = shape
        self._clear_transient()
        if self.mode not in ("paint", "erase"):
            self.mode = "paint"
            if self._ed._mode_btns.get("paint") is not None:
                self._ed._mode_btns["paint"].setChecked(True)
        if self._ed._shape_btns.get(shape) is not None:
            self._ed._shape_btns[shape].setChecked(True)
        self._ed._refresh_image()

    # ── 오버레이 미리보기 ─────────────────────────────────────────────────────
    def preview_rect(self):
        """bbox 그리는 중이면 미리보기 사각형 ``[x0,y0,x1,y1]``, 아니면 None (오버레이용)."""
        if self.mode == "bbox" and self._p0 is not None and self._cursor is not None:
            return _rect_from(self._p0, self._cursor)
        return None

    def preview_circle(self):
        """원 그리는 중이면 미리보기 ``(cx, cy, radius)``, 아니면 None (오버레이용)."""
        if (self.mode in ("paint", "erase") and self.shape == "circle"
                and self._p0 is not None and self._cursor is not None):
            return (self._p0[0], self._p0[1], self._radius_to(self._cursor))
        return None

    def preview_poly(self):
        """다각형 그리는 중이면 찍은 꼭짓점(+커서) 리스트, 아니면 None (오버레이용)."""
        if (self.mode in ("paint", "erase") and self.shape == "polygon"
                and self._poly):
            return self._poly + ([self._cursor] if self._cursor is not None else [])
        return None

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────
    def _radius_to(self, pt: tuple[int, int]) -> float:
        """원 중심(``self._p0``)에서 ``pt`` 까지의 반지름(px)."""
        return ((self._p0[0] - pt[0]) ** 2 + (self._p0[1] - pt[1]) ** 2) ** 0.5

    def _paint_at(self, x: int, y: int) -> bool:
        """현재 브러시로 활성 object 의 mask 를 칠하거나 지운다."""
        return self._ed._anns.paint_active(
            x, y, self._ed._brush_size, erase=(self.mode == "erase"),
            size=self._ed._canvas_size())

    def _near(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        """두 원본 좌표가 화면상 ~12px 이내로 붙어 있으면 True (다각형 닫기 판정용)."""
        _scale = self._ed._view.effective_zoom() or 1.0
        _thr = max(6.0, 12.0 / _scale)
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 <= _thr

    def _nearest_corner(self, bbox, x: int, y: int) -> int | None:
        """허용 반경 안에서 ``(x, y)`` 에 가장 가까운 코너 인덱스를 찾는다 (화면상 ~12px)."""
        _scale = self._ed._view.effective_zoom() or 1.0
        _thr = max(6.0, 12.0 / _scale)
        _best = None
        for _i, (_cx, _cy) in enumerate(_corners(bbox)):
            _d = ((_cx - x) ** 2 + (_cy - y) ** 2) ** 0.5
            if _d <= _thr:
                _thr = _d
                _best = _i
        return _best

    def _commit_circle(self, x: int, y: int) -> None:
        """원 중심~둘째 점 반지름으로 활성 mask 에 원을 칠/지우고 진행 상태를 비운다."""
        _r = round(self._radius_to((x, y)))
        if _r >= 1 and self._ed._anns.paint_active(
                self._p0[0], self._p0[1], _r, erase=(self.mode == "erase"),
                size=self._ed._canvas_size()):
            self._ed._commit()
        self._p0 = None
        self._cursor = None
        self._ed._refresh_image()

    def _commit_polygon(self) -> None:
        """찍은 꼭짓점으로 활성 mask 에 다각형을 칠/지우고 진행 상태를 비운다."""
        if self._ed._anns.fill_polygon_active(
                self._poly, erase=(self.mode == "erase"),
                size=self._ed._canvas_size()):
            self._ed._commit()
        self._poly = []
        self._cursor = None
        self._ed._refresh_image()

    # ── 마우스 인터랙션 (조작·모양별 분기) ──────────────────────────────────────
    def on_press(self, x: int, y: int) -> None:
        """좌클릭 — 조작/모양에 따라 mask 칠하기·bbox 2점·코너 핸들을 처리한다."""
        if self.mode in ("paint", "erase"):
            self._mask_press(x, y)
            return

        _obj = self._ed._anns.selected_obj()
        if self.mode == "bbox":
            if _obj is None:
                return                                  # 대상 object 선택 필요
            if self._p0 is None:                        # 첫 점
                self._p0 = (x, y)
                self._cursor = (x, y)
                self._ed._refresh_image()
            else:                                       # 둘째 점 → 확정
                self._ed._anns.set_bbox(_obj, _rect_from(self._p0, (x, y)))
                self._p0 = None
                self._cursor = None
                self._ed._commit()                      # bbox 확정 → 이력 적재
                self.set_mode("view")                   # 1회 그리면 보기로 복귀
        else:                                           # view — 코너 리사이즈 or object 선택
            # 현재 선택 object 의 코너를 잡으면 리사이즈, 아니면 클릭 지점의 object 를 선택.
            if _obj is not None:
                _bbox = _bbox_of(_obj)
                if _bbox is not None:
                    _i = self._nearest_corner(_bbox, x, y)
                    if _i is not None:                  # 잡은 코너의 반대 코너를 고정
                        self._anchor = _corners(_bbox)[(_i + 2) % 4]
                        self._dragged = False
                        return
            self._ed._anns.select_at(x, y)              # bbox 안을 클릭 → 그 object 선택

    def _mask_press(self, x: int, y: int) -> None:
        """paint/erase 조작에서 모양별로 좌클릭을 처리한다 (브러시 스트로크·원·다각형)."""
        if self.shape == "brush":
            if self._paint_at(x, y):                    # 스트로크 시작
                self._stroke_active = True
        elif self.shape == "circle":
            if self._p0 is None:                        # 중심
                self._p0 = (x, y)
                self._cursor = (x, y)
                self._ed._refresh_image()
            else:                                       # 반지름 확정
                self._commit_circle(x, y)
        elif self.shape == "polygon":
            if len(self._poly) >= 3 and self._near(self._poly[0], (x, y)):
                self._commit_polygon()                  # 첫 점 근처 클릭 → 닫기
            else:
                self._poly.append((x, y))               # 꼭짓점 추가
                self._cursor = (x, y)
                self._ed._refresh_image()

    def on_move(self, x: int, y: int) -> None:
        """모양/조작별 드래그 — 브러시 스트로크·bbox·원·다각형·코너 미리보기."""
        if self.mode in ("paint", "erase"):
            if self.shape == "brush":
                if self._stroke_active:
                    self._paint_at(x, y)
            elif self.shape == "circle":
                if self._p0 is not None:                # 반지름 미리보기
                    self._cursor = (x, y)
                    self._ed._refresh_image()
            elif self.shape == "polygon":
                if self._poly:                          # 다음 변 미리보기
                    self._cursor = (x, y)
                    self._ed._refresh_image()
            return
        if self.mode == "bbox" and self._p0 is not None:
            self._cursor = (x, y)
            self._ed._refresh_image()
        elif self.mode == "view" and self._anchor is not None:
            _obj = self._ed._anns.selected_obj()
            if _obj is not None:                        # 반대 코너 고정 + 커서 → 새 bbox
                self._ed._anns.set_bbox(_obj, _rect_from(self._anchor, (x, y)))
                self._dragged = True

    def on_release(self, _x: int, _y: int) -> None:
        """드래그 종료 — 브러시 스트로크/코너 드래그가 실제로 바뀌었으면 이력에 적재한다."""
        if self._stroke_active:
            self._stroke_active = False
            self._ed._commit()
        elif self._anchor is not None:
            _moved = self._dragged
            self._anchor = None
            self._dragged = False
            if _moved:
                self._ed._commit()
