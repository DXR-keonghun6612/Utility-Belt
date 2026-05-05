from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from ui.event_bus import EVENT_BUS


class Base_Panel(QWidget):
    """표준화된 UI 패널 베이스 클래스."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.bus = EVENT_BUS
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self): pass
    def _connect_signals(self): pass
