"""UI 패널 추상화 및 공통 기반 클래스.

모든 Sidebar 패널과 주요 UI 컴포넌트가 상속해야 하는 베이스 클래스입니다.
이벤트 버스 연결과 기본 레이아웃 구성 등 라이프사이클을 정형화합니다.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from ui.core.event_bus import EVENT_BUS

class Base_Panel(QWidget):
    """표준화된 UI 패널 베이스 클래스."""
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.bus = EVENT_BUS
        self.main_layout = QVBoxLayout(self)
        self._configure_default_layout()
        
        # 하위 클래스에서 오버라이드할 라이프사이클 훅
        self._setup_ui()
        self._connect_signals()
        
    def _configure_default_layout(self):
        """패널의 기본 여백과 정렬 상태를 설정합니다."""
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def _setup_ui(self):
        """자식 위젯을 생성하고 self.main_layout에 배치하는 코드를 구현하세요."""
        pass
        
    def _connect_signals(self):
        """Event Bus 또는 내부 시그널을 연결하는 코드를 구현하세요."""
        pass
