"""노드 트리 — 선택한 item 의 ``Data_Ref`` 서브트리를 **한 트리로** 보여준다.

예전엔 같은 재귀 타입을 셋으로 쪼개 각각 다른 위젯이 그렸다 — frame leaf(편집기의 데이터 트리) ·
객체(주석 패널) · params(별도 패널). 그런데 core 에서 그 셋은 **다른 종류가 아니라 트리의 다른 위치**다.
여기서 하나로 합친다.

**체크박스가 표시 여부다** — raster 뷰어가 있는 LEAF(image·segmap·rle)에만 붙고, 체크된 것들이 캔버스에
합성된다. 무엇을 그릴지는 뷰어 레지스트리가 알고([`gui/viewer`](../../viewer)), 트리는 묻기만 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QItemSelectionModel, Qt, Signal
from PySide6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem

from core.schema import Data_Ref
from gui.viewer import Viewer_for

_ROLE = Qt.ItemDataRole.UserRole


def _uncheckable(item: QTreeWidgetItem) -> None:
    """체크박스를 뗀다 — Qt 의 기본 플래그에 ``ItemIsUserCheckable`` 이 들어 있어 명시적으로 지운다.

    안 지우면 "그릴 수 없는 노드"에도 checkable 플래그가 남아, 나중에 체크 상태를 묻는 코드가
    조용히 틀린 답을 얻는다.
    """
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)


@dataclass
class Node:
    """트리의 한 노드 — 값을 어디서 읽었는지(주소)와 무엇인지(서술자)를 함께 든다.

    ``path`` 는 store 에 넘길 트리 key 경로다 — 뷰어는 경로를 모르므로(값만 본다) 여기가 기억한다.
    """

    path:   tuple[str, ...]          # 이 노드가 사는 **컨테이너**의 경로 (범주, stem, [obj_id])
    name:   str                      # info 안에서의 key
    ref:    Data_Ref
    value:  Any = None               # LEAF 면 디코드된 payload (BRANCH 면 None)

    @property
    def is_leaf(self) -> bool:
        return not self.ref.Is_branch()


class Node_tree(QTreeWidget):
    """``Data_Ref`` 서브트리 = 체크박스 트리. 체크 = 캔버스에 그린다.

    Attributes:
        selected: 선택 노드가 바뀜 ``(Node | None)`` — 오른쪽 패널이 그 값을 편집한다.
        layers_changed: 체크가 바뀜 — 캔버스가 다시 합성한다.
    """

    selected       = Signal(object)
    layers_changed = Signal()

    def __init__(self, scope: str = "all", parent=None) -> None:
        """``scope`` = 루트의 직속 자식 중 무엇을 보일지: ``all`` / ``leaves``(데이터) / ``objects``.

        같은 재귀 렌더러를 역할별로 나눠 쓰기 위한 필터다 — 루트 직속에만 걸리고, 객체 안쪽은 언제나
        전부 보인다(그 attr 을 편집해야 하므로). 데이터모델은 하나(재귀 ``Data_Ref``)지만 **표현은
        축(데이터 vs 객체)이 다르다.**
        """
        super().__init__(parent)
        self._scope = scope
        self.setHeaderLabels(["노드", "값"])
        self.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setAlternatingRowColors(True)
        if scope == "objects":                       # 여럿을 골라 **병합**한다 (데이터는 하나씩 다룬다)
            self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._editable = True
        self.currentItemChanged.connect(self._on_current)
        self.itemChanged.connect(self._on_check)

    # ── 채우기 ────────────────────────────────────────────────────────────────
    def load(self, store, key: str) -> None:
        """``key`` item(또는 ``params``)의 서브트리를 채운다 — 값은 store 에 **요청**해서 받는다.

        ``params`` 는 범주가 아니라 트리의 예약 최상위 key 라 경로가 ``(params,)`` 한 칸이다.
        """
        self.blockSignals(True)
        self.clear()
        if key == store.PARAMS:
            _path, _node = (store.PARAMS,), store.tree.Get(store.PARAMS)
        else:
            _path, _node = store.Item_path(key), store.Find(key)
        if _node is not None and _path is not None:
            self._add_children(self.invisibleRootItem(), store, _path, _node,
                               scope=self._scope)
        self.blockSignals(False)
        self.expandAll()

    def _add_children(self, parent: QTreeWidgetItem, store,
                      path: tuple[str, ...], node: Data_Ref,
                      scope: str = "all") -> None:
        """한 컨테이너의 자식들을 붙인다 — LEAF 는 값까지 풀고, BRANCH 는 파고든다.

        ``scope`` 는 **이 호출의 직속 자식에만** 걸린다(재귀는 언제나 전부) — 루트에서 데이터/객체 축을
        가르되 객체 안쪽 attr 은 다 보이게.
        """
        _values = store.Resolve(path, node)          # 직속 LEAF 만 (BRANCH 는 안 판다)
        for _name, _ref in node.Items():
            _is_branch = _ref.Is_branch()
            if (scope == "leaves" and _is_branch) or (scope == "objects" and not _is_branch):
                continue
            if _is_branch:                           # 객체 등 — 재귀
                _item = QTreeWidgetItem(parent, [_name, f"({len(_ref.info)})"])
                _item.setData(0, _ROLE, Node(path, _name, _ref))
                _uncheckable(_item)
                self._add_children(_item, store, path + (_name,), _ref)
                continue

            _val = _values.get(_name)
            _viewer = Viewer_for(_ref)
            _summary = _viewer.summary(_val, _ref) if _viewer else "?"
            _item = QTreeWidgetItem(parent, [_name, _summary])
            _item.setData(0, _ROLE, Node(path, _name, _ref, _val))
            if _viewer is not None and _viewer.RASTER:     # 그릴 수 있는 것만 체크박스
                _item.setCheckState(0, Qt.CheckState.Checked)
            else:
                _uncheckable(_item)                        # Qt 기본 플래그를 떼야 정직하다

    # ── 질의 ──────────────────────────────────────────────────────────────────
    def checked_layers(self) -> list[Node]:
        """체크된 raster 노드들 (트리 순서 = 합성 순서)."""
        _out: list[Node] = []

        def _walk(item: QTreeWidgetItem) -> None:
            for _i in range(item.childCount()):
                _c = item.child(_i)
                _n = _c.data(0, _ROLE)
                if (_n is not None and _n.is_leaf
                        and _c.flags() & Qt.ItemFlag.ItemIsUserCheckable
                        and _c.checkState(0) == Qt.CheckState.Checked):
                    _out.append(_n)
                _walk(_c)

        _walk(self.invisibleRootItem())
        return _out

    def current_node(self) -> Node | None:
        """현재 선택된 노드 (없으면 None) — 다중선택이어도 **조준은 current 하나**다."""
        _it = self.currentItem()
        return _it.data(0, _ROLE) if _it is not None else None

    def selected_nodes(self) -> list[Node]:
        """선택된 노드들 (``objects`` scope 에서만 여럿일 수 있다 — 병합의 단위)."""
        _out = [_it.data(0, _ROLE) for _it in self.selectedItems()]
        return [_n for _n in _out if _n is not None]

    def top_nodes(self) -> list[Node]:
        """루트 직속 노드들 — ``objects`` scope 에선 곧 객체 목록이다 (bbox·조준의 단위)."""
        _root = self.invisibleRootItem()
        _out: list[Node] = []
        for _i in range(_root.childCount()):
            _n = _root.child(_i).data(0, _ROLE)
            if _n is not None:
                _out.append(_n)
        return _out

    def select_node(self, node: Node, additive: bool = False) -> bool:
        """그 노드의 항목을 선택한다 (캔버스에서 고른 객체를 트리에 반영). 찾으면 True.

        ``additive`` 면 기존 선택을 지우지 않고 **토글**한다 — 안 골랐으면 더하고, **이미 골랐으면 뺀다**.
        캔버스에서 Shift+클릭으로 병합할 것들을 모으는 길이라, 잘못 집은 것을 빼려고 처음부터 다시
        고르게 하면 안 된다. 뺄 때 조준(current)은 남은 선택 중 하나로 옮긴다 — 방금 뺀 것을 계속
        겨누고 있으면 그게 아직 선택된 줄 안다.
        """
        _root = self.invisibleRootItem()
        for _i in range(_root.childCount()):
            _item = _root.child(_i)
            if _item.data(0, _ROLE) is not node:
                continue
            if not additive:
                self.setCurrentItem(_item)
            elif _item.isSelected():
                _item.setSelected(False)                        # 이미 고른 것 → 선택에서 뺀다
                _rest = self.selectedItems()
                if _rest:
                    self.setCurrentItem(_rest[-1], 0,
                                        QItemSelectionModel.SelectionFlag.NoUpdate)
            else:
                self.setCurrentItem(_item, 0, QItemSelectionModel.SelectionFlag.Select)
            return True
        return False

    def select_index(self, idx: int) -> bool:
        """루트 직속 ``idx`` 번째 항목을 선택한다 (숫자키 단축키 — 객체 트리에서 쓴다). 있으면 True."""
        _root = self.invisibleRootItem()
        if not 0 <= idx < _root.childCount():
            return False
        self.setCurrentItem(_root.child(idx))
        return True

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 — 체크(표시 토글)는 보기라 막지 않는다."""
        self._editable = editable

    # ── 신호 ──────────────────────────────────────────────────────────────────
    def _on_current(self, *_a) -> None:
        self.selected.emit(self.current_node())

    def _on_check(self, *_a) -> None:
        self.layers_changed.emit()
