"""stem 한 장의 편집 surface — 재사용 위젯 (목록·내비 없이 ``load_stem`` 으로 구동). 설계는 README."""

from __future__ import annotations

from copy import deepcopy

import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.data.handler import Data_Ref
from core.data.meta import Dataset_Meta
from core.data.schema import Attr
from gui.meta_page.verify import _fill, _overlay, _segment
from gui.meta_page.verify._annotation import _Annotation_panel
from gui.meta_page.verify._draw import Draw_controller
from gui.meta_page.verify._helpers import _bbox_of, _corners, _edge_midpoints
from gui.meta_page.verify._history import Edit_history
from gui.widgets import Image_label, make_tree


class Stem_editor(QWidget):
    """stem 한 장의 이미지/object 편집 surface (목록 없음 — 호출 측이 몬다).

    Attributes:
        saved: 저장이 ``meta`` 에 반영됐을 때 저장된 stem 이름과 함께 emit.
    """

    saved = Signal(str)

    def __init__(self, meta: Dataset_Meta, stem: str, parent=None) -> None:
        super().__init__(parent)
        self._meta = meta
        self._stem = stem
        # stem 의존 상태는 load_stem 에서 채운다 (stem 전환마다 갈아끼움).
        self._state: str | None = None                # 이 stem 이 사는 버킷 (modified/staged)
        self._work = None                             # 저장 전까지 원본을 안 건드리는 작업 사본
        self._bases: dict[str, np.ndarray] = {}
        self._data_items: dict[str, QTreeWidgetItem] = {}
        # 데이터 시각화 토글(키별 on/off) — stem 전환에도 유지하려 보관한다.
        self._data_vis: dict[str, bool] = {}
        self._brush_size = 8                          # 그리기/지우기 브러시 반지름(px, stem 넘어 유지)
        self._fill_radius = 30                        # 채우기(magic-wand) 원형 ROI 반지름(px) — 굵기와 독립
        self._tolerance = 20                          # 채우기(magic-wand) 색 허용오차 (stem 넘어 유지)
        self._brightness = 0                          # 표시용 base 밝기 가감 (view aid, stem 넘어 유지)
        self._editable = True                         # 편집 잠금 토글 (백그라운드 작업 중엔 보기만)
        # 모드/마우스 인터랙션(transient 상태 소유) · undo/redo 스택 — 분리된 헬퍼.
        self._draw = Draw_controller(self)
        self._history = Edit_history(self._snapshot, self._restore)
        self._build()
        self._install_shortcuts()
        self.load_stem(stem)

    def _install_shortcuts(self) -> None:
        """위젯 단위 단축키를 건다 (임베드 시 메인과 충돌 없게 ``WidgetWithChildren`` 컨텍스트).

        * ``0``–``9``      : 해당 인덱스 object 선택
        * ``Ctrl+Z / Y``   : 되돌리기 / 다시실행
        * ``Ctrl+S``       : 편집 저장
        * ``Ctrl+A``       : object 추가
        * ``Delete``       : 선택 object 삭제
        * ``V / R / D / E``: 조작 — 보기 / RoI / 그리기 / 지우기 (``V`` 가 그리기 취소 겸용)
        * ``B / P / C / F``: 모양 — 브러시 / 다각형 / 원 / 채우기 (그리기·지우기에 적용; 보기/RoI 면 그리기로 전환)
        * ``[ / ]``        : 브러시 굵기 -/+

        stem 내비게이션(다음/이전)·창 닫기(Esc)는 이 위젯의 책임이 아니다 — 목록·창을 가진 호출
        측이 건다. (Esc 를 여기서 잡으면 임베드 시 컨테이너의 닫기/취소를 가로챈다.)
        """
        def _sc(seq, slot) -> None:
            _s = QShortcut(QKeySequence(seq), self)
            _s.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            _s.activated.connect(slot)

        _sc("Ctrl+Z", self.undo)
        _sc("Ctrl+Y", self.redo)
        _sc("Ctrl+S", self.save)
        _sc("A", self._add_object)
        _sc("Delete", self._delete_object)
        for _i in range(10):
            _sc(str(_i), lambda i=_i: self._anns.select_index(i))
        for _key, _mode in (("V", "view"), ("R", "bbox"),
                            ("D", "paint"), ("E", "erase")):
            _sc(_key, lambda m=_mode: self._set_mode(m))
        for _key, _shape in (("B", "brush"), ("P", "polygon"), ("C", "circle"),
                             ("F", "fill")):
            _sc(_key, lambda s=_shape: self._set_shape(s))
        _sc("[", lambda: self._bump_brush(-2))
        _sc("]", lambda: self._bump_brush(+2))

    def _center_on_selected(self) -> None:
        """선택된 object 의 bbox 중심으로 이미지 뷰를 스크롤한다 (bbox 없으면 무시)."""
        _obj = self._anns.selected_obj()
        if _obj is None:
            return
        _bb = _bbox_of(_obj)
        if _bb is not None:
            self._view.center_on((_bb[0] + _bb[2]) / 2, (_bb[1] + _bb[3]) / 2)

    def focus_objects(self) -> None:
        """object 트리에 키보드 포커스를 준다 (Tab 토글용 — 현재 패널로 위임)."""
        if self._anns is not None:
            self._anns.focus_tree()

    def objects_have_focus(self) -> bool:
        """object 트리가 현재 키보드 포커스를 쥐고 있으면 True (Tab 토글 판정용)."""
        return self._anns is not None and self._anns.tree_has_focus()

    # ── 편집 잠금 (백그라운드 작업 중 — 보기·선택·줌은 유지, 수정만 차단) ──────────
    def set_editable(self, editable: bool) -> None:
        """편집 잠금을 토글한다 — 잠그면 mask/bbox/object 편집·저장을 막고 보기만 남긴다.

        백그라운드 작업 중 데이터가 워커에서 변형되므로 편집을 잠근다. 이미지 뷰(줌·오버레이
        토글·object 선택)는 그대로 두어 stem 을 계속 검토할 수 있게 한다.
        """
        self._editable = editable
        self._apply_editable()

    def _apply_editable(self) -> None:
        """현재 편집 가능 상태를 편집 컨트롤에 반영한다 (토글 시·stem 재구성 후)."""
        if not self._editable:
            self._draw.set_mode("view")                # 편집 조작(그리기/RoI) 해제
        for _m in ("bbox", "paint", "erase"):          # 보기만 남기고 편집 조작 버튼 비활성
            self._mode_btns[_m].setEnabled(self._editable)
        for _b in self._shape_btns.values():
            _b.setEnabled(self._editable)
        self._brush.setEnabled(self._editable)
        self._fill_roi.setEnabled(self._editable)
        self._tol.setEnabled(self._editable)
        if self._anns is not None:
            self._anns.set_editable(self._editable)

    def _bump_brush(self, delta: int) -> None:
        self._brush.setValue(self._brush.value() + delta)

    def _add_object(self) -> None:
        if not self._editable:
            return
        self._anns.add_object()

    def _delete_object(self) -> None:
        if not self._editable:
            return
        self._anns.delete_selected()

    # ── 골격 ────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        """편집 영역 컨테이너만 만든다 (stem 마다 ``_build_content`` 가 내부를 채운다)."""
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        self._content = QWidget()
        self._content_lay = QVBoxLayout(self._content)
        self._content_lay.setContentsMargins(0, 0, 0, 0)
        _lay.addWidget(self._content, stretch=1)

    # ── stem 로드 ──────────────────────────────────────────────────────────────
    def load_stem(self, stem: str) -> None:
        """``stem`` 의 작업 사본을 만들고 편집 영역을 재구성한다 (상태 버킷 기준).

        작업 사본이라 저장 전까지 원본 ``meta`` 는 건드리지 않는다.
        """
        self._stem = stem
        self._state = self._meta.State_of(stem)
        self._work = deepcopy(self._meta.Get(stem))
        # object 별 bbox 원본 스냅샷 — 저장 시 바뀐 bbox 만 골라 mask 를 잘라낸다.
        self._bbox_orig = {id(_o): _bbox_of(_o)
                           for _o in self._work.info.values() if _o.Is_stem()}
        self._bases = _overlay.load_base_images(self._meta, stem)
        self._data_items = {}
        self._draw.reset()
        self._build_content()
        self._reset_history()
        self._refresh_image()

    def reload(self) -> None:
        """meta 가 갱신됨 — 현재 stem 을 meta 기준으로 다시 읽는다 (미저장 편집은 버려진다)."""
        if self._meta.Has(self._stem):
            self.load_stem(self._stem)

    def _build_content(self) -> None:
        """현재 stem 용 편집 영역(이미지 뷰 + 데이터/object 패널)을 만든다.

        stem 전환마다 호출되므로 기존 위젯을 먼저 비운 뒤 다시 구성한다.
        """
        while self._content_lay.count():
            _it = self._content_lay.takeAt(0)
            _w = _it.widget()
            if _w is not None:
                _w.setParent(None)
                _w.deleteLater()

        _split = QSplitter(Qt.Orientation.Horizontal)

        # ── 좌: 툴바 + 이미지 뷰 ──────────────────────────────────────────────
        _left = QWidget()
        _left_lay = QVBoxLayout(_left)
        _left_lay.setContentsMargins(0, 0, 0, 0)
        _left_lay.setSpacing(2)

        _tool = QHBoxLayout()
        # ── 조작 그룹 (보기/RoI/그리기/지우기) — 상호배타 ─────────────────────
        self._mode_btns: dict[str, QToolButton] = {}
        _mode_group = QButtonGroup(_left)         # 조작 버튼 상호배타 (한 번에 하나)
        _mode_group.setExclusive(True)
        for _m, _text, _key, _tip in (
            ("view",  "👆 보기",  "V", "RoI 코너·변 핸들을 드래그해 수정 (선택/조회)"),
            ("bbox",  "⬚ RoI",   "R", "점 2개를 찍어 활성 object 의 RoI(사각형)를 그린다"),
            ("paint", "✏ 그리기", "D", "선택한 모양으로 활성 object 의 mask 를 칠한다"),
            ("erase", "⌫ 지우기", "E", "선택한 모양으로 활성 object 의 mask 를 지운다"),
        ):
            _b = QToolButton()
            _b.setText(_text)
            _b.setCheckable(True)
            _b.setToolTip(f"{_tip}  [단축키 {_key}]")
            _b.clicked.connect(lambda _c=False, m=_m: self._set_mode(m))
            _mode_group.addButton(_b)
            self._mode_btns[_m] = _b
            _tool.addWidget(_b)
        self._mode_btns[self._draw.mode].setChecked(True)

        # ── 모양 그룹 (브러시/다각형/원) — 그리기·지우기에만 적용, 상호배타 ─────
        _tool.addSpacing(12)
        _tool.addWidget(QLabel("모양"))
        self._shape_btns: dict[str, QToolButton] = {}
        _shape_group = QButtonGroup(_left)        # 모양 버튼 상호배타 (한 번에 하나)
        _shape_group.setExclusive(True)
        for _s, _text, _key, _tip in (
            ("brush",   "🖌 브러시", "B", "드래그로 자유롭게 칠/지운다 (반지름=굵기)"),
            ("polygon", "⬠ 다각형", "P", "꼭짓점을 클릭해 그리고 첫 점 근처를 클릭해 닫는다 (우클릭=점 취소)"),
            ("circle",  "◯ 원",     "C", "중심을 클릭한 뒤 한 번 더 클릭해 반지름을 정한다 (우클릭=중심 취소)"),
            ("fill",    "🪣 채우기", "F", "클릭점 중심 '채우기 반경' 원 안에서 색 유사 + LoG edge 경계까지 채운다 (반경=ROI, 허용=색차)"),
        ):
            _b = QToolButton()
            _b.setText(_text)
            _b.setCheckable(True)
            _b.setToolTip(f"{_tip}  [단축키 {_key}]")
            _b.clicked.connect(lambda _c=False, s=_s: self._set_shape(s))
            _shape_group.addButton(_b)
            self._shape_btns[_s] = _b
            _tool.addWidget(_b)
        self._shape_btns[self._draw.shape].setChecked(True)

        # ── 굵기 (브러시/원 스트로크 반경) — 채우기 아닐 때만 노출 ────────────
        _tool.addSpacing(12)
        self._brush_controls = QWidget()
        _brush_lay = QHBoxLayout(self._brush_controls)
        _brush_lay.setContentsMargins(0, 0, 0, 0)
        _brush_lay.addWidget(QLabel("굵기"))
        self._brush = QSpinBox()
        self._brush.setRange(1, 200)
        self._brush.setValue(self._brush_size)
        self._brush.setToolTip("브러시/원 반지름(px)  [단축키 [ / ] 로 -/+]")
        self._brush.valueChanged.connect(lambda v: setattr(self, "_brush_size", v))
        _brush_lay.addWidget(self._brush)
        _tool.addWidget(self._brush_controls)

        # ── 채우기 전용 (ROI 반경 + 색 허용오차) — 채우기 활성 시에만 노출 ────
        self._fill_controls = QWidget()
        _fill_lay = QHBoxLayout(self._fill_controls)
        _fill_lay.setContentsMargins(0, 0, 0, 0)
        _fill_lay.addWidget(QLabel("채우기 반경"))
        self._fill_roi = QSpinBox()
        self._fill_roi.setRange(1, 500)
        self._fill_roi.setValue(self._fill_radius)
        self._fill_roi.setToolTip("채우기 원형 ROI 반지름(px) — 이 원 안만 채운다 (굵기와 독립)")
        self._fill_roi.valueChanged.connect(lambda v: setattr(self, "_fill_radius", v))
        _fill_lay.addWidget(self._fill_roi)
        _fill_lay.addSpacing(8)
        _fill_lay.addWidget(QLabel("허용"))
        self._tol = QSpinBox()
        self._tol.setRange(0, 255)
        self._tol.setValue(self._tolerance)
        self._tol.setToolTip("채우기 색 허용오차 (클수록 넓게 번진다)")
        self._tol.valueChanged.connect(lambda v: setattr(self, "_tolerance", v))
        _fill_lay.addWidget(self._tol)
        _tool.addWidget(self._fill_controls)

        # ── 밝기 (표시용 base 보정) — 편집 잠금과 무관한 view aid, 항상 활성 ────
        _tool.addSpacing(12)
        _tool.addWidget(QLabel("밝기"))
        self._bright = QSpinBox()
        self._bright.setRange(-100, 100)
        self._bright.setValue(self._brightness)
        self._bright.setToolTip("표시용 밝기 조정 — 어두워 안 보이는 부분을 들어올린다 "
                                "(저장 데이터·채우기엔 영향 없음)")
        self._bright.valueChanged.connect(self._on_brightness)
        _tool.addWidget(self._bright)

        _tool.addStretch()
        _left_lay.addLayout(_tool)

        self._view = Image_label("이미지 없음")
        self._view.set_interactive(True)
        self._view.mouse_pressed.connect(self._draw.on_press)
        self._view.mouse_moved.connect(self._draw.on_move)
        self._view.mouse_released.connect(self._draw.on_release)
        self._view.mouse_right_pressed.connect(self._draw.on_right_press)
        _left_lay.addWidget(self._view, stretch=1)
        _split.addWidget(_left)

        # ── 우: 데이터 트리 + object 패널 ────────────────────────────────────
        _panel = QWidget()
        self._panel_lay = QVBoxLayout(_panel)
        self._panel_lay.setContentsMargins(4, 4, 4, 4)

        _data_tree = self._build_data_tree()
        _data_tree.setMaximumHeight(160)
        self._panel_lay.addWidget(_data_tree)

        self._anns = None
        self._rebuild_panel()                    # object 패널을 패널 레이아웃에 채운다

        _panel.setMinimumWidth(340)
        _split.addWidget(_panel)
        _split.setSizes([640, 360])
        self._content_lay.addWidget(_split)
        self._apply_editable()                   # 재구성된 컨트롤에 현재 잠금 상태 반영
        self._update_fill_ui()                   # 현재 모양에 맞춰 굵기/채우기 컨트롤 노출

    def _rebuild_panel(self, masks: dict | None = None) -> None:
        """object 패널만 다시 구성한다 (이미지 뷰/툴바는 유지).

        Args:
            masks: ``{obj_id: (mask|None, dirty)}`` 강제 주입 (없으면 디스크 로드).
        """
        # 패널이 포커스를 쥔 채 파괴되면 Qt 가 포커스를 엉뚱한 위젯으로 넘기므로(예:
        # dataset_root), 재구성 후 새 트리에 포커스를 되돌려 준다. 트리뿐 아니라 "병합"
        # 버튼 클릭(버튼도 패널 안)으로 재구성되는 경우도 있어 패널 전체로 판정한다.
        _had_focus = self._anns is not None and self._anns.contains_focus()
        if self._anns is not None:
            self._panel_lay.removeWidget(self._anns)
            self._anns.setParent(None)
            self._anns.deleteLater()
        self._anns = _Annotation_panel(self._meta, self._stem, self._work, masks=masks)
        self._anns.changed.connect(self._refresh_image)
        self._anns.edited.connect(self._commit)
        self._anns.merge_requested.connect(self._on_merge)
        self._anns.object_selected.connect(self._center_on_selected)
        self._panel_lay.addWidget(self._anns, stretch=1)
        if _had_focus:
            self._anns.focus_tree()
        self._refresh_image()

    def _on_merge(self) -> None:
        """병합 선택된 object 들을 합집합 bbox + 합집합 mask 의 한 object 로 병합한다."""
        if not self._editable:
            return
        _sel = self._anns.checked_merge()
        if len(_sel) < 2:
            return

        # 합집합 mask (선택 중 mask 있는 것들의 OR)
        _masks = [_m for _, _, _m in _sel if _m is not None]
        _union: np.ndarray | None = None
        if _masks:
            _union = np.zeros(_masks[0].shape[:2], np.uint8)
            for _m in _masks:
                _union[_m > 0] = 1

        # 합집합 bbox (각 bbox 포함; bbox 없으면 합집합 mask 외접으로)
        _boxes = [_bbox_of(_o) for _, _o, _ in _sel if _bbox_of(_o) is not None]
        if _boxes:
            _bb = [min(_b[0] for _b in _boxes), min(_b[1] for _b in _boxes),
                   max(_b[2] for _b in _boxes), max(_b[3] for _b in _boxes)]
        elif _union is not None and _union.any():
            _ys, _xs = np.where(_union > 0)
            _bb = [float(_xs.min()), float(_ys.min()),
                   float(_xs.max() + 1), float(_ys.max() + 1)]
        else:
            _bb = None

        # class_id 는 선택 중 첫 비어있지 않은 값
        _cls = next((Attr(_o, "class_id") for _, _o, _ in _sel if Attr(_o, "class_id")),
                    Attr(_sel[0][1], "class_id"))

        # 병합 대상 제거(= 그 obj_id key 제거) + 겹치지 않는 새 obj_id 부여
        _merged_ids = {_oid for _oid, _, _ in _sel}
        _remain = {_k: _v for _k, _v in self._work.info.items()
                   if not (_v.Is_stem() and _k in _merged_ids)}
        _i = 0
        while str(_i) in _remain:
            _i += 1
        _new_id = str(_i)

        _data: dict = {"class_id": Data_Ref(type="attr", info={"value": _cls})}
        if _bb is not None:
            _data["bbox"] = Data_Ref(type="attr", format="xyxy",
                                     info={"value": [float(_v) for _v in _bb]})
        _remain[_new_id] = Data_Ref(type="stem", info=_data)
        self._work.info = _remain

        # rebuild 시 주입할 mask 스냅샷: 남은 것 유지 + 병합본(합집합) 추가
        _snap = self._anns.snapshot_masks()
        for _oid, _, _ in _sel:
            _snap.pop(_oid, None)
        _snap[_new_id] = (_union, True)
        self._rebuild_panel(_snap)
        self._commit()

    def _build_data_tree(self) -> QTreeWidget:
        """stem 바로 아래 frame ``info`` 의 leaf Data_Ref 를 체크박스 트리로 만든다 (객체=stem 은 제외)."""
        _tree = make_tree(hidden=True)
        _root = QTreeWidgetItem(_tree, ["데이터"])
        _root.setExpanded(True)

        _first_unset = True
        for _key, _val in self._work.info.items():
            if not isinstance(_val, Data_Ref) or _val.Is_stem():
                continue
            _it = QTreeWidgetItem(_root, [_key])
            _it.setData(0, Qt.ItemDataRole.UserRole, _key)
            _it.setFlags(_it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if _key in self._bases:
                if _key in self._data_vis:                  # 이전 토글 복원 (stem 넘어 유지)
                    _checked = self._data_vis[_key]
                else:                                       # 처음 보는 키 → 첫 이미지만 기본 ON
                    _checked = _first_unset
                    self._data_vis[_key] = _checked
                if _checked:
                    _first_unset = False
                _it.setCheckState(
                    0, Qt.CheckState.Checked if _checked else Qt.CheckState.Unchecked)
            else:
                _it.setCheckState(0, Qt.CheckState.Unchecked)
                _it.setFlags(_it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                _it.setText(0, f"{_key} (이미지 아님)")
            self._data_items[_key] = _it

        _tree.itemChanged.connect(self._on_data_changed)
        return _tree

    def _on_data_changed(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        """데이터 키 체크가 바뀌면 ``_data_vis`` 에 기록하고(유지용) 화면을 다시 그린다."""
        _key = item.data(0, Qt.ItemDataRole.UserRole)
        if _key is not None:
            self._data_vis[_key] = item.checkState(0) == Qt.CheckState.Checked
        self._refresh_image()

    # ── 동작 ────────────────────────────────────────────────────────────────
    def _selected_bases(self) -> list[np.ndarray]:
        """체크된 데이터 키 중 이미지로 로드된 것들을 순서대로 모은다."""
        return [
            self._bases[_key]
            for _key, _it in self._data_items.items()
            if _key in self._bases
            and _it.checkState(0) == Qt.CheckState.Checked
        ]

    def _on_brightness(self, value: int) -> None:
        """표시용 밝기 값을 바꾸고 화면만 다시 그린다 (저장 데이터 불변)."""
        self._brightness = value
        self._refresh_image()

    def _refresh_image(self, *_args) -> None:
        _base = _overlay.adjust_brightness(
            _overlay.merge_bases(self._selected_bases()), self._brightness)
        _layers = self._anns.layers()
        _size = None
        if _base is None:
            for _ly in _layers:
                if _ly.get("mask") is not None:
                    _size = _ly["mask"].shape[:2]
                    break

        _preview = self._draw.preview_rect()
        _preview_circle = self._draw.preview_circle()
        _preview_poly = self._draw.preview_poly()
        _preview_brush = self._draw.preview_brush()
        # 코너·변 핸들은 bbox 를 편집하는 view 모드에서만 (그리기/RoI 중엔 방해되니 숨김).
        _handles = None
        _edge_handles = None
        if self._draw.mode == "view":
            _obj = self._anns.selected_obj()
            if _obj is not None:
                _bb = _bbox_of(_obj)
                if _bb is not None:
                    _handles = _corners(_bb)
                    _edge_handles = [(_x, _y) for _x, _y, _ in _edge_midpoints(_bb)]

        _img = _overlay.compose(
            _base, _layers, size=_size, handles=_handles, edge_handles=_edge_handles,
            preview=_preview, preview_circle=_preview_circle, preview_poly=_preview_poly,
            preview_brush=_preview_brush)
        self._view.set_image(_img)

    # ── 편집 모드 ────────────────────────────────────────────────────────────
    def _set_mode(self, mode: str) -> None:
        """편집 조작을 바꾼다 (툴바 버튼·단축키 → 컨트롤러로 위임)."""
        if not self._editable and mode != "view":     # 잠금 중엔 보기만 허용
            return
        self._draw.set_mode(mode)

    def _set_shape(self, shape: str) -> None:
        """mask 편집 모양을 바꾼다 (툴바 버튼·단축키 → 컨트롤러로 위임)."""
        if not self._editable:
            return
        self._draw.set_shape(shape)
        self._update_fill_ui()

    def _update_fill_ui(self) -> None:
        """채우기 모양이 활성일 때만 채우기 전용 컨트롤(ROI·허용)을 노출하고 굵기는 숨긴다."""
        _is_fill = self._draw.shape == "fill"
        self._fill_controls.setVisible(_is_fill)
        self._brush_controls.setVisible(not _is_fill)

    def _fill_at(self, x: int, y: int, erase: bool) -> bool:
        """seed ``(x, y)`` 중심 '채우기 반경' 원 안에서 색 유사 + LoG edge 경계까지 채워 활성 mask 에 적용.

        원형 ROI 반경은 채우기 전용 ``_fill_radius`` (브러시 굵기와 독립), 색 허용오차는 ``_tolerance``.
        보이는 base(선택된 데이터 병합)를 기준으로 채운다 — base 가 없으면 no-op(조용한 전체 채움 금지).

        Args:
            x: seed 원본 픽셀 x.
            y: seed 원본 픽셀 y.
            erase: True면 지우고, False면 칠한다.

        Returns:
            채운 대상이 있었으면 True.
        """
        _base = _overlay.merge_bases(self._selected_bases())
        if _base is None:
            return False
        _region = _fill.magic_wand(_base, (x, y), self._tolerance, self._fill_radius)
        if _region is None:
            return False
        return self._anns.fill_region_active(_region, erase, self._canvas_size())

    def _canvas_size(self) -> tuple[int, int] | None:
        """새 mask 를 만들 때 쓸 캔버스 크기 ``(H, W)`` (base 우선, 없으면 기존 mask)."""
        for _im in self._bases.values():
            return _im.shape[:2]
        for _ly in self._anns.layers():
            if _ly.get("mask") is not None:
                return _ly["mask"].shape[:2]
        return None

    # ── 편집 실행취소 / 다시실행 ───────────────────────────────────────────────
    def _snapshot(self):
        """현재 편집 상태(작업 Frame + 노드 mask)를 스냅샷으로 만든다."""
        return (deepcopy(self._work), self._anns.snapshot_masks())

    def _reset_history(self) -> None:
        """이력을 현재 상태 한 칸으로 초기화한다 (stem 로드 직후)."""
        self._history.reset()

    def _commit(self) -> None:
        """현재 편집 상태를 이력에 적재한다 (bbox 확정·스트로크 종료·병합 등)."""
        self._history.commit()

    def _restore(self, state) -> None:
        """스냅샷 상태로 작업본/패널을 되돌린다 (스냅샷은 복사해 격리; ``Edit_history`` 콜백)."""
        _frame, _masks = state
        self._work = deepcopy(_frame)
        self._rebuild_panel({
            _id: (None if _m is None else _m.copy(), _d)
            for _id, (_m, _d) in _masks.items()
        })

    def undo(self) -> None:
        """편집 실행취소 — 직전 이력 상태로 되돌린다 (단축키 Ctrl+Z)."""
        if not self._editable:
            return
        self._history.undo()

    def redo(self) -> None:
        """편집 다시실행 — 취소했던 다음 이력 상태로 되돌린다 (단축키 Ctrl+Y)."""
        if not self._editable:
            return
        self._history.redo()

    # ── 저장 ────────────────────────────────────────────────────────────────
    def save(self) -> None:
        """작업 사본을 meta 의 같은 상태 버킷에 되쓰고 저장을 알린다.

        반영 전에 모든 객체 mask 를 인스턴스 ``segment`` 한 장으로 합치며 obj_id 를 압축한다
        (``_segment.write_segment`` — 지워진 객체 정리 + 재번호). 파일은 이 stem 의 상태 루트
        (``{root}/{state}``)에 저장한다. 상태 승격(stage/commit)은 하지 않는다 — 그건 목록의
        버튼이 ``meta.Move`` 로 따로 한다. ``saved`` 에 저장한 stem 을 실어 보낸다.
        """
        if not self._editable:                # 잠금 중(백그라운드 작업)엔 저장 금지
            return
        _segment.write_segment(
            self._meta.State_root(self._state), self._stem, self._work,
            self._anns.all_masks(), self._bbox_orig, self._canvas_size())
        self._meta.Bucket(self._state)[self._stem] = self._work
        self.saved.emit(self._stem)
