"""class 트리 (드래그&드롭 재지정) — Editor 좌측.

class = 부모 노드, 샘플(stem) = leaf. leaf 를 다른 class 노드로 드롭하면 재지정,
🚫 제외됨 노드로 드롭하면 제외. 컨텍스트 메뉴로도 제외/복원/이동한다. 모델을 직접
갱신하고 changed 로 알린다(우측 그리드 동기화는 panel 담당).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
)

from gui.editor._model import EXCLUDED, Editor_model


_EXCLUDED_LABEL = "🚫 제외됨"
_C_CLASS    = QColor("#7fb8e8")
_C_EXCLUDED = QColor("#888888")


class Category_tree(QTreeWidget):
    """class/샘플 2단 트리 (드래그&드롭 + 컨텍스트 메뉴 재지정)."""

    changed           = Signal()          # 모델 변경됨
    category_selected = Signal(object)    # 선택된 class key (또는 EXCLUDED)

    def __init__(self, model: Editor_model, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self.setHeaderHidden(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_menu)
        self.currentItemChanged.connect(self._on_current)

    # ── 구성 ──────────────────────────────────────────────────────────────────

    def rebuild(self) -> None:
        self.blockSignals(True)
        self.clear()

        _parents: dict[str, QTreeWidgetItem] = {}
        for _cls in self._model.classes():
            _parents[_cls] = self._make_parent(_cls, _cls)
            self.addTopLevelItem(_parents[_cls])
        _exc = self._make_parent(_EXCLUDED_LABEL, EXCLUDED)
        self.addTopLevelItem(_exc)
        _parents[EXCLUDED] = _exc

        for _e in self._model.entries:
            _key = EXCLUDED if _e["excluded"] else _e["cls"]
            _parent = _parents.get(_key)
            if _parent is None:
                _parent = self._make_parent(_key, _key)
                self.insertTopLevelItem(self.topLevelItemCount() - 1, _parent)
                _parents[_key] = _parent
            _leaf = QTreeWidgetItem([Path(_e["rel"]).stem])
            _leaf.setData(0, Qt.ItemDataRole.UserRole, _e["rel"])
            _leaf.setFlags(
                (_leaf.flags() | Qt.ItemFlag.ItemIsDragEnabled)
                & ~Qt.ItemFlag.ItemIsDropEnabled
            )
            _parent.addChild(_leaf)

        for _i in range(self.topLevelItemCount()):
            _p = self.topLevelItem(_i)
            _key = _p.data(0, Qt.ItemDataRole.UserRole)
            _base = _EXCLUDED_LABEL if _key == EXCLUDED else _key
            _p.setText(0, f"{_base}  ({_p.childCount()})")
        self.expandAll()
        self.blockSignals(False)

    def _make_parent(self, label: str, key: str) -> QTreeWidgetItem:
        _item = QTreeWidgetItem([label])
        _item.setData(0, Qt.ItemDataRole.UserRole, key)
        _item.setFlags(
            (_item.flags() | Qt.ItemFlag.ItemIsDropEnabled)
            & ~Qt.ItemFlag.ItemIsDragEnabled
        )
        _font = _item.font(0)
        _font.setBold(True)
        _item.setFont(0, _font)
        _item.setForeground(0, _C_EXCLUDED if key == EXCLUDED else _C_CLASS)
        return _item

    # ── 선택 ──────────────────────────────────────────────────────────────────

    def _on_current(self, current: QTreeWidgetItem | None, _prev) -> None:
        if current is None:
            return
        _node = current if current.parent() is None else current.parent()
        self.category_selected.emit(_node.data(0, Qt.ItemDataRole.UserRole))

    def _selected_rels(self) -> set[str]:
        return {
            _it.data(0, Qt.ItemDataRole.UserRole)
            for _it in self.selectedItems() if _it.parent() is not None
        }

    # ── 드롭 / 메뉴 ───────────────────────────────────────────────────────────

    def dropEvent(self, event) -> None:  # noqa: N802
        _target = self.itemAt(event.position().toPoint())
        _rels = self._selected_rels()
        if _target is None or not _rels:
            event.ignore()
            return
        _node = _target if _target.parent() is None else _target.parent()
        self._apply(_rels, _node.data(0, Qt.ItemDataRole.UserRole))
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()

    def _on_menu(self, pos) -> None:
        _rels = self._selected_rels()
        if not _rels:
            return
        _menu = QMenu(self)
        _act_exc = _menu.addAction(f"제외 ({len(_rels)})")
        _act_res = _menu.addAction("복원")
        _sub = _menu.addMenu("class 로 이동")
        _moves = {_sub.addAction(_c): _c for _c in self._model.classes()}
        _chosen = _menu.exec(self.viewport().mapToGlobal(pos))
        if _chosen is _act_exc:
            self._apply(_rels, EXCLUDED)
        elif _chosen is _act_res:
            self._apply(_rels, None)
        elif _chosen in _moves:
            self._apply(_rels, _moves[_chosen])

    def _apply(self, rels: set[str], target_key) -> None:
        if target_key == EXCLUDED:
            self._model.exclude(rels)
        elif target_key is None:
            self._model.restore(rels)
        else:
            self._model.reassign(rels, target_key)
        self.rebuild()
        self.changed.emit()
