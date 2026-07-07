"""class_id (id_map) 트리 패널 — class 이름 추가/삭제 가능."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QPushButton,
    QTreeWidgetItem,
    QVBoxLayout,
)

from gui.widgets import make_tree, set_bold


class Idmap_panel(QGroupBox):
    """``id_map`` 트리 — 넘겨받은 dict 를 직접 수정하고 ``changed`` emit (저장은 상위)."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("class_id", parent)
        self._id_map: dict[str, dict[str, int]] = {}
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(4, 4, 4, 4)

        _btns = QHBoxLayout()
        _add = QPushButton("+ class")
        _add.clicked.connect(self._on_add)
        _del = QPushButton("− class")
        _del.clicked.connect(self._on_del)
        _btns.addWidget(_add)
        _btns.addWidget(_del)
        _btns.addStretch()
        _lay.addLayout(_btns)

        self._tree = make_tree(
            headers=["class", "scope", "id"],
            resize=[QHeaderView.Stretch, QHeaderView.ResizeToContents,
                    QHeaderView.ResizeToContents],
            alternating=True)
        _lay.addWidget(self._tree)

    # ── public ──────────────────────────────────────────────────────────────

    def load(self, id_map: dict[str, dict[str, int]]) -> None:
        """``id_map`` 참조를 보관하고 트리를 갱신한다."""
        self._id_map = id_map
        self._refresh()

    def clear(self) -> None:
        """패널을 비운다."""
        self._id_map = {}
        self._tree.clear()
        self.setTitle("class_id")

    # ── 내부 ────────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        self._tree.clear()
        for _cls, _scopes in sorted(self._id_map.items()):
            _cls_item = QTreeWidgetItem([_cls, "", ""])
            set_bold(_cls_item)
            for _scope, _id in sorted(_scopes.items(), key=lambda x: x[1]):
                _cls_item.addChild(QTreeWidgetItem(["", _scope, str(_id)]))
            _cls_item.setExpanded(True)
            self._tree.addTopLevelItem(_cls_item)
        self.setTitle(f"class_id  ({len(self._id_map)} classes)")

    def _on_add(self) -> None:
        _name, _ok = QInputDialog.getText(self, "class 추가", "class 이름:")
        _name = _name.strip()
        if not (_ok and _name) or _name in self._id_map:
            return
        self._id_map[_name] = {}
        self._refresh()
        self.changed.emit()

    def _on_del(self) -> None:
        _item = self._tree.currentItem()
        if _item is None:
            return
        # 최상위 class 노드로 올라간다 (scope 노드를 선택했을 수도 있으므로).
        while _item.parent() is not None:
            _item = _item.parent()
        _cls = _item.text(0)
        if _cls in self._id_map:
            del self._id_map[_cls]
            self._refresh()
            self.changed.emit()
