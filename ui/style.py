"""UI 전역 스타일 정의 모듈.

모든 Qt 위젯 스타일시트를 단일 지점에서 관리함.
색상 토큰 → 컴포넌트 스타일 → 복합 스타일 순으로 구성됨.
"""


# ==========================================
# 색상 토큰
# ==========================================

class Color:
    """프로젝트 공용 색상 팔레트."""
    BG_DARK = "#252526"
    BG_MID = "#2A2A2A"
    BG_PANEL = "#333333"
    BORDER = "#555555"
    BORDER_DARK = "#444444"
    BORDER_ACCENT = "#88AAFF"

    TEXT = "#E8E8E8"
    TEXT_HEADER = "#E0E0E0"
    TEXT_DIM = "#AAAAAA"
    TEXT_MUTED = "#888888"
    TEXT_GROUP = "#CCCCCC"
    TEXT_NAV = "#858585"

    AXIS_X = "#FF5555"
    AXIS_Y = "#55FF55"
    AXIS_Z = "#5555FF"
    AXIS_W = "#AAAAAA"

    HIGHLIGHT = "#37373d"
    HOVER = "#444444"


AXIS_COLORS = [Color.AXIS_X, Color.AXIS_Y, Color.AXIS_Z]
AXIS_COLORS_WXYZ = [Color.AXIS_W, Color.AXIS_X, Color.AXIS_Y, Color.AXIS_Z]


# ==========================================
# 컴포넌트 스타일
# ==========================================

SPIN_BOX = f"""
    QDoubleSpinBox {{
        font-size: 13px;
        padding: 3px 4px;
        background: {Color.BG_MID};
        color: {Color.TEXT};
        border: 1px solid {Color.BORDER};
        border-radius: 2px;
        min-height: 24px;
    }}
    QDoubleSpinBox:focus {{
        border: 1px solid {Color.BORDER_ACCENT};
    }}
"""


def Spin_box_accented(color: str) -> str:
    """하단에 축 색상 악센트가 적용된 스핀박스 스타일을 생성함."""
    return f"""
    QDoubleSpinBox {{
        font-size: 13px;
        padding: 3px 4px;
        background: {Color.BG_MID};
        color: {Color.TEXT};
        border: 1px solid {Color.BORDER};
        border-bottom: 2px solid {color};
        border-radius: 2px;
        min-height: 24px;
    }}
    QDoubleSpinBox:focus {{
        border: 1px solid {color};
        border-bottom: 2px solid {color};
    }}
"""


def Axis_label(color: str) -> str:
    """축 라벨(X/Y/Z/W) 스타일을 생성함."""
    return f"font-size: 12px; font-weight: bold; color: {color}; min-width: 14px;"


LABEL = f"font-size: 12px; color: {Color.TEXT_DIM};"

HEADER = f"font-size: 16px; font-weight: bold; color: {Color.TEXT_HEADER};"

SUB_HEADER = f"font-size: 12px; color: {Color.TEXT_MUTED};"

GROUP_BOX = f"QGroupBox {{ font-weight: bold; color: {Color.TEXT_GROUP}; }}"

SEPARATOR = f"color: {Color.BORDER_DARK};"

BUTTON = "QPushButton { padding: 6px; font-size: 12px; }"


# ==========================================
# 네비게이션 스타일
# ==========================================

ACTIVITY_BAR = f"background-color: {Color.BG_PANEL}; border-right: 1px solid {Color.BG_DARK}"

SIDE_BAR = f"background-color: {Color.BG_DARK}; border-right: 1px solid #111111"

NAV_BUTTON = f"""
    QPushButton {{ background-color: transparent; border: none; color: {Color.TEXT_NAV}; font-size: 18px; font-weight: bold; }}
    QPushButton:hover {{ background-color: {Color.HOVER}; color: white; }}
    QPushButton:checked {{ border-left: 2px solid white; background-color: {Color.HIGHLIGHT}; color: white; }}
"""
