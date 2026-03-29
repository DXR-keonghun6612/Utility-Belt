"""Draw.io 스타일 및 테마 정의."""

# 테마 색상 정의
THEME_CLASS = {"header": "#dae8fc", "stroke": "#6c8ebf"}
THEME_METHOD = {"header": "#ffe6cc", "stroke": "#d79b00"}
THEME_GLOBAL = {"header": "#f5f5f5", "stroke": "#666666"}
THEME_MODULE = {"header": "#e1d5e7", "stroke": "#9673a6"}

# 내부 요소 배경색
BG_VARIABLE = "#fff2cc"
BG_METHOD = "#d5e8d4"

# 레이아웃 상수
DEFAULT_WIDTH = 350
START_X = 40
START_Y = 40
MARGIN_Y = 40    # 노드 간 수직 간격

# 요소 높이 상수
ROW_HEIGHT = 26           # 속성/메서드 한 줄의 높이
HEADER_HEIGHT = 40        # 일반 노드(클래스 등) 헤더 높이
STEREOTYPE_HEADER = 60    # 스테레오타입이 있는 노드 헤더 높이
MODULE_HEADER_HEIGHT = 60 # 모듈 컨테이너 헤더 높이

def get_swimlane_style(start_size: int, fill_color: str, stroke_color: str, use_stack: bool = True) -> dict[str, str]:
    """컨테이너(Swimlane) 스타일 반환. 상황에 따라 stackLayout 여부를 결정함."""
    style = {
        "shape": "swimlane",
        "horizontal": "1",
        "horizontalStack": "0",
        "startSize": str(start_size),
        "html": "1",
        "fontStyle": "1",
        "align": "center",
        "verticalAlign": "top",
        "fillColor": fill_color,
        "swimlaneFillColor": "#ffffff",
        "resizeParent": "1",
        "resizeParentMax": "0",
        "resizeLast": "0",
        "collapsible": "1",
        "marginBottom": "0",
        "whiteSpace": "wrap",
        "strokeColor": stroke_color
    }
    
    if use_stack:
        style["childLayout"] = "stackLayout"
        
    return style

def get_child_style(bg_color: str) -> dict[str, str]:
    """내부 요소(속성/메서드) 스타일 반환."""
    return {
        "text": "1",
        "html": "1",
        "align": "left",
        "verticalAlign": "top",
        "spacingTop": "2",
        "spacingLeft": "4",
        "spacingRight": "4",
        "strokeColor": "none",
        "fillColor": bg_color,
        "overflow": "hidden",
        "whiteSpace": "wrap",
        "rotatable": "0"
    }

def get_edge_style(edge_type: str) -> dict[str, str]:
    """연결선(Edge) 스타일 반환."""
    base_style = {
        "edgeStyle": "orthogonalEdgeStyle",
        "rounded": "0",
        "orthogonalLoop": "1",
        "jettySize": "auto",
        "html": "1"
    }
    
    if edge_type == "inheritance":
        base_style.update({
            "endArrow": "block",
            "endFill": "0",
            "strokeWidth": "1"
        })
    else:
        base_style.update({
            "endArrow": "open",
            "dashed": "1",
            "strokeWidth": "1"
        })
    return base_style
