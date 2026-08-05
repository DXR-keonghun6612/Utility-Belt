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
    activated      = Signal(object)           # 더블클릭 ``(Node)`` — "이걸 열어라" (무엇이 열리나는 상위가)
    layers_changed = Signal()
    reordered      = Signal(object, object)   # (컨테이너 path, 새 자식 순서) — 적용은 store 가 한다

    def __init__(self, scope: str = "all", check_default: bool = True, parent=None) -> None:
        """``scope`` = 루트의 직속 자식 중 무엇을 보일지: ``all`` / ``leaves``(데이터) / ``objects``.

        같은 재귀 렌더러를 역할별로 나눠 쓰기 위한 필터다 — 루트 직속에만 걸리고, 객체 안쪽은 언제나
        전부 보인다(그 attr 을 편집해야 하므로). 데이터모델은 하나(재귀 ``Data_Ref``)지만 **표현은
        축(데이터 vs 객체)이 다르다.**

        Args:
            check_default: 첫 로드 시 raster 를 켤지 — 데이터는 켜고(True), params 는 끈다(전역이라
                stem 마다 캔버스를 채우면 방해). 사용자가 한 번 토글하면 그 선택(``_checked``)이 이겨서
                **stem 을 넘어가도 유지**된다(편집기가 앱 싱글턴이라 매번 리셋되면 귀찮다).
        """
        super().__init__(parent)
        self._scope = scope
        self._check_default = check_default
        self._checked: set[str] | None = None   # 사용자가 정한 표시 선택 (None = 아직 없음 → 기본값)
        self.setHeaderLabels(["노드", "값"])
        self.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setAlternatingRowColors(True)
        if scope == "objects":                       # 여럿을 골라 **병합**한다 (데이터는 하나씩 다룬다)
            self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._editable = True
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)   # 순서 바꾸기 (같은 부모 안에서만)
        self.setDropIndicatorShown(True)
        self.currentItemChanged.connect(self._on_current)
        self.itemChanged.connect(self._on_check)
        self.itemDoubleClicked.connect(self._on_activate)

    # ── 순서 바꾸기 (드래그앤드롭) ─────────────────────────────────────────────
    def dropEvent(self, event) -> None:
        """**같은 부모 안에서 항목 사이로** 떨어뜨린 것만 받는다 — 순서 변경이지 이동이 아니다.

        컨테이너 **위**에 떨어뜨리면 소속이 바뀌는데(객체를 다른 객체 안으로), 그건 순서가 아니라 다른
        연산이라 거절한다. 부모가 다른 항목을 섞어 끌어도 마찬가지.

        Qt 가 항목을 직접 옮기게 두지 않는다(``super()`` 를 안 부른다) — 진실은 store 에 있고, 트리는
        store 가 바꾼 뒤 다시 읽는다. 그래야 정수 key 재부여처럼 **이름까지 달라지는** 결과가 그대로 뜬다.
        """
        _pos = self.dropIndicatorPosition()
        _between = (QTreeWidget.DropIndicatorPosition.AboveItem,
                    QTreeWidget.DropIndicatorPosition.BelowItem,
                    QTreeWidget.DropIndicatorPosition.OnViewport)
        _items = [_it for _it in self.selectedItems() if _it.data(0, _ROLE) is not None]
        _target = self.itemAt(event.position().toPoint())
        _dest = _target.parent() if _target is not None else None
        if (not self._editable or not _items or _pos not in _between
                or any(_it.parent() is not _dest for _it in _items)):
            event.ignore()
            return
        _order = self._order_after(_items, _dest, _target,
                                   _pos == QTreeWidget.DropIndicatorPosition.BelowItem)
        event.accept()
        self.reordered.emit(_items[0].data(0, _ROLE).path, _order)

    def _order_after(self, items, dest, target, below: bool) -> list[str]:
        """끌어놓은 뒤의 자식 key 순서 — 끌린 것들을 빼고 목표 자리에 통째로 끼운다."""
        _parent = dest if dest is not None else self.invisibleRootItem()
        _names = [_parent.child(_i).data(0, _ROLE).name for _i in range(_parent.childCount())
                  if _parent.child(_i).data(0, _ROLE) is not None]
        _moving = [_it.data(0, _ROLE).name for _it in items]
        _rest = [_n for _n in _names if _n not in _moving]
        if target is None:                                   # 빈 곳 → 맨 뒤
            return _rest + _moving
        _at = _names.index(target.data(0, _ROLE).name) + (1 if below else 0)
        _at -= sum(1 for _n in _moving if _names.index(_n) < _at)   # 앞에서 빠진 만큼 당긴다
        return _rest[:_at] + _moving + _rest[_at:]

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
                _on = (_name in self._checked if self._checked is not None
                       else self._check_default)           # 유지된 선택 우선, 없으면 기본값
                _item.setCheckState(0, Qt.CheckState.Checked if _on
                                    else Qt.CheckState.Unchecked)
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

    def check_node(self, node: Node) -> bool:
        """그 노드의 raster 를 표시(체크)한다 — 편집하려고 조준할 때 화면에 뜨게. 체크했으면 True.

        params [수정]에서 쓴다: 전역 raster 는 기본 꺼져 있으니, 편집을 시작하면 캔버스에 띄운다.
        """
        def _walk(item: QTreeWidgetItem) -> bool:
            for _i in range(item.childCount()):
                _c = item.child(_i)
                if (_c.data(0, _ROLE) is node
                        and _c.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    _c.setCheckState(0, Qt.CheckState.Checked)
                    return True
                if _walk(_c):
                    return True
            return False

        return _walk(self.invisibleRootItem())

    def select_index(self, idx: int) -> bool:
        """루트 직속 ``idx`` 번째 항목을 선택한다 (숫자키 단축키 — 객체 트리에서 쓴다). 있으면 True."""
        _root = self.invisibleRootItem()
        if not 0 <= idx < _root.childCount():
            return False
        self.setCurrentItem(_root.child(idx))
        return True

    def select_name(self, name: str) -> bool:
        """루트 직속에서 그 이름의 항목을 선택한다 — 병합 생존자(가장 작은 obj_id)로 조준을 옮긴다.

        노드는 ``load`` 로 새로 만들어져 정체성이 바뀌므로(``select_node`` 는 못 씀), 이름으로 찾는다.
        선택하면 조준이 그리로 따라가 인스펙터가 생존자의 class 를 보인다. 있으면 True.
        """
        _root = self.invisibleRootItem()
        for _i in range(_root.childCount()):
            _item = _root.child(_i)
            _n = _item.data(0, _ROLE)
            if _n is not None and _n.name == name:
                self.setCurrentItem(_item)
                return True
        return False

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 — 체크(표시 토글)는 보기라 막지 않는다."""
        self._editable = editable

    # ── 신호 ──────────────────────────────────────────────────────────────────
    def _on_current(self, *_a) -> None:
        self.selected.emit(self.current_node())

    def _on_check(self, *_a) -> None:
        self._checked = {_n.name for _n in self.checked_layers()}   # stem 넘어가도 유지할 선택
        self.layers_changed.emit()

    def _on_activate(self, item, _col: int = 0) -> None:
        """더블클릭 — **여는 것**은 트리가 정하지 않는다. 노드만 실어 올리고 상위가 무엇을 열지 고른다."""
        _node = item.data(0, _ROLE) if item is not None else None
        if _node is not None:
            self.activated.emit(_node)
