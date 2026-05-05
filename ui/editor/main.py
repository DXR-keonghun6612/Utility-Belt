from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout
from spatial_toolbox.scene import Controller as Stage_Controller

from ui.editor.viewer import Viewer_Panel
from ui.editor.sidebar.container import Sidebar_Container, Page_Config
from ui.editor.panels.scene.page import Scene_Explorer_Page
from ui.editor.panels.asset.browser import Asset_Browser_Panel
from ui.editor.panels.viewport.camera import Orbit_Camera_Panel
from ui.editor.panels.simulation.page import Simulation_Page
# 시뮬레이션 패널 등 추가 필요 시 여기서 임포트

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
        
        _main_layout = QHBoxLayout(self.holder)
        _main_layout.setContentsMargins(0, 0, 0, 0)
        _main_layout.setSpacing(0)

        # 1. 뷰어 및 도메인 패널 독립 생성
        self.viewer = Viewer_Panel(self.stage)
        
        self.scene_page = Scene_Explorer_Page(self.stage)
        self.asset_page = Asset_Browser_Panel()
        self.camera_page = Orbit_Camera_Panel()
        self.simulation_page = Simulation_Page(self.stage)

        self.camera_page.Bind_camera(self.viewer.camera)
        self.camera_page.Bind_viewer_config(self.viewer.renderer.config)

        # 2. 범용 사이드바 컨테이너에 페이지 주입 (Dependency Injection)
        _pages = [
            Page_Config("scene", "🗂", "Scene Explorer", self.scene_page),
            Page_Config("asset", "📦", "Asset Browser", self.asset_page),
            Page_Config("camera", "🎥", "Viewport Camera", self.camera_page),
            Page_Config("simulation", "🎬", "Simulation Engine", self.simulation_page)
        ]
        self.sidebar = Sidebar_Container(_pages)

        # 3. 레이아웃 배치
        _main_layout.addWidget(self.sidebar)
        _main_layout.addWidget(self.viewer)

        _main_layout.setStretch(0, 0) # Sidebar 크기 고정 (내부 resizer가 너비 결정)
        _main_layout.setStretch(1, 1) # Viewer 가변 확장