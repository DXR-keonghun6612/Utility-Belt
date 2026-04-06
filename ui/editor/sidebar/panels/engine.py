from dataclasses import dataclass
from typing import Dict, Optional, TypeVar, Generic

from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget, QFrame, QWidget
)
from PySide6.QtCore import Qt, Slot, Signal

from ui.style import ACTIVITY_BAR, NAV_BUTTON

PAGE = TypeVar("PAGE", bound=QWidget)

@dataclass
class Page_Config(Generic[PAGE]):
    text: str
    tooltip: str
    widget: PAGE

class Navigation(QHBoxLayout):
    """Activity Bar와 Side Bar를 통합 관리하는 범용 네비게이션 레이아웃 엔진."""

    toggled = Signal(bool)

    def __init__(self, page_config: dict[str, Page_Config]):
        super().__init__()
        self.pages: Dict[str, QWidget] = {}
        self.nav_buttons: Dict[str, QPushButton] = {}
        self._init_ui(page_config)

    def _init_ui(self, page_config: dict[str, Page_Config]):
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(0)

        self.activity_bar = QFrame()
        self.activity_bar.setFixedWidth(50)
        self.activity_bar.setStyleSheet(ACTIVITY_BAR)

        self.activity_layout = QVBoxLayout(self.activity_bar)
        self.activity_layout.setContentsMargins(0, 5, 0, 5)
        self.activity_layout.setSpacing(2)
        self.activity_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.side_bar = QStackedWidget()
        self.side_bar.setMinimumWidth(50)
        self.side_bar.hide()

        for _key, _cfg in page_config.items():
            _btn = self._create_nav_btn(_cfg.text, _cfg.tooltip)
            _widget = _cfg.widget  # [수정됨] 반영

            self.nav_buttons[_key] = _btn
            self.pages[_key] = _widget
            
            self.activity_layout.addWidget(_btn)
            self.side_bar.addWidget(_widget)
            
            _btn.clicked.connect(lambda checked=False, k=_key: self._toggle_panel(k))

        self.addWidget(self.activity_bar)
        self.addWidget(self.side_bar)

    def _create_nav_btn(self, text: str, tooltip: str) -> QPushButton:
        _btn = QPushButton(text)
        _btn.setFixedSize(50, 50)
        _btn.setToolTip(tooltip)
        _btn.setCheckable(True)
        _btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _btn.setStyleSheet(NAV_BUTTON)
        return _btn

    @Slot(str)
    def _toggle_panel(self, page_key: str):
        _target_widget = self.pages[page_key]
        _is_visible = not self.side_bar.isHidden()
        _is_same_page = (self.side_bar.currentWidget() == _target_widget)

        if _is_visible and _is_same_page:
            self.side_bar.hide()
            self._update_btn_states(None)
            self.toggled.emit(False) # [추가] 닫힘 상태 알림
        else:
            self.side_bar.setCurrentWidget(_target_widget)
            self.side_bar.show()
            self._update_btn_states(page_key)
            self.toggled.emit(True)  # [추가] 열림 상태 알림

    def _update_btn_states(self, active_key: Optional[str]):
        for _key, _btn in self.nav_buttons.items():
            _btn.setChecked(_key == active_key)