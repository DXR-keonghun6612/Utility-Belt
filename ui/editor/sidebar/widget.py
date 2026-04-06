from PySide6.QtWidgets import QWidget, QFrame
from PySide6.QtCore import Qt, Slot

from .panels.engine import Navigation, Page_Config
from .panels.scene.page import Scene_Explorer_Page
from .panels.asset.browser import Asset_Browser_Panel
from .panels.viewport.camera import Orbit_Camera_Panel

from data.scene.stage import Stage_Controller
from data.registry import Asset_Registry

class Main_Sidebar(QWidget):
    """
    내부에 크기 조절 전용 핸들을 포함하여, 
    자식 위젯의 간섭 없이 사이드바 너비를 조절하는 컨테이너.
    """
    def __init__(self, stage: Stage_Controller, res_manager: Asset_Registry, parent=None):
        super().__init__(parent)

        # 1. 패널 인스턴스화
        self.scene_page = Scene_Explorer_Page(stage)
        self.asset_page = Asset_Browser_Panel(res_manager)
        self.camera_page = Orbit_Camera_Panel()

        page_config = {
            "scene": Page_Config("🗂", "Scene Explorer", self.scene_page),
            "asset": Page_Config("📦", "Asset Browser", self.asset_page),
            "camera": Page_Config("🎥", "Viewport Camera", self.camera_page)
        }

        # 2. 레이아웃 엔진 설정
        self.nav_panel = Navigation(page_config)
        self.setLayout(self.nav_panel)

        # 3. [핵심] 크기 조절용 투명 핸들 위젯 생성
        # 이 위젯이 오른쪽 끝에 배치되어 마우스 이벤트를 전담함
        self.resizer = QFrame(self)
        self.resizer.setFixedWidth(5) # 5픽셀 두께의 감지 영역
        self.resizer.setCursor(Qt.CursorShape.SizeHorCursor)
        self.resizer.setStyleSheet("background: transparent;") # 평소엔 투명
        
        # 4. 상태 관리 변수
        self._is_resizing = False
        self._sidebar_width = 300
        self.setFixedWidth(50) # 초기 상태 (닫힘)

        # 엔진의 토글 신호 연결 (toggled 시그널은 engine.py에 추가 필요)
        self.nav_panel.toggled.connect(self._on_navigation_toggled)

    def resizeEvent(self, event):
        """사이드바 크기가 변할 때 핸들 위젯을 항상 오른쪽 끝에 붙임."""
        super().resizeEvent(event)
        self.resizer.setFixedHeight(self.height())
        self.resizer.move(self.width() - self.resizer.width(), 0)

    # ==========================================
    # 크기 조절 핸들 이벤트 오버라이딩
    # ==========================================

    def mousePressEvent(self, event):
        # resizer 영역 내에서 클릭했는지 확인
        if event.button() == Qt.MouseButton.LeftButton:
            _pos = event.position().x()
            if self.width() - 10 <= _pos <= self.width():
                self._is_resizing = True
                event.accept()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            # 전체 창(Global) 기준 마우스 좌표로 계산하여 끊김 현상 방지
            new_width = int(event.scenePosition().x())
            
            # 최소 250(Activity 50 + Side 200) ~ 최대 650 사이로 제한
            if 250 <= new_width <= 650:
                self._sidebar_width = new_width - 50
                self.setFixedWidth(new_width)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_resizing = False
        event.accept()

    @Slot(bool)
    def _on_navigation_toggled(self, is_open: bool):
        """패널이 열리면 이전 너비로, 닫히면 50px로 즉시 변경."""
        if is_open:
            self.resizer.show()
            self.setFixedWidth(50 + self._sidebar_width)
        else:
            self.resizer.hide()
            self.setFixedWidth(50)