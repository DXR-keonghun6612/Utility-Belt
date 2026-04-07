from OpenGL.GL import glReadPixels, GL_RGB, GL_UNSIGNED_BYTE
from data.node import Base_Node
from ..view import Orbit_Camera
from ..renderer import Scene_Renderer 

class Selection_Controller:
    """사용자의 마우스 클릭 좌표를 기반으로 3D 씬 내의 객체를 식별하고 선택 상태를 관리함."""

    def __init__(self):
        self.selected_node: Base_Node | None = None

    def Pick(
        self, x: int, y: int, 
        root_node: Base_Node, 
        camera: Orbit_Camera, 
        renderer: Scene_Renderer
    ) -> Base_Node | None:
        """화면 좌표(x, y)의 픽셀 색상을 읽어 객체를 픽킹함.
        
        [주의]
        OpenGL의 윈도우 좌표계 원점(0,0)은 좌측 하단임.
        Qt 프레임워크의 마우스 이벤트(좌측 상단 원점)에서 넘어온 y 좌표는 
        반드시 (위젯_높이 - y)로 반전되어 전달되어야 함.
        """
        # 1. 렌더러에 오프스크린 ID 패스 렌더링 요청 및 ID 매핑 딕셔너리 획득
        _id_map = renderer.Render_id_pass(root_node, camera)

        # 2. 하드웨어 프레임 버퍼에서 1x1 픽셀 데이터 추출
        _pixel = glReadPixels(x, y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)

        if isinstance(_pixel, bytes):
            # RGB 바이트열을 튜플로 변환하여 딕셔너리 키로 사용
            _color_key = tuple(_pixel)
            
            # 배경(0,0,0)을 클릭했거나 매핑되지 않은 색상이면 None 반환
            self.selected_node = _id_map.get(_color_key, None)
            return self.selected_node

        self.selected_node = None
        return None

    def Clear(self) -> None:
        """현재 선택된 객체 상태를 해제함."""
        self.selected_node = None
        
    def Set_selection(self, node: Base_Node | None) -> None:
        """외부 패널(예: Outliner 트리 뷰)에서 명시적으로 선택 상태를 주입할 때 사용함."""
        self.selected_node = node