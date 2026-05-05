from OpenGL.GL import glReadPixels, GL_RGB, GL_UNSIGNED_BYTE
from spatial_toolbox.scene.node import Base_Node
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

        OpenGL 윈도우 좌표계 원점(0,0)은 좌측 하단임.
        Qt 마우스 이벤트의 y는 호출 측에서 (위젯_높이 - y)로 반전 후 전달해야 함.
        """
        _id_map = renderer.Render_id_pass(root_node, camera)
        _pixel = glReadPixels(x, y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)

        if isinstance(_pixel, bytes):
            _color_key = tuple(_pixel)
            self.selected_node = _id_map.get(_color_key, None)
            return self.selected_node

        self.selected_node = None
        return None

    def Clear(self) -> None:
        self.selected_node = None

    def Set_selection(self, node: Base_Node | None) -> None:
        self.selected_node = node
