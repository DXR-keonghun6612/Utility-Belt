"""dataloader 구성 패널 — 데이터 그룹(reader + sources + globs)들을 정의.

각 카드 하나가 dataloader config 하나(= 데이터 그룹 하나)에 대응한다. 출력으로
Build_reader 가 받는 meta dict 리스트를 제공한다.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.dataloader._base import FRAME_KEY, Dataloader_config
from core.dataloader import reader_registry


class Dataloader_card(QGroupBox):
    """단일 데이터 그룹(reader + sources + globs) 카드."""

    remove_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("dataloader")
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setSpacing(4)

        # reader + 삭제
        _top = QHBoxLayout()
        _top.addWidget(QLabel("reader"))
        self._reader = QComboBox()
        self._reader.addItems(sorted(reader_registry._module_dict))
        _top.addWidget(self._reader, stretch=1)
        _rm = QToolButton()
        _rm.setText("✕")
        _rm.clicked.connect(lambda: self.remove_requested.emit(self))
        _top.addWidget(_rm)
        _lay.addLayout(_top)

        # id_map_file
        _idr = QHBoxLayout()
        _idr.addWidget(QLabel("id_map"))
        self._id_map = QLineEdit("ip_map.json")
        _idr.addWidget(self._id_map, stretch=1)
        _idb = QPushButton("…")
        _idb.setFixedWidth(28)
        _idb.clicked.connect(self._pick_id_map)
        _idr.addWidget(_idb)
        _lay.addLayout(_idr)

        # sources
        _lay.addWidget(QLabel("sources (세션 디렉터리)"))
        self._sources = QListWidget()
        self._sources.setFixedHeight(80)
        _lay.addWidget(self._sources)
        _src_btns = QHBoxLayout()
        _add_src = QPushButton("+ 디렉터리")
        _add_src.clicked.connect(self._add_source)
        _del_src = QPushButton("− 선택삭제")
        _del_src.clicked.connect(self._remove_source)
        _src_btns.addWidget(_add_src)
        _src_btns.addWidget(_del_src)
        _lay.addLayout(_src_btns)

        # globs
        _lay.addWidget(QLabel("globs (key → 패턴)"))
        self._globs = QTableWidget(0, 2)
        self._globs.setHorizontalHeaderLabels(["key", "pattern"])
        self._globs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._globs.setFixedHeight(96)
        _lay.addWidget(self._globs)
        _g_btns = QHBoxLayout()
        _add_g = QPushButton("+ glob")
        _add_g.clicked.connect(lambda: self._add_glob("", ""))
        _del_g = QPushButton("− 선택삭제")
        _del_g.clicked.connect(self._remove_glob)
        _g_btns.addWidget(_add_g)
        _g_btns.addWidget(_del_g)
        _lay.addLayout(_g_btns)

        self._add_glob(FRAME_KEY, "*_pose.png")

    # ── 동작 ──────────────────────────────────────────────────────────────────

    def _pick_id_map(self) -> None:
        _p, _ = QFileDialog.getOpenFileName(self, "id_map 파일", "", "JSON/YAML (*.json *.yaml *.yml)")
        if _p:
            self._id_map.setText(_p)

    def _add_source(self) -> None:
        _d = QFileDialog.getExistingDirectory(self, "세션 디렉터리")
        if _d:
            self._sources.addItem(_d)

    def _remove_source(self) -> None:
        for _it in self._sources.selectedItems():
            self._sources.takeItem(self._sources.row(_it))

    def _add_glob(self, key: str, pattern: str) -> None:
        _r = self._globs.rowCount()
        self._globs.insertRow(_r)
        self._globs.setItem(_r, 0, QTableWidgetItem(key))
        self._globs.setItem(_r, 1, QTableWidgetItem(pattern))

    def _remove_glob(self) -> None:
        for _idx in sorted({_i.row() for _i in self._globs.selectedIndexes()}, reverse=True):
            self._globs.removeRow(_idx)

    # ── public API ───────────────────────────────────────────────────────────

    def to_config(self) -> dict:
        _globs: dict[str, str] = {}
        for _r in range(self._globs.rowCount()):
            _k = self._globs.item(_r, 0)
            _p = self._globs.item(_r, 1)
            if _k and _k.text().strip() and _p and _p.text().strip():
                _globs[_k.text().strip()] = _p.text().strip()

        _sources = [self._sources.item(_i).text() for _i in range(self._sources.count())]

        return Dataloader_config(
            object_type=self._reader.currentText(),
            id_map_file=self._id_map.text().strip(),
            sources=_sources,
            globs=_globs,
        ).Serialize()


class Dataloader_panel(QWidget):
    """여러 dataloader 카드를 관리하는 패널."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cards: list[Dataloader_card] = []
        self._build()
        self.add_card()

    def _build(self) -> None:
        _root = QVBoxLayout(self)
        _root.setContentsMargins(0, 0, 0, 0)

        _hdr = QHBoxLayout()
        _hdr.addWidget(QLabel("Dataloaders"))
        _hdr.addStretch(1)
        _add = QPushButton("+ dataloader")
        _add.clicked.connect(lambda: self.add_card())
        _hdr.addWidget(_add)
        _root.addLayout(_hdr)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        _holder = QWidget()
        _holder.setLayout(self._list_layout)
        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setWidget(_holder)
        _root.addWidget(_scroll, stretch=1)

    def add_card(self) -> Dataloader_card:
        _card = Dataloader_card()
        _card.remove_requested.connect(self._on_remove)
        self._cards.append(_card)
        self._relayout()
        self.changed.emit()
        return _card

    def _on_remove(self, card: Dataloader_card) -> None:
        self._cards.remove(card)
        card.setParent(None)
        card.deleteLater()
        self._relayout()
        self.changed.emit()

    def _relayout(self) -> None:
        while self._list_layout.count():
            _item = self._list_layout.takeAt(0)
            if _item.widget():
                _item.widget().setParent(None)
        for _card in self._cards:
            self._list_layout.addWidget(_card)
        self._list_layout.addStretch(1)

    def configs(self) -> list[dict]:
        """dataloader meta dict 리스트."""
        return [_c.to_config() for _c in self._cards]
