"""메인 본문 — stem 목록 + (params · 데이터 · 객체) 트리 + 데이터 뷰어 (``Pipeline`` 구동). 설계는 README.

```text
[stem 목록]   ┌ params  (dataset-wide) ┐   [데이터 뷰어]
 범주 뱃지     ├────────────────────────┤    체크된 raster 합성 + 선택 노드 편집
              │ 데이터  (선택 stem)     │ ← raster leaf(frame·segment·roi) — 체크=합성
              ├────────────────────────┤
              │ 객체    (선택 stem)     │ ← 객체(BRANCH)+attr — 선택=조준/편집
              └────────────────────────┘   각 섹션은 접힌다(Collapsible)
```

**같은 재귀 렌더러(`Node_tree`)를 scope 로 세 번 쓴다** — params / 데이터(leaf) / 객체(objects). 데이터모델은
하나(재귀 ``Data_Ref``)지만 **표현 축이 다르다**: raster 는 체크해서 합성하고, 객체는 골라서 조준·편집한다.
예전엔 그 셋을 한 트리에 합쳐 놓고 top-level 을 훑어 객체를 추론했는데(축이 섞여 있었다), 여기서 축대로
가른다. core 데이터모델은 그대로다 — 정돈은 표현 계층의 일이지 저장 구조의 일이 아니다.

**params 는 stem 목록에 안 넣는다** — dataset-wide 라 stem 의 형제가 아니다. 화면에서도 축이 다르다:
stem 을 바꿔도 params 는 그대로 있고, 그 raster(예: `roi`)는 어느 stem 위에든 겹쳐 볼 수 있다.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui.meta_page.view._data_view import Data_view
from gui.meta_page.view._node_panel import Node_panel
from gui.meta_page.view._node_tree import Node
from gui.meta_page.view._params_panel import Params_panel
from gui.meta_page.view._stem_list import Stem_list
from gui.widgets import Collapsible


class Meta_view(QWidget):
    """staging 본문 — stem 목록 + (데이터·객체) 트리 + 데이터 뷰어.

    Attributes:
        meta_changed: 내용이 편집돼 영속됐을 때 emit (상위 알림용).
        transition_requested: 대량 stem 전이 요청 ``(to_state, [stem…])`` — 상위가 백그라운드로 실행.
        remove_requested: 대량 stem 삭제 요청 ``[stem…]`` — 상위가 백그라운드로 실행.
    """

    meta_changed         = Signal()
    transition_requested = Signal(str, list)
    remove_requested     = Signal(list)

    def __init__(self, pipeline=None, parent=None) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._editable = True                # 편집 잠금 (백그라운드 작업 중엔 보기만)
        self._key: str = ""                  # 지금 트리에 열린 item (stem 또는 params)
        self._dirty = False                  # 저장 안 된 편집(값·라스터)이 있나 — 명시적 저장 대기
        self._dirty_params = False           # 그중 params 노드가 있나 (전체 저장 필요)
        self._pending_rasters: list[Node] = []  # 저장 시 Route 할 라스터 노드 (payload 는 저장 때 flush)
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)

        _top = QHBoxLayout()
        self._save_btn = QPushButton("저장")
        self._save_btn.setToolTip("이 stem 의 편집을 저장하고 객체를 재정렬한다 (obj_id 구멍 압축)  [Ctrl+S]")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        _top.addWidget(self._save_btn)

        # 편집은 전부 메모리라, **취소 = 되돌리기 스택이 아니라 다시 읽기**다 (한 번에 마지막 저장 시점으로).
        self._revert_btn = QPushButton("되돌리기")
        self._revert_btn.setToolTip("저장 안 한 편집을 버리고 디스크에서 다시 읽는다  [Ctrl+R]")
        self._revert_btn.setEnabled(False)
        self._revert_btn.clicked.connect(self._on_revert)
        _top.addWidget(self._revert_btn)
        _top.addStretch(1)
        _lay.addLayout(_top)

        self._stem_list = Stem_list()
        self._stem_list.selected.connect(self._on_stem)
        self._stem_list.to_state_requested.connect(self.transition_requested)
        self._stem_list.delete_requested.connect(self.remove_requested)

        # 가운데 = params(dataset-wide) · 데이터(leaf) · 객체(objects). 같은 렌더러, 다른 scope.
        self._params = Params_panel(self._meta, get_size=lambda: self._data.canvas_size())
        self._params.tree.selected.connect(self._on_params_select)   # 선택 = 읽기전용 미리보기 (전역이라)
        self._params.tree.layers_changed.connect(self._redraw)
        self._params.edit_requested.connect(self._on_params_edit)    # [수정] = 조준·편집
        self._params.changed.connect(self._on_params_changed)

        self._leaf_panel = Node_panel("leaves", self._meta, lambda: self._key)
        self._leaf_tree = self._leaf_panel.tree
        self._leaf_tree.selected.connect(self._on_node)
        self._leaf_tree.layers_changed.connect(self._redraw)
        self._leaf_panel.changed.connect(self._on_nodes_changed)

        # 객체 삭제·병합은 store 라이프사이클이다 — 컨테이너 pop·mask 합집합을 store 가 든다(라벨맵 조작 없음).
        self._obj_panel = Node_panel("objects", self._meta, lambda: self._key)
        self._obj_tree = self._obj_panel.tree
        self._obj_tree.selected.connect(self._on_node)
        self._obj_tree.layers_changed.connect(self._redraw)
        self._obj_panel.changed.connect(self._on_nodes_changed)
        self._obj_panel.raster_edited.connect(self._on_raster_edited)

        _mid = QSplitter(Qt.Orientation.Vertical)
        _mid.addWidget(Collapsible("params  (dataset-wide)", self._params, expanded=False))
        _mid.addWidget(Collapsible("데이터  (선택 stem)", self._leaf_panel))
        _mid.addWidget(Collapsible("객체  (선택 stem)", self._obj_panel))
        _mid.setStretchFactor(1, 1)
        _mid.setStretchFactor(2, 1)
        _mid.setSizes([28, 300, 300])

        self._data = Data_view()
        self._data.edited.connect(self._on_edited)
        self._data.raster_edited.connect(self._on_raster_edited)
        self._data.object_picked.connect(self._obj_tree.select_node)   # 캔버스 클릭 → 트리 선택 (Shift=더하기)

        _split = QSplitter(Qt.Orientation.Horizontal)
        _split.addWidget(self._stem_list)
        _split.addWidget(_mid)
        _split.addWidget(self._data)
        _split.setStretchFactor(2, 1)
        _split.setSizes([240, 320, 700])
        _lay.addWidget(_split, stretch=1)
        self._install_shortcuts()
        QApplication.instance().installEventFilter(self)   # Tab = stem 목록 ↔ 편집기 왕복 (아래 eventFilter)

    def _install_shortcuts(self) -> None:
        """**store 를 아는 단축키는 여기 산다** — 편집기가 아니라.

        도구·이력 단축키(`V/R/D/E`·`B/P/C/F`·`Ctrl+Z/Y`·`[`·`]`)는 편집기가 자기 도구 선언에서 만든다.
        여기 있는 것들은 저장·객체 추가/삭제라 store 를 불러야 하고, 그걸 편집기에 들려주면 편집기가
        다시 store 에 묶여 재사용이 안 된다(옛 `Stem_editor` 가 그랬다).

        * ``0``–``9``  : 그 순번 객체 선택 (라벨링 중 손이 트리로 안 가게)
        * ``A``        : 객체 추가 · ``Delete`` : 선택 노드 삭제 · ``M`` : 고른 객체 병합
        * ``Ctrl+S``   : 저장 (+ 객체 재정렬) · ``Ctrl+R`` : 저장 안 한 편집 버리고 다시 읽기
        """
        def _bind(seq: str, slot) -> None:
            _sc = QShortcut(QKeySequence(seq), self)
            _sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            _sc.activated.connect(slot)

        for _i in range(10):
            _bind(str(_i), lambda i=_i: self._obj_tree.select_index(i))
        _bind("A", self._obj_panel.add_object)
        _bind("Delete", self._obj_panel.delete_selected)
        _bind("M", self._obj_panel.merge_selected)
        _bind("Ctrl+S", self._on_save)
        _bind("Ctrl+R", self._on_revert)

    def eventFilter(self, obj, event) -> bool:
        """Tab / Shift+Tab — 이 뷰 안에선 stem 목록 ↔ 이미지 편집기 사이만 포커스를 왕복한다.

        앱 전역 필터지만 **이 뷰에 포커스가 있을 때만** 가로챈다(다른 창·트리로 안 샌다). 폼 필드
        (스핀박스·입력·콤보)에선 Tab 이 필드 이동으로 남게 예외를 둔다(bbox 4칸 이동 보존).
        """
        if (event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)):
            _fw = QApplication.focusWidget()
            if (_fw is not None and (_fw is self or self.isAncestorOf(_fw))
                    and not isinstance(_fw, (QLineEdit, QAbstractSpinBox, QComboBox))):
                self._toggle_focus()
                return True
        return super().eventFilter(obj, event)

    def _toggle_focus(self) -> None:
        """포커스를 stem 목록 ↔ 이미지 편집기 사이에서 왕복한다 (라벨링 동선 — 트리로 안 샌다)."""
        if self._stem_list.list_has_focus():
            self._data.focus_editor()
        else:
            self._stem_list.focus_list()

    # ── Public API ────────────────────────────────────────────────────────────
    def set_pipeline(self, pipeline) -> None:
        """구동 ``Pipeline`` 을 갈아끼우고 본문을 갱신한다."""
        self._pipeline = pipeline
        self._key = ""
        self.refresh()

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 — 잠그면 보기(목록 클릭·체크·줌)는 유지하고 값 수정만 막는다.

        상위(``Main_page``)가 백그라운드 워커(전이·Convert·Run) 실행 중 호출한다. 데이터가 워커에서
        변형되는 동안 편집이 끼어들지 못하게 막되, 계속 보고 검토할 수 있게 한다.
        """
        self._editable = editable
        self._stem_list.set_editable(editable)
        self._params.set_editable(editable)
        self._leaf_panel.set_editable(editable)
        self._obj_panel.set_editable(editable)
        self._data.set_editable(editable)
        self._save_btn.setEnabled(editable and self._dirty)
        self._revert_btn.setEnabled(editable and self._dirty)

    def refresh(self, keep: str | None = None) -> None:
        """현재 ``pipeline.meta`` 로 목록을 다시 채운다 (선택은 트리·뷰어를 따라 갱신된다)."""
        _meta = self._meta()
        if _meta is None:
            self.clear()
            return
        self._reset_dirty()                             # 디스크 상태로 다시 그리므로 대기 편집은 없다
        self._params.load(_meta)                        # dataset-wide — stem 과 무관하게 유지
        self._stem_list.load(_meta, keep=keep if keep is not None else self._key)

    def clear(self) -> None:
        """본문을 비운다."""
        self._reset_dirty()
        self._stem_list.clear()
        self._params.clear()
        self._leaf_panel.clear()
        self._obj_panel.clear()
        self._data.show_layers([])
        self._data.show_node(None)

    # ── 내부 ──────────────────────────────────────────────────────────────────
    def _meta(self):
        return self._pipeline.meta if self._pipeline is not None else None

    def _classes(self) -> list[str]:
        """class 후보 (정본 id_map) — **어느 노드에 줄지는 여기가 정한다**(뷰어는 도메인을 모른다)."""
        return sorted(self._pipeline.Id_map()) if self._pipeline is not None else []

    def _on_stem(self, key: str) -> None:
        """목록 선택 → 그 stem 의 서브트리를 데이터·객체 트리에 펼치고 캔버스를 다시 그린다.

        이전 stem 에 저장 안 된 편집이 있으면 **넘어가기 전에 저장(+정렬)** 한다 — 대기 라스터는
        node.value 에만 있어 트리를 다시 로드하면 사라지기 때문이다.
        """
        if self._dirty and self._key and self._key != key:
            self._flush()                               # 넘어가기 전에 편집 영속 (대기 라스터는 메모리에만)
        self._key = key
        self._show_stem(key)

    def _show_stem(self, key: str) -> None:
        """선택된 stem 의 데이터·객체 패널을 펼치고 캔버스를 다시 그린다 — **stem 목록은 안 건드린다**.

        저장·stem 전환처럼 목록 구성(이름·상태·개수)은 그대로고 **한 stem 의 내용만** 바뀔 때 쓴다.
        6.5만 개짜리 목록을 통째 재구축하는 ``refresh`` 와 달리 비용이 O(이 stem 의 객체 수)다.
        """
        _meta = self._meta()
        if not key or _meta is None:
            self._leaf_panel.clear()
            self._obj_panel.clear()
            self._data.show_layers([])
            self._data.show_node(None)
            return
        self._leaf_panel.load(_meta, key)
        self._obj_panel.load(_meta, key)
        self._redraw()
        self._data.show_node(None)              # 새 stem — 아직 고른 노드 없음(조준도 해제)

    def _on_node(self, node: Node | None) -> None:
        """노드 선택 → 그 값의 편집 패널. ``class_id`` 에만 id_map 후보를 넘긴다."""
        _cands = self._classes() if (node is not None and node.name == "class_id") else None
        self._data.show_node(node, candidates=_cands)

    def _on_params_select(self, node: Node | None) -> None:
        """params 선택 → **읽기전용 미리보기**(조준·편집 안 함). 편집은 [수정]에서만 — 전역 값이라."""
        self._data.show_node(node, aim=False, editable=False)

    def _on_params_edit(self, node: Node) -> None:
        """params [수정] → 그 값을 편집한다. raster(roi)는 캔버스에 띄우고 편집기를 조준한다(원본 위에)."""
        if node is None:
            return
        self._params.tree.check_node(node)              # 편집하려면 보여야 한다 (전역 raster 는 기본 off)
        _cands = self._classes() if node.name == "class_id" else None
        self._data.show_node(node, candidates=_cands, aim=True, editable=True)

    def _redraw(self) -> None:
        """체크가 바뀌면 캔버스를 다시 합성한다 — **params 의 raster 도 함께 겹친다**.

        `roi` 같은 dataset-wide 이미지는 어느 stem 위에든 겹쳐 보는 게 자연스럽다. params 를 먼저
        쌓아 stem 의 것이 그 위에 오게 한다. 객체(bbox)는 raster 가 아니라 attr 이라 객체 트리가 준다.
        """
        self._data.set_objects(self._obj_tree.top_nodes())
        self._data.show_layers(self._params.tree.checked_layers()
                               + self._leaf_tree.checked_layers())

    def _on_nodes_changed(self) -> None:
        """노드가 추가/삭제됨 — 캔버스를 다시 합성하고 **저장 대기**로 표시한다.

        객체 추가·삭제·병합은 메모리에서만 일어난다(payload-free) — 그래서 값 편집과 똑같이 저장을
        기다린다. 데이터 leaf 추가·삭제는 파일을 이미 건드렸지만, 트리에 생긴/사라진 서술자는 사이드카에
        적혀야 하므로 여기서도 dirty 다.
        """
        self._mark_dirty(None)
        self._redraw()
        self.meta_changed.emit()

    def _on_params_changed(self) -> None:
        """params 가 추가/삭제됨 — 캔버스를 다시 합성하고 상위에 알린다."""
        self._redraw()
        self.meta_changed.emit()

    def _on_raster_edited(self, node: Node, raster) -> None:
        """캔버스 편집 확정 — **디스크엔 안 쓰고 대기**시킨다(명시적 저장 때 flush).

        편집된 픽셀은 ``node.value`` 에 있고 캔버스는 그걸로 그려진다 — 파일 write(``Route``)는 저장
        때 한 번에 한다(``_flush``). 라스터 노드를 대기 목록에 담고 dirty 표시만 한다.
        """
        if not self._editable:
            return
        if not any(_n is node for _n in self._pending_rasters):
            self._pending_rasters.append(node)
        self._mark_dirty(node)

    def _on_edited(self, node: Node) -> None:
        """인라인 값이 편집됨 — in-memory 서술자는 이미 갱신됨. **저장은 명시적 저장까지 미룬다**."""
        if not self._editable:
            return
        self._mark_dirty(node)

    # ── 명시적 저장 (auto-save 대신) — 저장 = flush (사이드카 write) ─────────────────
    def _on_save(self) -> None:
        """이 stem 의 편집을 flush 한다 (대기 라스터 Route + 사이드카 Save).

        객체 재정렬·유령 제거는 여기서 안 한다 — obj_id 는 라벨맵 픽셀값이 아니라 트리 key 라 연속일
        필요가 없고(구멍 압축 불필요), mask 무게중심 정렬은 ``order_objects`` process(flow)의 몫이다.
        저장은 편집을 디스크에 영속할 뿐이다.
        """
        if self._pipeline is None or not self._editable or not self._dirty:
            return
        _key = self._key
        self._flush()                                   # 대기 라스터 Route + 사이드카 Save
        self._show_stem(_key)                           # 현재 stem 만 다시 그린다 (65k 목록 재구축 없음)
        self.meta_changed.emit()

    def _on_revert(self) -> None:
        """저장 안 한 편집을 **버리고 디스크에서 다시 읽는다** — 편집의 취소는 되돌리기가 아니다.

        붓질·상자·객체 추가/삭제/병합이 전부 메모리에 쌓이므로, 마지막 저장 시점으로 한 번에 돌아가는
        길이 있으면 개별 undo 를 겹겹이 쌓을 필요가 없다(그게 사용자가 실제로 원하는 "취소"다).
        """
        if self._pipeline is None or not self._editable or not self._dirty:
            return
        if QMessageBox.question(
                self, "되돌리기",
                "저장하지 않은 편집을 모두 버리고 디스크에서 다시 읽습니다. 계속할까요?") \
                != QMessageBox.StandardButton.Yes:
            return
        _key = self._key
        self._pipeline.Reload()                         # 정본을 디스크 기준으로 다시 (메모리 편집 폐기)
        self._reset_dirty()
        self.refresh(keep=_key)
        self.meta_changed.emit()

    def _flush(self) -> None:
        """대기 라스터를 store 에 Route 하고 사이드카를 저장한다 (경로는 트리 위치가 정한다)."""
        _meta = self._meta()
        if _meta is None:
            return
        for _node in self._pending_rasters:
            _spec = {"to": "storage", "type": _node.ref.format[0]}
            if len(_node.ref.format) > 1 and _node.ref.format[1]:
                _spec["format"] = _node.ref.format[1]
            _new = _meta.Route(_node.path, _node.name, _spec, _node.value)
            _parent = _meta.tree.At(_node.path)
            if _parent is not None:
                _parent.Push(_node.name, _new)
            _node.ref = _new
        if self._dirty_params:
            _meta.Save()                                # params 포함 전체
        elif self._key:
            _meta.Save(self._key)                       # 그 stem 사이드카만 (증분)
        else:
            _meta.Save()
        self._reset_dirty()

    def _mark_dirty(self, node: Node | None) -> None:
        """저장 대기 표시 — params 노드면 전체 저장이 필요하다고 함께 기록한다."""
        self._dirty = True
        _meta = self._meta()
        if _meta is not None and node is not None and node.path and node.path[0] == _meta.PARAMS:
            self._dirty_params = True
        self._save_btn.setEnabled(self._editable)
        self._revert_btn.setEnabled(self._editable)      # 취소 = 다시 읽기 (같은 dirty 를 탄다)

    def _reset_dirty(self) -> None:
        self._dirty = False
        self._dirty_params = False
        self._pending_rasters = []
        self._save_btn.setEnabled(False)
        self._revert_btn.setEnabled(False)
