from dataclasses import dataclass
from typing import Generic, TypeVar

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt, Slot, Signal

from ui.style import ACTIVITY_BAR, NAV_BUTTON

PAGE = TypeVar("PAGE", bound=QWidget)

@dataclass
class Page_Config(Generic[PAGE]):
    key: str
    icon_text: str
    tooltip: str
    widget: PAGE

class Sidebar_Container(QWidget):
    """
    도메인 패널에 종속되지 않는 범용 사이드바 컨테이너.
    Activity Bar, Stacked Widget, 그리고 크기 조절 핸들을 통합 관리함.
    """
    toggled = Signal(bool)

    def __init__(self, pages: list[Page_Config], parent=None):
        super().__init__(parent)
        self.pages_dict: dict[str, QWidget] = {}
        self.nav_buttons: dict[str, QPushButton] = {}
        
        # 상태 관리
        self._is_resizing = False
        self._sidebar_width = 300
        self.setFixedWidth(50) # 초기 상태 (닫힘)

        self._Init_ui(pages)

    def _Init_ui(self, pages: list[Page_Config]) -> None:
        _layout = QHBoxLayout(self)
        _layout.setContentsMargins(0, 0, 0, 0)
        _layout.setSpacing(0)

        # 1. Activity Bar (좌측)
        self.activity_bar = QFrame()
        self.activity_bar.setFixedWidth(50)
        self.activity_bar.setStyleSheet(ACTIVITY_BAR)
        
        _act_layout = QVBoxLayout(self.activity_bar)
        _act_layout.setContentsMargins(0, 5, 0, 5)
        _act_layout.setSpacing(2)
        _act_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 2. Stacked Widget (우측 패널 영역)
        self.side_bar = QStackedWidget()
        self.side_bar.setMinimumWidth(50)
        self.side_bar.hide()

        # 페이지 등록
        for _cfg in pages:
            _btn = self._Create_nav_btn(_cfg.icon_text, _cfg.tooltip)
            self.nav_buttons[_cfg.key] = _btn
            self.pages_dict[_cfg.key] = _cfg.widget
            
            _act_layout.addWidget(_btn)
            self.side_bar.addWidget(_cfg.widget)
            
            _btn.clicked.connect(
                lambda checked=False, k=_cfg.key: self._Toggle_panel(k))

        _layout.addWidget(self.activity_bar)
        _layout.addWidget(self.side_bar)

        # 3. 크기 조절 핸들 (우측 끝)
        self.resizer = QFrame(self)
        self.resizer.setFixedWidth(5)
        self.resizer.setCursor(Qt.CursorShape.SizeHorCursor)
        self.resizer.setStyleSheet("background: transparent;")
        self.resizer.hide()

    def _Create_nav_btn(self, text: str, tooltip: str) -> QPushButton:
        _btn = QPushButton(text)
        _btn.setFixedSize(50, 50)
        _btn.setToolTip(tooltip)
        _btn.setCheckable(True)
        _btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _btn.setStyleSheet(NAV_BUTTON)
        return _btn

    @Slot(str)
    def _Toggle_panel(self, page_key: str) -> None:
        _target_widget = self.pages_dict[page_key]
        _is_visible = not self.side_bar.isHidden()
        _is_same_page = (self.side_bar.currentWidget() == _target_widget)

        if _is_visible and _is_same_page:
            self.side_bar.hide()
            self.resizer.hide()
            self.setFixedWidth(50)
            self._Update_btn_states(None)
            self.toggled.emit(False)
        else:
            self.side_bar.setCurrentWidget(_target_widget)
            self.side_bar.show()
            self.resizer.show()
            self.setFixedWidth(50 + self._sidebar_width)
            self._Update_btn_states(page_key)
            self.toggled.emit(True)

    def _Update_btn_states(self, active_key: str | None) -> None:
        for _key, _btn in self.nav_buttons.items():
            _btn.setChecked(_key == active_key)

    # ==========================================
    # 크기 조절 이벤트 (이전 widget.py 로직 병합)
    # ==========================================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resizer.setFixedHeight(self.height())
        self.resizer.move(self.width() - self.resizer.width(), 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.width() - 10 <= event.position().x() <= self.width():
                self._is_resizing = True
                event.accept()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            _new_width = int(event.scenePosition().x())
            if 250 <= _new_width <= 650:
                self._sidebar_width = _new_width - 50
                self.setFixedWidth(_new_width)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_resizing = False
        event.accept()