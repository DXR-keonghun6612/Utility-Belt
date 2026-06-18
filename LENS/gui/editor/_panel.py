"""Editor 탭 — 결과 검수·교정 (트리 + 썸네일 조합).

좌: class 트리(드래그&드롭 재지정). 우: 선택한 class 의 결과 썸네일 그리드.
그리드에서 다중 선택 후 버튼으로도 재지정/제외할 수 있다. 교정 결과는
categorization.json 으로 저장한다. mask 페인팅은 후속(#3b).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui.editor._grid import Grid
from gui.editor._model import EXCLUDED, Editor_model
from gui.editor._tree import Category_tree


class EditorPanel(QWidget):
    """결과 검수·교정 탭."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = Editor_model()
        self._current: object = None   # 그리드에 표시 중인 class key
        self._build()

    # ── build ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        _root = QVBoxLayout(self)
        _root.setContentsMargins(4, 4, 4, 4)

        # 상단 바
        _bar = QHBoxLayout()
        _open = QPushButton("결과 폴더 열기")
        _open.clicked.connect(self._on_open)
        _bar.addWidget(_open)
        _bar.addStretch(1)
        _bar.addWidget(QLabel("선택 →"))
        self._target = QComboBox()
        self._target.setEditable(True)
        self._target.setMinimumWidth(140)
        _bar.addWidget(self._target)
        for _txt, _slot in (
            ("재지정", self._on_reassign),
            ("제외",   self._on_exclude),
            ("복원",   self._on_restore),
        ):
            _btn = QPushButton(_txt)
            _btn.clicked.connect(_slot)
            _bar.addWidget(_btn)
        _save = QPushButton("저장")
        _save.clicked.connect(self._on_save)
        _bar.addWidget(_save)
        _root.addLayout(_bar)

        # 트리 + 그리드
        self._tree = Category_tree(self._model)
        self._tree.category_selected.connect(self._on_category)
        self._tree.changed.connect(self._on_model_changed)

        self._grid = Grid()

        _split = QSplitter(Qt.Orientation.Horizontal)
        _split.addWidget(self._tree)
        _split.addWidget(self._grid)
        _split.setSizes([260, 740])
        _root.addWidget(_split, stretch=1)

        self._status = QLabel("결과 폴더를 여세요.")
        self._status.setStyleSheet("color: #aaa;")
        _root.addWidget(self._status)

    # ── 핸들러 ────────────────────────────────────────────────────────────────

    def _on_open(self) -> None:
        _d = QFileDialog.getExistingDirectory(self, "결과 폴더 (<class>/<stem>.png)")
        if not _d:
            return
        try:
            self._model.load(Path(_d))
        except Exception as _e:
            self._status.setText(f"로드 실패: {_e}")
            return
        self._tree.rebuild()
        self._reload_targets()
        self._current = None
        self._grid.populate(self._model.filtered(None))
        self._status.setText(f"로드: {len(self._model.entries)}개 · {Path(_d).name}")

    def _reload_targets(self) -> None:
        _cur = self._target.currentText()
        self._target.clear()
        self._target.addItems(self._model.classes())
        self._target.setCurrentText(_cur)

    def _on_category(self, cls) -> None:
        self._current = cls
        self._grid.populate(self._model.filtered(cls))

    def _on_model_changed(self) -> None:
        # 트리 재지정/제외/복원 후 그리드·콤보 동기화.
        self._reload_targets()
        self._grid.populate(self._model.filtered(self._current))

    def _grid_op(self, op, *args, label: str = "") -> None:
        _rels = self._grid.selected_rels()
        if not _rels:
            self._status.setText("그리드에서 항목을 선택하세요.")
            return
        op(_rels, *args)
        self._tree.rebuild()
        self._reload_targets()
        self._grid.populate(self._model.filtered(self._current))
        self._status.setText(f"{label}: {len(_rels)}개")

    def _on_reassign(self) -> None:
        _new = self._target.currentText().strip()
        if not _new:
            self._status.setText("대상 class 를 입력하세요.")
            return
        self._grid_op(self._model.reassign, _new, label=f"재지정 → {_new}")

    def _on_exclude(self) -> None:
        self._grid_op(self._model.exclude, label="제외")

    def _on_restore(self) -> None:
        self._grid_op(self._model.restore, label="복원")

    def _on_save(self) -> None:
        try:
            _path = self._model.save()
        except Exception as _e:
            self._status.setText(f"저장 실패: {_e}")
            return
        self._status.setText(f"저장(적용) 완료: 파일 {self._model.moved}개 이동 · {_path}")
