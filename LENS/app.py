"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow

from gui.page import Main_page


def _dark_palette() -> QPalette:
    """애플리케이션 전역에 적용할 다크 테마 팔레트를 만든다."""
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(45, 45, 45))
    p.setColor(QPalette.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.Base,            QColor(30, 30, 30))
    p.setColor(QPalette.AlternateBase,   QColor(40, 40, 40))
    p.setColor(QPalette.ToolTipBase,     QColor(50, 50, 50))
    p.setColor(QPalette.ToolTipText,     QColor(220, 220, 220))
    p.setColor(QPalette.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.Button,          QColor(60, 60, 60))
    p.setColor(QPalette.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.BrightText,      QColor(255, 80, 80))
    p.setColor(QPalette.Highlight,       QColor(42, 130, 218))
    p.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    return p


class Main_window(QMainWindow):
    """LENS 애플리케이션 최상위 윈도우."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LENS")
        self.resize(1280, 860)
        self.setCentralWidget(Main_page())


def main() -> None:
    """Qt 애플리케이션을 띄우고 이벤트 루프를 시작한다."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())
    win = Main_window()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
