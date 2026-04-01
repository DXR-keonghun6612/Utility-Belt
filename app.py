import sys
from PySide6.QtWidgets import QApplication

from graphics.ui.editor.main import Main_Window


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = Main_Window()
    window.show()
    sys.exit(app.exec())