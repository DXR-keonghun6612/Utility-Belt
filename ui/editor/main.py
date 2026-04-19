from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QApplication
from PySide6.QtCore import Slot

# 코어 데이터 매니저
from spatial_toolbox.scene import Controller as Stage_Controller

# 분리된 UI 위젯들 임포트
from .viewer import Viewer_Panel
from .sidebar.widget import Main_Sidebar


class Main_Window(QMainWindow):
    """
    VS Code 스타일의 레이아웃 사령탑.
    [Activity/Side Bar (좌)] | [3D Viewer (우)] 구조로 배치함.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Engine Editor")
        self.resize(1280, 720)

        self.stage = Stage_Controller()

        self._Setup_ui()

    def _Setup_ui(self):
        self.holder = QWidget()
        self.setCentralWidget(self.holder)
        
        # 여백과 간격을 0으로 설정하여 사이드바와 뷰어를 밀착시킴
        _main_layout = QHBoxLayout(self.holder)
        _main_layout.setContentsMargins(0, 0, 0, 0)
        _main_layout.setSpacing(0)

        # 2. 위젯 생성
        self.sidebar = Main_Sidebar(self.stage)
        self.viewer = Viewer_Panel(self.stage)

        # 뷰포트 카메라 패널 바인딩
        self.sidebar.camera_page.Bind_camera(self.viewer.camera)

        # 3. 레이아웃에 배치
        _main_layout.addWidget(self.sidebar)
        _main_layout.addWidget(self.viewer)

        # 4. [핵심] 뷰어에게 모든 확장 우선순위를 부여함 (Stretch Factor)
        # 사이드바는 내용물 크기(고정)만큼만 차지하고, 뷰어는 남은 공간을 100% 점유함
        _main_layout.setStretch(0, 0) # Sidebar
        _main_layout.setStretch(1, 1) # Viewer
