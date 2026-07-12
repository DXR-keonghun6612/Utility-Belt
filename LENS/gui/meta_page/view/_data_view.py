"""데이터 뷰어 — 체크된 raster 를 합성해 그리고, 선택 노드의 값을 편집한다.

**이미지 편집창이 아니라 데이터 뷰어다.** 이미지는 그중 한 종류일 뿐이고, 무엇을 어떻게 그릴지는
[`gui/viewer`](../../viewer) 의 레지스트리가 안다. 그래서 새 종류(depth·points3d…)가 생겨도 여기를
안 고친다 — 뷰어 하나만 더하면 된다.

**편집기는 하나다.** 캔버스 위 `Mask_editor` 는 여기서 한 번 만들어 계속 살고, 노드를 고르면 그
대상으로 **조준**만 바뀐다(만들었다 버리지 않는다). 무엇을 겨눌지는 **구조**가 정하고, 그 규칙은 이
파일이 소유한다 — 뷰어는 트리를 모르고, 편집기는 store 를 모른다:

| 고른 것 | 겨누는 것 | 칠할 값 |
|---|---|---|
| 객체(BRANCH), 또는 객체 안의 값 | 프레임의 라벨맵(`segment`) | 그 객체의 라벨 (obj_id+1) |
| 이진 mask leaf (`roi` 등) | 그 라스터 자체 | 1 |
| 그 밖 | 없음 (왜인지 툴바가 말한다) | — |
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from core.schema import Data_Ref
from gui.viewer import Viewer_for
from gui.viewer._compose import compose
from gui.viewer._raster_edit import Mask_editor, Target
from gui.viewer.obj import label_of
from gui.widgets import Image_label

from ._node_tree import Node


class Data_view(QWidget):
    """캔버스(체크된 layer 합성 + 편집기) + 인스펙터(선택 노드 값 편집).

    Attributes:
        edited: 인라인 값이 편집됨 ``(Node)`` — **어느 트리의 노드인지** 상위가 알아야 어디에 저장할지
            정할 수 있다(stem 사이드카 vs params).
        raster_edited: 라스터가 편집됨 ``(Node, raster)`` — 파일 payload 라 store 가 써야 한다.
    """

    edited        = Signal(object)
    raster_edited = Signal(object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ctx: dict = {}
        self._layers: list[Node] = []       # 지금 그린 layer (편집 미리보기에 재사용)
        self._objects: list[Node] = []      # 선택 stem 의 객체들 (bbox 를 그린다)
        self._edit_node: Node | None = None  # 편집기가 겨눈 **라스터를 든 노드** (저장 대상)
        self._aim_obj: Node | None = None    # 겨눈 객체 (bbox 를 쓸 곳)

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _split = QSplitter(Qt.Orientation.Vertical)

        _top = QWidget()
        _top_lay = QVBoxLayout(_top)
        _top_lay.setContentsMargins(0, 0, 0, 0)
        _top_lay.setSpacing(2)
        self._canvas = Image_label("표시할 데이터가 없습니다")
        self._editor = Mask_editor(self._canvas)          # 앱에 하나 — 대상만 갈아끼운다
        self._editor.changed.connect(self._on_raster)
        self._editor.bbox_changed.connect(self._on_bbox)
        self._editor.preview.connect(self._on_preview)
        _top_lay.addWidget(self._editor)
        _top_lay.addWidget(self._canvas, stretch=1)
        _split.addWidget(_top)

        self._inspector = QWidget()
        self._inspector_lay = QVBoxLayout(self._inspector)
        self._inspector_lay.setContentsMargins(6, 6, 6, 6)
        self._inspector_lay.addWidget(self._label("노드를 선택하세요"))
        _split.addWidget(self._inspector)

        _split.setStretchFactor(0, 1)
        _split.setSizes([560, 180])
        _lay.addWidget(_split, stretch=1)

    # ── Public ────────────────────────────────────────────────────────────────
    def set_context(self, ctx: dict) -> None:
        """뷰어에 넘길 주변 정보 (예: ``{"candidates": [...]}`` — 어느 노드에 줄지는 상위가 정한다)."""
        self._ctx = dict(ctx)

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 — 보기(합성·줌)는 유지하고 값 수정·캔버스 편집만 막는다."""
        self._inspector.setEnabled(editable)
        self._editor.set_locked(not editable)

    def set_objects(self, objects: list[Node]) -> None:
        """선택 stem 의 객체들 — bbox 는 raster 가 아니라 attr 이라 layer 로 안 오고, 조준의 단위다.

        stem 이 바뀌면 겨눴던 객체는 **더 이상 없다** — 조준을 놓는다(옛 stem 의 라스터를 계속 칠하지
        않도록). 다음 stem 의 노드를 고르면 그 meta 에서 읽은 값으로 다시 겨눈다.
        """
        self._objects = list(objects)
        if self._aim_obj is not None and not any(_o is self._aim_obj for _o in self._objects):
            self._aim(None)

    def show_layers(self, nodes: list[Node]) -> None:
        """체크된 노드들을 합성해 캔버스에 그린다 (없으면 비운다)."""
        self._layers = list(nodes)
        _layers = []
        for _n in nodes:
            _v = Viewer_for(_n.ref)
            if _v is None:
                continue
            _raster = _v.layer(_n.value, _n.ref)
            if _raster is not None:
                _layers.append((_raster, _n.ref.format[0]))
        if not _layers:
            self._canvas.clear_image("표시할 데이터가 없습니다 (트리에서 체크하세요)")
            return
        _img = compose(_layers, boxes=self._boxes())
        self._canvas.set_image(_img) if _img is not None else self._canvas.clear_image("합성 실패")

    def show_node(self, node: Node | None, *, candidates=None) -> None:
        """선택 노드 → 인스펙터에 값 패널을 띄우고, **편집기를 그 대상으로 조준**한다."""
        self._aim(node)
        self._clear_inspector()
        if node is None:
            self._inspector_lay.addWidget(self._label("노드를 선택하세요"))
            return
        _viewer = Viewer_for(node.ref)
        if _viewer is None:
            self._inspector_lay.addWidget(
                self._label(f"{node.name} — 뷰어 없음 ({node.ref.format[0]})"))
            return

        _ctx = {**self._ctx}
        if candidates is not None:
            _ctx["candidates"] = candidates
        _panel = _viewer.panel(node.value, node.ref, ctx=_ctx,
                               on_change=lambda _v: self._on_change(node, _v))
        if _panel is None:
            self._inspector_lay.addWidget(self._label(_viewer.summary(node.value, node.ref)))
            return
        self._inspector_lay.addWidget(QLabel(f"<b>{node.name}</b>"))
        self._inspector_lay.addWidget(_panel)
        self._inspector_lay.addStretch(1)

    # ── 조준 — **구조가 정한다** ───────────────────────────────────────────────
    def _aim(self, node: Node | None) -> None:
        self._edit_node = None
        self._aim_obj = None
        _target, _hint = self._resolve(node)
        self._editor.aim(_target, hint=_hint)

    def _resolve(self, node: Node | None) -> tuple[Target | None, str]:
        """무엇을 겨눌지 — 겨눌 게 없으면 **왜 없는지**를 함께 돌려준다(조용히 안 죽는다)."""
        if node is None:
            return None, "노드를 선택하세요"

        _viewer = Viewer_for(node.ref)
        if node.is_leaf and _viewer is not None and _viewer.EDITABLE and _is_mask(node.value):
            self._edit_node = node                       # 이진 mask leaf — 자기 자신을 칠한다
            return Target(raster=node.value, paint=1, base=self._base_image(),
                          key=_key_of(node)), ""

        _obj = self._object_of(node)                     # 객체이거나, 그 안의 값을 고른 것이거나
        if _obj is None:
            return None, "객체를 고르면 그 mask 를 칠할 수 있습니다"
        _label = label_of(_obj.name)
        if _label is None:
            return None, f"'{_obj.name}' 은 라벨이 될 수 없습니다 (정수 obj_id 가 아님)"
        _seg = self._segment_node()
        if _seg is None:
            return None, "segment 가 없습니다 — '+ 데이터'로 만들고 트리에서 체크하세요"

        _ref = _obj.ref.Get("bbox")
        _box = [float(_v) for _v in (_ref.info.get("value") or [])] if _ref is not None else []
        self._edit_node, self._aim_obj = _seg, _obj
        return Target(raster=_seg.value, paint=_label, base=self._base_image(),
                      bbox=_box, key=_key_of(_seg)), ""

    def _object_of(self, node: Node) -> Node | None:
        """이 노드가 속한 객체 — 객체 자신이거나, 그 안의 값이거나 (아니면 None).

        객체 안의 값(`class_id` 등)을 고쳐도 **조준은 그 객체에 남는다** — 값을 만지러 갔다가 붓을
        놓치면 라벨링이 끊긴다.
        """
        for _o in self._objects:
            if node.path == _o.path and node.name == _o.name:
                return _o
            if node.path == _o.path + (_o.name,):
                return _o
        return None

    def _segment_node(self) -> Node | None:
        """지금 그려진 layer 중 라벨맵 노드 (객체 mask 가 사는 곳)."""
        for _n in self._layers:
            if _n.ref.format and _n.ref.format[0] == "segmap" and _is_mask(_n.value):
                return _n
        return None

    def _base_image(self) -> np.ndarray | None:
        """체크된 layer 중 첫 BGR 배경 (없으면 None) — 색 기반 채우기의 기준."""
        for _n in self._layers:
            _v = Viewer_for(_n.ref)
            if _v is None:
                continue
            _l = _v.layer(_n.value, _n.ref)
            if _l is not None and _l.ndim == 3:
                return _l
        return None

    # ── 편집 결과 ─────────────────────────────────────────────────────────────
    def _on_raster(self, raster) -> None:
        """편집 확정 — 값은 여기서 갱신하고, **파일 write 는 store 가 한다**(상위가 받는다)."""
        if self._edit_node is None:
            return
        self._edit_node.value = raster
        self.show_layers(self._layers)
        self.raster_edited.emit(self._edit_node, raster)

    def _on_bbox(self, box) -> None:
        """bbox 를 드래그로 그렸다 — 겨눈 객체의 ``bbox`` attr 을 만들거나 갱신한다(인라인)."""
        if self._aim_obj is None:
            return
        _value = [float(_v) for _v in box]
        _ref = self._aim_obj.ref.Get("bbox")
        if _ref is None:
            self._aim_obj.ref.Push("bbox", Data_Ref(format=("attr", "xyxy"),
                                                    info={"value": _value}))
        else:
            _ref.info["value"] = _value
        self.show_layers(self._layers)
        self.edited.emit(self._aim_obj)

    def _on_preview(self) -> None:
        """편집 중 미리보기 — 겨눈 노드의 값을 **잠깐만** 갈아끼워 다시 합성한다.

        원본을 되돌려 놓는 게 핵심이다: 편집기가 겨눈 배열과 트리가 든 배열은 **같은 객체**라
        (제자리 편집), 미리보기 사본을 그대로 꽂아 두면 조준이 끊긴다.
        """
        if self._edit_node is None:
            self.show_layers(self._layers)
            return
        _preview = self._editor.preview_raster()
        if _preview is None:
            return
        _saved = self._edit_node.value
        self._edit_node.value = _preview
        self.show_layers(self._layers)
        self._edit_node.value = _saved

    def _boxes(self) -> list[tuple[list, int]]:
        """객체들의 bbox (+ 그리는 중인 미리보기) — 색은 라벨과 맞춘다."""
        _out: list[tuple[list, int]] = []
        _aimed = self._aim_obj.name if self._aim_obj is not None else None
        for _o in self._objects:
            if _o.name == _aimed:                    # 겨눈 객체는 아래에서 미리보기로 그린다
                continue
            _ref = _o.ref.Get("bbox")
            _box = _ref.info.get("value") if _ref is not None else None
            if _box:
                _out.append((_box, _index_of(_o.name)))
        if _aimed is not None:
            _pv = self._editor.preview_box()
            if _pv:
                _out.append((_pv, _index_of(_aimed)))
        return _out

    # ── 내부 ──────────────────────────────────────────────────────────────────
    def _on_change(self, node: Node, value) -> None:
        """인라인 값 편집 — 서술자에 바로 쓴다(인라인은 사이드카 안에 산다)."""
        node.ref.info["value"] = value
        node.value = value
        if node.name == "bbox":                      # 손으로 고친 좌표도 캔버스에 바로 보인다
            self.show_layers(self._layers)
        self.edited.emit(node)

    @staticmethod
    def _label(text: str) -> QLabel:
        _l = QLabel(text)
        _l.setStyleSheet("color: #888;")
        return _l

    def _clear_inspector(self) -> None:
        while self._inspector_lay.count():
            _it = self._inspector_lay.takeAt(0)
            _w = _it.widget()
            if _w is not None:
                _w.setParent(None)


def _is_mask(value) -> bool:
    """캔버스에서 칠할 수 있는 라스터인가 — **단채널만**(색 이미지는 정본이라 안 건드린다)."""
    return isinstance(value, np.ndarray) and value.ndim == 2


def _key_of(node: Node) -> tuple:
    """조준 대상 식별 — 이게 바뀌면 편집기가 undo 이력을 비운다 (다른 라스터니까)."""
    return (node.path, node.name, id(node.value))


def _index_of(obj_id: str) -> int:
    try:
        return int(obj_id)
    except (TypeError, ValueError):
        return 0
