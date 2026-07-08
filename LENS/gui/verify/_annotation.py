"""object 트리 패널 — 시각화 토글 + 값 편집 + mask 브러시/병합 (mask 는 프레임 segment 에서 파생)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.data.handler import Data_Ref
from core.data.meta import Dataset_Meta
from gui.verify import _overlay
from gui.verify._edit_form import _Ann_edit_form
from gui.verify._helpers import _bbox_of, _color_icon
from gui.widgets import make_tree


@dataclass
class _Ann_node:
    """트리 노드 하나에 묶인 object 의 시각화/편집 메타 (obj_id = 부모 info 의 key)."""

    obj: Data_Ref
    obj_id: str
    color: tuple[int, int, int]
    mask: np.ndarray | None
    mask_item: QTreeWidgetItem | None
    bbox_item: QTreeWidgetItem | None
    item: QTreeWidgetItem
    form: "_Ann_edit_form"
    dirty: bool = False                # mask 가 그리기/지우기로 수정됨 (저장 시 영속화 대상)
    sel: "QCheckBox | None" = None     # 병합 선택 체크박스 (트리 컬럼1 임베드)

    def layer(self) -> dict:
        """현재 체크 상태를 반영한 compose 레이어를 만든다."""
        _show_mask = (self.mask_item is not None
                      and self.mask_item.checkState(0) == Qt.CheckState.Checked)
        _show_bbox = (self.bbox_item is not None
                      and self.bbox_item.checkState(0) == Qt.CheckState.Checked)
        return {
            "mask": self.mask,
            "bbox": _bbox_of(self.obj),
            "color": self.color,
            "show_mask": bool(_show_mask),
            "show_bbox": bool(_show_bbox),
        }


class _Annotation_panel(QWidget):
    """object 트리(시각화 체크박스) + 선택 항목 편집 폼.

    트리 구조: ``object → [idx] obj_id → mask/bbox``. 체크박스로 시각화를 토글하고
    (부모를 끄면 자식도 함께 꺼진다), object 노드를 선택하면 아래 편집 폼이 바뀐다.

    ``masks`` 를 주면 디스크 대신 그 mask(+dirty)로 노드를 채운다 — 실행취소/다시실행이
    스냅샷을 되돌릴 때 쓴다 (``{obj_id: (mask|None, dirty)}``).

    Attributes:
        changed: 시각화 토글/값 편집으로 화면을 다시 그려야 할 때 emit.
        edited:  object 값/구성이 실제로 바뀌어 실행취소 이력을 남겨야 할 때 emit.
    """

    changed        = Signal()
    edited         = Signal()
    merge_requested = Signal()         # "병합" 버튼 → 체크한 object 들 병합 요청
    object_selected = Signal()         # 현재 object 선택이 바뀜 (이미지 뷰 중앙 이동용)

    def __init__(self, meta: Dataset_Meta, stem: str, work: Data_Ref,
                 masks: dict | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meta = meta
        self._stem = stem
        self._work = work
        self._editable = True              # 편집 잠금 토글 (백그라운드 작업 중엔 보기만)
        self._masks = masks                # obj_id → (mask|None, dirty) 강제 주입 (없으면 segment)
        # 프레임의 인스턴스 라벨맵 1장 — 객체별 mask 는 여기서(segment==obj_id+1) 파생한다.
        self._segment = _overlay.load_segment(meta, stem)
        self._classes: list[str] = []      # TODO(sample): class 목록(id_map)은 sample 소유
        self._nodes: list[_Ann_node] = []
        # object 노드 → _Ann_node — 선택/삭제에 사용.
        self._node_by_item: dict[QTreeWidgetItem, _Ann_node] = {}

        # 컬럼0 = 라벨+시각화 체크, 컬럼1 = 병합 선택 체크박스(object 노드에만 임베드).
        self._tree = make_tree(
            columns=2, hidden=True,
            resize=[QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.Fixed])
        self._tree.header().setStretchLastSection(False)   # 1열을 Fixed 28px 로 고정
        self._tree.setColumnWidth(1, 28)

        # 프레임의 객체(work.info 의 컨테이너 entry)들 — 최상위 "object" 노드 하나로 묶는다.
        _objs = self._obj_items()
        self._top = QTreeWidgetItem(self._tree, [f"object  ({len(_objs)})"])
        self._top.setFlags(self._top.flags()
                           | Qt.ItemFlag.ItemIsUserCheckable
                           | Qt.ItemFlag.ItemIsAutoTristate)
        self._top.setExpanded(True)
        for _i, (_oid, _obj) in enumerate(_objs):
            self._add_obj(self._top, _obj, _oid, _i)
        if _objs:
            self._top.setCheckState(0, Qt.CheckState.Checked)

        self._tree.currentItemChanged.connect(self._on_select)
        self._tree.itemChanged.connect(lambda *_: self.changed.emit())

        self._add_btn = QPushButton("＋ 추가")
        self._add_btn.clicked.connect(self.add_object)
        self._del_btn = QPushButton("－ 삭제")
        self._del_btn.clicked.connect(self.delete_selected)
        self._merge_btn = QPushButton("⛶ 병합")
        self._merge_btn.setToolTip("체크한 object 들을 하나로 병합 (합집합 bbox + mask)")
        self._merge_btn.clicked.connect(self.merge_requested)
        _btn_row = QHBoxLayout()
        _btn_row.addWidget(self._add_btn)
        _btn_row.addWidget(self._del_btn)
        _btn_row.addWidget(self._merge_btn)

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.addLayout(_btn_row)
        _lay.addWidget(self._tree, stretch=1)

    def _obj_items(self) -> list[tuple[str, Data_Ref]]:
        """work.info 의 객체(컨테이너 entry)를 ``(obj_id, ref)`` 리스트로 (트리 순서)."""
        return [(_k, _v) for _k, _v in self._work.info.items() if _v.Is_stem()]

    def focus_tree(self) -> None:
        """object 트리(QTreeWidget)에 키보드 포커스를 준다 (Tab 토글용)."""
        self._tree.setFocus()

    def tree_has_focus(self) -> bool:
        """object 트리(QTreeWidget)가 현재 키보드 포커스를 쥐고 있으면 True (Tab 토글 판정용)."""
        return self._tree.hasFocus()

    def contains_focus(self) -> bool:
        """패널(트리·버튼·편집폼 등) 안 어딘가가 포커스를 쥐고 있으면 True (재구성 시 복원 판정용)."""
        _fw = QApplication.focusWidget()
        return _fw is not None and (_fw is self or self.isAncestorOf(_fw))

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 — 추가/삭제/병합 버튼과 값 편집 폼을 막는다 (시각화 토글·선택은 유지)."""
        self._editable = editable
        self._add_btn.setEnabled(editable)
        self._del_btn.setEnabled(editable)
        self._merge_btn.setEnabled(editable)
        for _n in self._nodes:               # 트리에 임베드된 값 편집 폼(class_id/obj_id/bbox)
            _n.form.setEnabled(editable)

    def selected_node(self) -> _Ann_node | None:
        """현재 선택과 연결된 object 의 _Ann_node 를 반환한다."""
        _it = self._tree.currentItem()
        while _it is not None:
            if _it in self._node_by_item:
                return self._node_by_item[_it]
            _it = _it.parent()
        return None

    def selected_obj(self) -> Data_Ref | None:
        """현재 선택된 object (없으면 None) — 이미지 bbox 편집 대상."""
        _n = self.selected_node()
        return _n.obj if _n is not None else None

    def _node_of_obj(self, obj: Data_Ref) -> _Ann_node | None:
        for _n in self._nodes:
            if _n.obj is obj:
                return _n
        return None

    def set_bbox(self, obj: Data_Ref, values) -> None:
        """object 의 bbox 를 그림 편집 값으로 설정한다 (없으면 생성).

        ``info["bbox"]`` Data_Ref(attr 인라인)를 단일 소스로 갱신하고, 트리 노드의 bbox 키·
        편집 폼 스핀을 동기화한 뒤 ``changed`` 를 emit 한다.

        Args:
            obj: 대상 object.
            values: ``[x0, y0, x1, y1]``.
        """
        _values = [int(_v) for _v in values]
        _ref = obj.info.get("bbox")
        if _ref is None:
            obj.info["bbox"] = Data_Ref(type="attr", info={"value": _values})
        else:
            _ref.info["value"] = _values
        _node = self._node_of_obj(obj)
        if _node is not None:
            if _node.bbox_item is None:                  # 새로 생긴 bbox → 트리 키 추가
                _node.bbox_item = self._add_key(_node.item, "bbox")
            _node.form.set_bbox_values(_values)
        self.changed.emit()

    def _add_obj(self, top: QTreeWidgetItem, obj: Data_Ref, obj_id: str,
                 idx: int) -> QTreeWidgetItem:
        """object 한 개에 대한 트리 노드 + 편집 폼을 만든다 (obj_id = 부모 info key)."""
        _color = _overlay.color_for(idx)
        # masks 주입이 있으면 그 값(스냅샷)으로, 아니면 디스크에서 로드.
        _dirty = False
        if self._masks is not None and obj_id in self._masks:
            _mask, _dirty = self._masks[obj_id]
        else:
            _mask = _overlay.mask_from_segment(self._segment, obj_id)

        _node = QTreeWidgetItem(top, [f"[{idx}] {obj_id}"])
        _node.setIcon(0, _color_icon(_color))
        _node.setFlags(_node.flags()
                       | Qt.ItemFlag.ItemIsUserCheckable
                       | Qt.ItemFlag.ItemIsAutoTristate)

        _has_bbox = _bbox_of(obj) is not None
        _mask_item = self._add_key(_node, "mask") if _mask is not None else None
        _bbox_item = self._add_key(_node, "bbox") if _has_bbox else None

        # 값 편집 폼을 트리 노드 안에 직접 임베드한다 (펼치면 보임).
        _edit_item = QTreeWidgetItem(_node)
        _edit_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # 체크/선택 없는 컨테이너
        _form = _Ann_edit_form(obj, obj_id, self._classes)
        _form.changed.connect(self.changed)
        _form.edited.connect(self.edited)
        _form.renamed.connect(
            lambda text, it=_node, i=idx: self._rename(it, i, text))
        self._tree.setItemWidget(_edit_item, 0, _form)

        _node.setCheckState(0, Qt.CheckState.Checked)

        # 병합 선택 체크박스 (컬럼1 임베드 — 시각화 체크와 별개)
        _sel = QCheckBox()
        _sel.setToolTip("병합 선택")
        self._tree.setItemWidget(_node, 1, _sel)

        _ann_node = _Ann_node(obj, obj_id, _color, _mask, _mask_item, _bbox_item, _node,
                              _form, dirty=_dirty, sel=_sel)
        self._nodes.append(_ann_node)
        self._node_by_item[_node] = _ann_node
        return _node

    def _add_key(self, node: QTreeWidgetItem, key: str) -> QTreeWidgetItem:
        _it = QTreeWidgetItem(node, [key])
        _it.setFlags(_it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        _it.setCheckState(0, Qt.CheckState.Checked)
        return _it

    def _rename(self, item: QTreeWidgetItem, idx: int, text: str) -> None:
        """obj_id 편집을 부모 info key 로 재키잉 + 트리 노드 제목에 반영한다 (체크 시그널 억제).

        obj_id 는 별도 필드가 아니라 ``work.info`` 의 key 라, 여기서 old→new 로 옮긴다(같은 값·
        빈 값·충돌이면 노드 제목만 갱신). ``_Ann_node.obj_id`` 도 동기화.
        """
        _node = self._node_by_item.get(item)
        if _node is not None and text and text != _node.obj_id and text not in self._work.info:
            self._work.info = {(text if _k == _node.obj_id else _k): _v
                               for _k, _v in self._work.info.items()}
            _node.obj_id = text
        self._tree.blockSignals(True)
        item.setText(0, f"[{idx}] {text}")
        self._tree.blockSignals(False)

    def _on_select(self, *_args) -> None:
        """선택이 바뀌면 화면을 다시 그리고(강조용) 선택 변경을 알린다(중앙 이동용)."""
        self.changed.emit()
        self.object_selected.emit()

    def select_at(self, x: int, y: int) -> bool:
        """원본 좌표 ``(x, y)`` 를 품는 bbox 의 object 를 선택한다.

        겹치는 bbox 가 여럿이면 **중심점이 클릭 지점에 가장 가까운** object 를 고른다.

        Args:
            x: 원본 픽셀 x.
            y: 원본 픽셀 y.

        Returns:
            포함하는 object 가 있어 선택했으면 True.
        """
        _best: _Ann_node | None = None
        _best_dist: float | None = None
        for _n in self._nodes:
            _bb = _bbox_of(_n.obj)
            if _bb is None:
                continue
            _x0, _y0, _x1, _y1 = _bb
            if _x0 <= x <= _x1 and _y0 <= y <= _y1:
                _cx, _cy = (_x0 + _x1) / 2, (_y0 + _y1) / 2
                _dist = (_cx - x) ** 2 + (_cy - y) ** 2
                if _best_dist is None or _dist < _best_dist:
                    _best, _best_dist = _n, _dist
        if _best is None:
            return False
        self._tree.setCurrentItem(_best.item)
        return True

    def select_index(self, idx: int) -> bool:
        """idx 번째 object 노드를 선택한다 (숫자키 단축키용).

        Args:
            idx: 선택할 object 인덱스 (0-based).

        Returns:
            해당 인덱스 object 가 있어 선택했으면 True.
        """
        if 0 <= idx < len(self._nodes):
            self._tree.setCurrentItem(self._nodes[idx].item)
            return True
        return False

    # ── object 추가/삭제 ─────────────────────────────────────────────────────
    def _next_obj_id(self) -> str:
        """기존 obj_id(= work.info key)와 겹치지 않는 정수 문자열 id 를 만든다."""
        _used = set(self._work.info)
        _i = 0
        while str(_i) in _used:
            _i += 1
        return str(_i)

    def add_object(self) -> None:
        """``work.info`` 에 빈 object(컨테이너 Data_Ref)를 추가한다 (mask/bbox 없이 class_id/obj_id 만)."""
        _oid = self._next_obj_id()
        _obj = Data_Ref(type="stem", info={})
        self._work.info[_oid] = _obj
        _node = self._add_obj(self._top, _obj, _oid, len(self._nodes))
        self._tree.blockSignals(True)
        self._top.setText(0, f"object  ({len(self._obj_items())})")
        self._tree.blockSignals(False)
        self._tree.setCurrentItem(_node)
        _node.setExpanded(True)
        self.changed.emit()
        self.edited.emit()

    def delete_selected(self) -> None:
        """현재 선택된 object 를 info/트리에서 제거한다."""
        _node = self.selected_node()
        if _node is None:
            return
        self._work.info.pop(_node.obj_id, None)
        self._nodes.remove(_node)
        del self._node_by_item[_node.item]
        self._top.removeChild(_node.item)
        self._tree.blockSignals(True)
        self._top.setText(0, f"object  ({len(self._obj_items())})")
        self._tree.blockSignals(False)
        self.changed.emit()
        self.edited.emit()

    # ── mask 그리기/지우기 ────────────────────────────────────────────────────
    def _active_mask_node(self, size: tuple[int, int] | None) -> _Ann_node | None:
        """활성 object 의 그릴 수 있는(C-연속) mask 노드를 확보한다.

        mask 가 없던 object 면 ``size`` 캔버스로 빈 mask 를 만들고 트리에 mask 키를 추가한다.
        cv2 in-place 그리기는 C-연속 배열을 요구하므로(rle 디코드 mask 는 Fortran order) 필요 시
        연속 배열로 갈아끼운다.

        Args:
            size: mask 가 없을 때 새로 만들 캔버스 크기 ``(H, W)``.

        Returns:
            그릴 준비가 된 노드 (선택 없음/캔버스 모름이면 None).
        """
        _node = self.selected_node()
        if _node is None:
            return None
        if _node.mask is None:
            if size is None:
                return None
            _node.mask = np.zeros(size, dtype=np.uint8)
            if _node.mask_item is None:
                _node.mask_item = self._add_key(_node.item, "mask")
        if not _node.mask.flags["C_CONTIGUOUS"]:
            _node.mask = np.ascontiguousarray(_node.mask)
        return _node

    def paint_active(self, x: int, y: int, radius: int, erase: bool,
                     size: tuple[int, int] | None) -> bool:
        """선택된 object 의 mask 에 원형 브러시로 칠하거나(1) 지운다(0).

        값이 바뀌면 ``changed`` 를 emit 한다 (실행취소 커밋은 상위가 스트로크 종료 시 한다).

        Args:
            x: 원본 픽셀 x.
            y: 원본 픽셀 y.
            radius: 브러시 반지름(px).
            erase: True면 0 으로 지우고, False면 1 로 칠한다.
            size: mask 가 없을 때 새로 만들 캔버스 크기 ``(H, W)``.

        Returns:
            칠한 대상이 있었으면 True (선택 없음/캔버스 모름이면 False).
        """
        _node = self._active_mask_node(size)
        if _node is None:
            return False
        cv2.circle(_node.mask, (int(x), int(y)), max(1, int(radius)),
                   0 if erase else 1, thickness=-1)
        _node.dirty = True
        self.changed.emit()
        return True

    def fill_polygon_active(self, points: list[tuple[int, int]], erase: bool,
                            size: tuple[int, int] | None) -> bool:
        """선택된 object 의 mask 에 다각형(꼭짓점 리스트) 내부를 칠하거나(1) 지운다(0).

        볼록/오목 무관하게 ``cv2.fillPoly`` 로 채운다. 꼭짓점이 3개 미만이면 아무것도 하지 않는다.

        Args:
            points: 다각형 꼭짓점 ``[(x, y), …]`` (원본 픽셀).
            erase: True면 0 으로 지우고, False면 1 로 칠한다.
            size: mask 가 없을 때 새로 만들 캔버스 크기 ``(H, W)``.

        Returns:
            채운 대상이 있었으면 True (선택 없음/캔버스 모름/꼭짓점 부족이면 False).
        """
        if len(points) < 3:
            return False
        _node = self._active_mask_node(size)
        if _node is None:
            return False
        _pts = np.array([[int(_x), int(_y)] for _x, _y in points], dtype=np.int32)
        cv2.fillPoly(_node.mask, [_pts], 0 if erase else 1)
        _node.dirty = True
        self.changed.emit()
        return True

    def fill_region_active(self, region: np.ndarray, erase: bool,
                           size: tuple[int, int] | None) -> bool:
        """미리 계산된 영역(uint8 mask)을 활성 object mask 에 통째로 칠하거나(1) 지운다(0).

        magic-wand 채우기용 — 브러시/다각형과 달리 도형이 아니라 임의 영역(flood fill 결과)을 받는다.

        Args:
            region: ``(H, W)`` uint8 (0/1) 적용할 영역.
            erase: True면 0 으로 지우고, False면 1 로 칠한다.
            size: mask 가 없을 때 새로 만들 캔버스 크기 ``(H, W)``.

        Returns:
            적용했으면 True (선택 없음/캔버스 모름/크기 불일치면 False).
        """
        _node = self._active_mask_node(size)
        if _node is None:
            return False
        _sel = region > 0
        if _sel.shape != _node.mask.shape[:2]:
            return False
        _node.mask[_sel] = 0 if erase else 1
        _node.dirty = True
        self.changed.emit()
        return True

    def snapshot_masks(self) -> dict:
        """현재 노드 mask 상태를 ``{obj_id: (mask복사본|None, dirty)}`` 로 떠 둔다 (실행취소용)."""
        return {
            _n.obj_id: (None if _n.mask is None else _n.mask.copy(), _n.dirty)
            for _n in self._nodes
        }

    def checked_merge(self) -> list[tuple[str, Data_Ref, np.ndarray | None]]:
        """병합 선택 체크된 object 들의 ``(obj_id, obj, mask|None)`` 을 돌려준다 (병합 대상)."""
        return [(_n.obj_id, _n.obj, _n.mask) for _n in self._nodes
                if _n.sel is not None and _n.sel.isChecked()]

    def all_masks(self) -> list[tuple[Data_Ref, np.ndarray | None]]:
        """모든 노드의 ``(obj, mask|None)`` 을 트리 순서(=object 순서)대로 돌려준다.

        저장 시 segment 한 장으로 합치고 obj_id 를 압축하는 데 쓴다 — dirty 여부와 무관하게
        모든 객체 mask 가 필요하다(누락하면 segment 에서 빠진다).
        """
        return [(_n.obj, _n.mask) for _n in self._nodes]

    def layers(self) -> list[dict]:
        """compose 용 레이어 리스트 (체크 상태 반영)."""
        return [_n.layer() for _n in self._nodes]
