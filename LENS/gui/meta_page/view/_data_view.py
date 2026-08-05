"""데이터 뷰어 — 체크된 raster 를 합성해 그리고, 선택 노드의 값을 편집한다.

**이미지 편집창이 아니라 데이터 뷰어다.** 이미지는 그중 한 종류일 뿐이고, 무엇을 어떻게 그릴지는
[`gui/viewer`](../../viewer) 의 레지스트리가 안다. 그래서 새 종류(depth·points3d…)가 생겨도 여기를
안 고친다 — 뷰어 하나만 더하면 된다.

**편집기는 하나다.** [`Image_editor`](../../editor/image/_editor.py) 는 여기서 한 번 만들어 계속 살고,
노드를 고르면 그 대상으로 **조준**만 바뀐다(만들었다 버리지 않는다). 무엇을 겨눌지는 **구조**가 정하고,
그 규칙은 이 파일이 소유한다 — 뷰어는 트리를 모르고, 편집기는 store 도 트리도 모른다:

| 고른 것 | 겨누는 것 | 칠할 값 |
|---|---|---|
| 객체(BRANCH), 또는 객체 안의 값 | **그 객체의 `mask`**(rle 인라인) | 1 |
| 이진 mask leaf (`roi` 등) | 그 라스터 자체 | 1 |
| 그 밖 | 없음 (왜인지 툴바가 말한다) | — |

**객체마다 자기 mask 를 든다** — 한때 프레임 라벨맵 한 장(`segment`)에 obj_id+1 로 겹쳐 담았지만
(겹침·255 한계), 이제 각 객체가 `("mask", "rle")` 로 자기 픽셀을 든다. 편집기는 그 이진 배열을 칠하고
(rle↔배열 왕복은 이 계층이 든다), 표시는 객체 mask 들을 [`Compose`](../../../core/func/mask/instance.py)
로 라벨맵을 **재구성**해 보여준다(화면은 그대로, truth 만 객체별). 라벨맵은 표시·계산의 파생이다.

**캔버스에서 고른 것도 여기가 답한다** — 편집기는 "여기 뭐가 있냐"(`picked`)고 묻기만 하고, bbox 를 든
객체를 찾아 트리에 알리는 건 트리를 아는 이 계층의 일이다.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from core.format import rle
from core.func.cv.geom import Clip_to_box
from core.func.mask.instance import Compose
from core.schema import Data_Ref
from gui.editor.format import bbox
from gui.editor.image import Image_editor, Target
from gui.viewer import Viewer_for
from gui.viewer._compose import compose

from ._node_tree import Node


class Data_view(QWidget):
    """캔버스(체크된 layer 합성 + 편집기) + 인스펙터(선택 노드 값 편집).

    Attributes:
        edited: 인라인 값이 편집됨 ``(Node)`` — **어느 트리의 노드인지** 상위가 알아야 어디에 저장할지
            정할 수 있다(stem 사이드카 vs params).
        raster_edited: 라스터가 편집됨 ``(Node, raster)`` — 파일 payload 라 store 가 써야 한다.
        object_picked: 캔버스에서 객체를 골랐다 ``(Node, additive)`` — 상위가 객체 트리의 선택을 옮긴다
            (``additive`` = Shift, 기존 선택에 **더한다** → 여러 개를 집어 바로 병합).
    """

    edited        = Signal(object)
    raster_edited = Signal(object, object)
    object_picked = Signal(object, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ctx: dict = {}
        self._class_names: dict[str, str] = {}   # class_id → 이름 (상자 라벨 표시용; 상위가 채운다)
        self._layers: list[Node] = []       # 지금 그린 layer (편집 미리보기에 재사용)
        self._objects: list[Node] = []      # 선택 stem 의 객체들 (bbox 를 그린다)
        self._visible_masks: set[str] = set()   # mask 를 그릴 객체 id (객체 트리 체크) — 상위가 준다
        self._edit_node: Node | None = None  # 편집기가 겨눈 **라스터를 든 노드** (저장 대상)
        self._aim_obj: Node | None = None    # 겨눈 객체 (bbox·mask 를 쓸 곳)
        self._edit_arr: np.ndarray | None = None  # 조준 객체 mask 의 편집 배열 (rle 를 푼 사본)

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _split = QSplitter(Qt.Orientation.Vertical)

        self._editor = Image_editor()                     # 앱에 하나 — 대상만 갈아끼운다
        self._canvas = self._editor.canvas                # 캔버스는 편집기가 소유한다
        self._editor.changed.connect(self._on_raster)
        self._editor.bbox_changed.connect(self._on_bbox)
        self._editor.preview.connect(self._redraw)
        self._editor.display_changed.connect(self._redraw)
        self._editor.picked.connect(self._on_pick)
        _split.addWidget(self._editor)

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

    def focus_editor(self) -> None:
        """이미지 편집기(캔버스)에 키보드 포커스를 준다 (Tab 왕복의 한 끝)."""
        self._canvas.setFocus(Qt.FocusReason.TabFocusReason)

    def canvas_size(self) -> tuple[int, int] | None:
        """지금 캔버스에 뜬 이미지 크기 (H, W) — 빈 라스터를 이 크기로 만든다 (편집기가 든 그 이미지).

        store 를 다시 순회하지 않고 **편집기가 현재 보여주는 것**을 그대로 쓴다 (roi 는 그 위에 그린다).
        """
        return self._canvas.source_size()

    def set_class_names(self, names: dict[str, str]) -> None:
        """상자 라벨에 쓸 ``{class_id: 이름}`` — **어디서 오는지는 상위가 안다**(정본 id_map).

        캔버스는 정본을 모르므로 사전만 받는다. 데이터셋이 바뀌거나 id_map 을 고치면 상위가 다시 준다.

        **여기서 다시 그리지 않는다** — 데이터셋 교체 중에 불리므로, 아직 옛 store 를 가리키는 layer 를
        합성하게 된다. 상위가 목록을 다시 채우면서 어차피 그린다.
        """
        self._class_names = dict(names)

    def set_objects(self, objects: list[Node], *, visible: set[str]) -> None:
        """선택 stem 의 객체들 — bbox 는 raster 가 아니라 attr 이라 layer 로 안 오고, 조준의 단위다.

        stem 이 바뀌면 겨눴던 객체는 **더 이상 없다** — 조준을 놓는다(옛 stem 의 라스터를 계속 칠하지
        않도록). 다음 stem 의 노드를 고르면 그 meta 에서 읽은 값으로 다시 겨눈다.

        Args:
            objects: 이 stem 의 객체 전부 — bbox 와 조준은 체크와 무관하게 **다** 필요하다.
            visible: mask 를 그릴 객체 id — 객체 트리에서 체크된 것들. 객체 mask 는 한 장의 라벨맵으로
                합쳐 그리므로(:meth:`_objects_layer`) 어느 걸 넣을지 **여기서** 갈린다. 이걸 안 보고
                전부 그리면 체크박스가 달려 있어도 아무 일도 안 일어난다.
        """
        self._objects = list(objects)
        self._visible_masks = set(visible)
        if self._aim_obj is not None and not any(_o is self._aim_obj for _o in self._objects):
            self._aim(None)

    def show_layers(self, nodes: list[Node]) -> None:
        """체크된 노드들을 합성해 캔버스에 그린다 (없으면 비운다).

        합성(데이터가 무엇인가)은 뷰어가, 그 위의 오버레이(지금 무엇을 하려는가)는 편집기가 그린다 —
        `decorate` 가 그 경계다.
        """
        self._layers = list(nodes)
        _layers = []
        for _n in nodes:
            _v = Viewer_for(_n.ref)
            if _v is None:
                continue
            _raster = _v.layer(_n.value, _n.ref)
            if _raster is not None:
                _layers.append((_raster, _n.ref.format[0]))
        _seg = self._objects_layer()                     # 객체 mask 들 → 표시용 라벨맵 (파생)
        if _seg is not None:
            _layers.append((_seg, "segmap"))
        if not _layers:
            self._canvas.clear_image("표시할 데이터가 없습니다 (트리에서 체크하세요)")
            return
        _img = compose(_layers, boxes=self._boxes())
        if _img is None:
            self._canvas.clear_image("합성 실패")
            return
        self._canvas.set_image(self._editor.decorate(_img))

    def _redraw(self) -> None:
        """편집 중 미리보기·표시 옵션 변경 — 지금 layer 그대로 다시 그린다."""
        self.show_layers(self._layers)

    def show_node(self, node: Node | None, *, candidates=None,
                  aim: bool = True, editable: bool = True) -> None:
        """선택 노드 → 인스펙터에 값을 띄운다.

        ``aim`` 이면 편집기를 그 대상으로 **조준**하고(칠할 수 있게), ``editable`` 이면 값 편집 패널을
        준다. params 같은 **전역 값은 선택만으론 조준·편집하지 않는다**(``aim=False, editable=False`` 로
        읽기전용 미리보기) — 무심코 칠하면 전 stem 에 파급되므로 명시적 [수정]에서만 둘 다 켠다.
        """
        self._aim(node if aim else None)
        self._clear_inspector()
        if node is None:
            self._inspector_lay.addWidget(self._label("노드를 선택하세요"))
            return
        _viewer = Viewer_for(node.ref)
        if _viewer is None:
            self._inspector_lay.addWidget(
                self._label(f"{node.name} — 뷰어 없음 ({node.ref.format[0]})"))
            return
        if not editable:                                  # 미리보기 — 읽기전용 요약만 (편집은 [수정]에서)
            self._inspector_lay.addWidget(QLabel(f"<b>{node.name}</b>"))
            self._inspector_lay.addWidget(self._label(_viewer.summary(node.value, node.ref)))
            self._inspector_lay.addStretch(1)
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
        self._edit_arr = None
        _target, _hint = self._resolve(node)
        self._editor.aim(_target, hint=_hint)
        self._center_on_aim()

    def _center_on_aim(self) -> None:
        """겨눈 객체가 화면 밖이면 끌어온다 — 줌해서 칠하는 중에 객체를 바꾸면 딴 데를 보고 있게 된다.

        (fit 모드로 다 보이는 중이면 스크롤바가 없어 사실상 no-op.)
        """
        _aimed = _box_of(self._aim_obj) if self._aim_obj is not None else None
        if bbox.is_set(_aimed):
            _center = _aimed.mean(axis=0)
            self._canvas.center_on(_center[0], _center[1])

    def _resolve(self, node: Node | None) -> tuple[Target | None, str]:
        """무엇을 겨눌지 — 겨눌 게 없으면 **왜 없는지**를 함께 돌려준다(조용히 안 죽는다)."""
        if node is None:
            return None, "노드를 선택하세요"

        _viewer = Viewer_for(node.ref)
        if node.is_leaf and _viewer is not None and _viewer.EDITABLE and _is_mask(node.value):
            self._edit_node = node                       # 이진 mask leaf (roi 등) — 자기 자신을 칠한다
            return Target(raster=node.value, paint=1, base=self._base_image(),
                          name=node.name, key=_key_of(node)), ""

        _obj = self._object_of(node)                     # 객체이거나, 그 안의 값을 고른 것이거나
        if _obj is None:
            return None, "객체를 고르면 그 mask 를 칠할 수 있습니다"
        _size = self.canvas_size()
        if _size is None:
            return None, "이미지를 먼저 표시하세요 — 트리에서 프레임을 체크하세요"

        self._edit_node, self._aim_obj = _obj, _obj
        self._edit_arr = _obj_mask(_obj, _size)          # 객체 mask 를 배열로 (없으면 빈 것)
        return Target(raster=self._edit_arr, paint=1, base=self._base_image(),
                      bbox=_box_of(_obj), name=f"객체 {_obj.name}", key=_key_of(_obj)), ""

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

    def _objects_layer(self) -> np.ndarray | None:
        """선택 stem 의 객체 mask 들을 표시용 라벨맵 한 장으로 **재구성**한다 (없으면 None).

        truth 는 객체별 mask(rle)지만 화면은 지금처럼 라벨맵으로 보인다 — 색은 `Compose` 가 픽셀에
        obj_id+1 을 찍고 [`compose`](../../viewer/_compose.py) 가 라벨별로 칠한다(bbox 색과 맞는다).

        **조준 중인 객체는 편집 배열(`_edit_arr`)을 쓴다** — 저장 안 한 붓질이 그 안에 있으므로, rle 로
        굳기 전의 픽셀을 그대로 얹어야 칠하는 게 즉시 보인다.
        """
        if not self._objects:
            return None
        _size = self.canvas_size()
        if _size is None:
            return None
        _masks: dict[str, np.ndarray] = {}
        for _o in self._objects:
            if _o.name not in self._visible_masks:         # 체크 꺼짐 — 이 객체만 안 그린다
                continue
            if _o is self._aim_obj and self._edit_arr is not None:
                _masks[_o.name] = self._edit_arr        # 편집 중 — 굳기 전 붓질
            else:
                _ref = _o.ref.Get("mask")
                _val = _ref.info.get("value") if _ref is not None else None
                if _val:
                    _masks[_o.name] = rle.To_mask(_val)
        return Compose(_size, _masks) if _masks else None

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
    def _on_raster(self, target) -> None:
        """편집 확정 — 겨눈 것이 **객체 mask** 면 rle 인라인으로, **leaf 라스터**(roi)면 파일로 저장한다.

        객체 mask 는 편집 배열(``_edit_arr``)을 rle 로 굳혀 서술자에 담는다(bbox 와 같은 인라인 경로 →
        사이드카). roi 같은 파일 mask 는 제자리 배열이라 store 가 파일로 write 한다(``raster_edited``).
        """
        if self._aim_obj is not None:                    # 객체 mask → rle 인라인 (사이드카)
            _raster = target.raster
            _box = self._aim_obj.ref.Get("bbox")         # region 이 있으면 그 안 픽셀만 남긴다
            if _box is not None and _box.info.get("value"):
                _raster = Clip_to_box(_raster, _box.info["value"])
                self._edit_arr[...] = _raster            # 편집 배열도 잘린 상태로 (display 일관)
            _value = rle.From_mask(_raster)
            _ref = self._aim_obj.ref.Get("mask")
            if _ref is None:
                self._aim_obj.ref.Push("mask", Data_Ref(format=("mask", "rle"),
                                                        info={"value": _value}))
            else:
                _ref.info["value"] = _value
            self._redraw()
            self.edited.emit(self._aim_obj)
        elif self._edit_node is not None:                # leaf 라스터(roi) → 파일
            self._edit_node.value = target.raster
            self._redraw()
            self.raster_edited.emit(self._edit_node, target.raster)

    def _on_bbox(self, box) -> None:
        """상자가 바뀌었다(그리기·핸들·undo) — 겨눈 객체의 ``bbox`` attr 을 만들거나 갱신한다(인라인).

        편집기는 정준형 상자를 내고, 서술자에 담기는 건 평탄 리스트다 — 그 변환이 이 계층의 일이다.
        """
        if self._aim_obj is None:
            return
        _value = bbox.to_flat(box)
        _ref = self._aim_obj.ref.Get("bbox")
        if _ref is None:
            self._aim_obj.ref.Push("bbox", Data_Ref(format=("region", "bbox", "xyxy"),
                                                    info={"value": _value}))
        else:
            _ref.info["value"] = _value
        if self._edit_arr is not None:                   # 새 box 밖 mask 는 이 객체 것이 아니다 → 자른다
            self._edit_arr[...] = Clip_to_box(self._edit_arr, _value)
            _mref = self._aim_obj.ref.Get("mask")        # 저장 rle 도 잘린 상태로 (display·영속 일관)
            if _mref is not None and _mref.info.get("value"):
                _mref.info["value"] = rle.From_mask(self._edit_arr)
        self._redraw()
        self.edited.emit(self._aim_obj)

    def _on_pick(self, x: int, y: int, additive: bool) -> None:
        """캔버스에서 골랐다 — 그 점을 품는 bbox 의 객체를 찾아 상위에 알린다.

        **겹치면 작은 상자가 이긴다** — 큰 상자 안에 든 작은 객체를 영영 못 고르는 일이 없게.
        편집기는 여기까지 못 온다(트리를 모른다) — 그래서 좌표만 주고 답을 기다린다.
        """
        _hits = [(_o, bbox.measure(_box_of(_o))) for _o in self._objects
                 if bbox.inside(_box_of(_o), (x, y))]
        if _hits:
            self.object_picked.emit(min(_hits, key=lambda _h: _h[1])[0], additive)

    def _boxes(self) -> list[tuple[list, int, str]]:
        """객체들의 bbox (+ 그리는 중인 미리보기) — 색은 라벨과 맞추고, 이름은 편집기가 켰을 때만.

        합성은 평탄 ``[x0, y0, x1, y1]`` 을 먹으므로 여기서 정준형을 되돌린다 (`_box_of` 의 짝).

        **상자 표시를 끄면 겨눈 것만 남는다** — 상자는 mask 위를 덮어 아래 픽셀을 가리므로 걷어낼 수
        있어야 하지만, 지금 그리는 중인 상자까지 지우면 드래그로 bbox 를 못 맞춘다.
        """
        _out: list[tuple[list, int, str]] = []
        _aimed = self._aim_obj.name if self._aim_obj is not None else None
        for _o in self._objects if self._editor.show_boxes() else ():
            if _o.name == _aimed:                    # 겨눈 객체는 아래에서 미리보기로 그린다
                continue
            _flat = bbox.to_flat(_box_of(_o))
            if _flat:
                _out.append((_flat, _index_of(_o.name), self._caption(_o)))
        if _aimed is not None:
            _preview = bbox.to_flat(self._editor.preview_box())
            if _preview:
                _out.append((_preview, _index_of(_aimed), self._caption(self._aim_obj)))
        return _out

    def _caption(self, obj: Node) -> str:
        """상자에 적을 이름 — ``obj_id`` + (있으면) class **이름**. 표시를 끄면 빈 문자열.

        저장된 ``class_id`` 는 번호라 그대로 적으면 ``241`` 이 된다 — 사람이 읽는 건 이름이므로
        :meth:`set_class_names` 로 받은 id_map 으로 되돌린다. 모르는 번호는 **번호 그대로 드러낸다**
        (id_map 에 없는 라벨을 조용히 빈칸으로 만들면 잘못된 걸 눈치챌 수 없다).
        """
        if not self._editor.show_labels():
            return ""
        _ref = obj.ref.Get("class_id")
        _cid = str(_ref.info.get("value")) if _ref is not None else None
        if _cid is None or _cid == "":
            return obj.name
        return f"{obj.name} · {self._class_names.get(_cid, _cid)}"

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


def _box_of(node: Node) -> np.ndarray:
    """객체의 bbox — [`format/bbox`](../../editor/format/bbox.py) 정준형 (없으면 빈 상자).

    상자는 raster 가 아니라 인라인 attr 이라 서술자에 평탄 리스트로 산다. **평탄 ↔ 정준형 변환은 이
    경계에서만** 한다 — 편집기 안으로 리스트를 들이면 "길이가 4"가 곳곳에 박힌다.
    """
    _ref = node.ref.Get("bbox")
    return bbox.from_flat(_ref.info.get("value") or [] if _ref is not None else [])


def _obj_mask(obj: Node, size: tuple[int, int]) -> np.ndarray:
    """객체의 mask 를 편집용 배열로 — rle 서술자를 풀어 **사본**을, 없으면 빈 mask(그리기 시작).

    편집기는 이 배열을 제자리에서 칠하고, 확정되면 이 계층이 다시 rle 로 굳힌다(`_on_raster`). mask 가
    rle 인라인이라 서술자(``obj.ref.Get("mask").info["value"]``)에 값이 직접 있어 store 를 안 부른다.
    """
    _ref = obj.ref.Get("mask")
    _val = _ref.info.get("value") if _ref is not None else None
    return rle.To_mask(_val).copy() if _val else np.zeros(size, np.uint8)


def _key_of(node: Node) -> tuple:
    """조준 대상 식별 — 이게 바뀌면 편집기가 undo 이력을 비운다 (다른 라스터니까)."""
    return (node.path, node.name, id(node.value))


def _index_of(obj_id: str) -> int:
    try:
        return int(obj_id)
    except (TypeError, ValueError):
        return 0
