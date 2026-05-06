from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget
from spatial_toolbox.scene import Controller as Stage_Controller

from ui.viewer import Viewer_Panel
from ui.sidebar.container import Sidebar_Container, Page_Config
from ui.panels.scene.page import Scene_Explorer_Page
from ui.panels.asset.browser import Asset_Browser_Panel
from ui.panels.viewport.camera import Orbit_Camera_Panel
from ui.panels.simulation.page import Simulation_Page


class Main_Window(QMainWindow):
    """
    레이아웃 사령탑.
    모든 도메인 패널을 독립적으로 인스턴스화하고, 이를 사이드바 컨테이너에 주입함.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Engine Editor")
        self.resize(1280, 720)

        self.stage = Stage_Controller()
        self._Setup_ui()

    def _Setup_ui(self) -> None:
        self.holder = QWidget()
        self.setCentralWidget(self.holder)

        _root_layout = QVBoxLayout(self.holder)
        _root_layout.setContentsMargins(0, 0, 0, 0)
        _root_layout.setSpacing(0)

        self.content_holder = QWidget()
        _main_layout = QHBoxLayout(self.content_holder)
        _main_layout.setContentsMargins(0, 0, 0, 0)
        _main_layout.setSpacing(0)

        self.viewer = Viewer_Panel(self.stage)

        self.scene_page      = Scene_Explorer_Page(self.stage)
        self.asset_page      = Asset_Browser_Panel()
        self.camera_page     = Orbit_Camera_Panel()
        self.simulation_page = Simulation_Page(self.stage)

        self.camera_page.Bind_camera(self.viewer.camera)
        self.camera_page.Bind_viewer_config(self.viewer.renderer.config)

        _pages = [
            Page_Config("scene",      "🗂",  "Scene Explorer",    self.scene_page),
            Page_Config("asset",      "📦",  "Asset Browser",     self.asset_page),
            Page_Config("camera",     "🎥",  "Viewport Camera",   self.camera_page),
            Page_Config("simulation", "🎬",  "Simulation Engine", self.simulation_page),
        ]
        self.sidebar = Sidebar_Container(_pages)

        _main_layout.addWidget(self.sidebar)
        _main_layout.addWidget(self.viewer)
        _main_layout.setStretch(0, 0)
        _main_layout.setStretch(1, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(False)
        self.status_label.setFixedHeight(20)
        self.status_label.setStyleSheet(
            "padding: 1px 8px; font-size: 11px; border-top: 1px solid #2c2c2c; background: #171717; color: #d8d8d8;"
        )

        _root_layout.addWidget(self.content_holder)
        _root_layout.addWidget(self.status_label)

        self.asset_page.bus.loading_progress.connect(self._On_loading_progress)
        self.asset_page.bus.simulation_progress.connect(self._On_simulation_progress)

    @Slot(int, int, str)
    def _On_loading_progress(self, current: int, total: int, message: str) -> None:
        if total > 0:
            _current = max(0, min(current, total))
            self.status_label.setText(f"{message} ({_current}/{total})")
        else:
            self.status_label.setText(message)
        QApplication.processEvents()

    @Slot(int, int, str)
    def _On_simulation_progress(self, current: int, total: int, message: str) -> None:
        if total > 0:
            _current = max(0, min(current, total))
            self.status_label.setText(f"Simulation: {message} ({_current}/{total})")
        else:
            self.status_label.setText(f"Simulation: {message}")
        QApplication.processEvents()
