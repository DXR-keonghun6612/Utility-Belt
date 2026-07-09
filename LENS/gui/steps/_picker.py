"""Process 선택기 — 검색 가능한 분류 트리 팝업 + 현재 키 버튼(``QComboBox`` 호환 API)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from core.process import PROCESS_REGISTRY

PROCESS_KEYS = sorted(PROCESS_REGISTRY._module_dict)
# process 키 → 분류 경로("대분류/중분류"). 없으면 "기타". 트리 팝업이 경로를 쪼개 계층을 만든다.
PROCESS_CATALOG = {
    _k: (getattr(_c, "CATEGORY", "") or "기타")
    for _k, _c in PROCESS_REGISTRY._module_dict.items()
}


class _Process_popup(QFrame):
    """category 경로 트리 + 검색칸 팝업 — leaf(process) 선택 시 ``selected`` emit."""

    selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(4, 4, 4, 4)
        _lay.setSpacing(4)

        self._search = QLineEdit()
        self._search.setPlaceholderText("검색 (process · 분류)")
        self._search.setClearButtonEnabled(True)
        _lay.addWidget(self._search)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumSize(300, 360)
        _lay.addWidget(self._tree)

        self._search.textChanged.connect(self._populate)
        self._search.returnPressed.connect(self._pick_first)
        self._tree.itemClicked.connect(self._on_click)
        self._populate("")

    def _populate(self, text: str) -> None:
        """검색어로 트리를 다시 채운다 (분류 경로를 ``/`` 로 쪼개 계층 노드 생성)."""
        _text = text.strip().lower()
        self._tree.clear()
        _nodes: dict[tuple[str, ...], QTreeWidgetItem] = {}
        for _key in sorted(PROCESS_CATALOG):
            _cat = PROCESS_CATALOG[_key]
            if _text and _text not in _key.lower() and _text not in _cat.lower():
                continue
            _parent: QTreeWidgetItem | None = None
            _path: tuple[str, ...] = ()
            for _part in _cat.split("/"):
                _path += (_part,)
                _item = _nodes.get(_path)
                if _item is None:
                    _item = QTreeWidgetItem([_part])
                    _item.setFlags(Qt.ItemFlag.ItemIsEnabled)   # 분류 노드는 선택 불가
                    if _parent is None:
                        self._tree.addTopLevelItem(_item)
                    else:
                        _parent.addChild(_item)
                    _nodes[_path] = _item
                _parent = _item
            _leaf = QTreeWidgetItem([_key])
            _leaf.setData(0, Qt.ItemDataRole.UserRole, _key)
            if _parent is not None:
                _parent.addChild(_leaf)
        if _text:
            self._tree.expandAll()

    def _on_click(self, item: QTreeWidgetItem, _col: int) -> None:
        _key = item.data(0, Qt.ItemDataRole.UserRole)
        if _key:
            self.selected.emit(_key)
            self.close()

    def _pick_first(self) -> None:
        """엔터 — 트리의 첫 리프를 고른다 (검색 좁힌 뒤 빠른 확정용)."""
        _it = QTreeWidgetItemIterator(self._tree)
        while _it.value():
            _key = _it.value().data(0, Qt.ItemDataRole.UserRole)
            if _key:
                self.selected.emit(_key)
                self.close()
                return
            _it += 1


class _Process_picker(QWidget):
    """현재 process 키 버튼 — 누르면 검색 트리 팝업 (``currentText``/``setCurrentText`` 호환).

    Attributes:
        changed: 선택 키 변경 시 emit.
    """

    changed = Signal()

    def __init__(self, key: str = "", parent=None) -> None:
        super().__init__(parent)
        self._key = key
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        self._btn = QToolButton()
        self._btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn.setArrowType(Qt.ArrowType.NoArrow)
        self._btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn.setText(self._label(key))
        self._btn.setToolTip("클릭해 분류 트리에서 process 선택")
        self._btn.clicked.connect(self._open)
        _lay.addWidget(self._btn)

    @staticmethod
    def _label(key: str) -> str:
        if not key:
            return "(process 선택) ▾"
        _cat = PROCESS_CATALOG.get(key)
        return f"{key}   [{_cat}] ▾" if _cat else f"{key} ▾"

    def _open(self) -> None:
        _popup = _Process_popup(self)
        _popup.selected.connect(self._on_select)
        _popup.move(self._btn.mapToGlobal(self._btn.rect().bottomLeft()))
        _popup.show()
        _popup._search.setFocus()

    def _on_select(self, key: str) -> None:
        self.setCurrentText(key)

    # ── QComboBox 호환 API ──────────────────────────────────────────────────────

    def currentText(self) -> str:  # noqa: N802 — QComboBox API 관례 유지
        return self._key

    def setCurrentText(self, key: str) -> None:  # noqa: N802
        """현재 키를 설정한다. 값이 실제로 바뀔 때만 ``changed`` 를 emit한다."""
        self._btn.setText(self._label(key))
        if key != self._key:
            self._key = key
            self.changed.emit()
