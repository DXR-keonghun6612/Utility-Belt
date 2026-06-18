"""메인 페이지 — Pipeline(저작) | Editor(검수·교정) 탭."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from gui.editor import EditorPanel
from gui.pipeline import PipelinePanel


class MainPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        tabs = QTabWidget()
        tabs.addTab(PipelinePanel(), "Pipeline")
        tabs.addTab(EditorPanel(), "Editor")

        root.addWidget(tabs)
