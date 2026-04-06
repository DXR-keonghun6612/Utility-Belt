from OpenGL.GL import *
from data.scene.node import Scene_Node
from data.scene.node.mesh import Mesh_Node
from data.scene.node.camera import Camera_Node
from .view import Orbit_Camera
from .tool.camera_gizmo import Draw_camera_gizmo
from graphics.core.draw import Draw_mesh

class Scene_Renderer:
    """OpenGL 고정 파이프라인을 활용하여 씬 검증 및 픽킹용 ID Pass를 렌더링하는 클래스."""

    def __init__(self):
        self.render_mode = "SOLID"
        self._bg_color = (0.15, 0.15, 0.15, 1.0)

    def Initialize(self) -> None:
        """초기 OpenGL 컨텍스트 및 조명 상태를 설정함 (위젯 초기화 시 1회 호출)."""
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_POLYGON_SMOOTH)

        glLightfv(GL_LIGHT0, GL_POSITION, [0.0, 1.0, 0.0, 0.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [1.0, 1.0, 1.0, 1.0])

    # ==========================================
    # 메인 렌더 패스 (시각적 검증용)
    # ==========================================

    def Render_frame(
        self, root_node: Scene_Node,
        camera: Orbit_Camera, selected_node: Scene_Node | None
    ) -> None:
        """메인 뷰포트 화면을 갱신함."""
        glClearColor(*self._bg_color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        camera.Apply_view()
        self._Draw_ground_grid()

        if self.render_mode == "WIREFRAME":
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glDisable(GL_LIGHTING)
            glColor3f(0.8, 0.8, 0.8)
        else:
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glEnable(GL_LIGHTING)

        self._Render_scene_recursive(root_node, selected_node)

    def _Render_scene_recursive(
        self, node: Scene_Node, selected_node: Scene_Node | None
    ) -> None:
        """노드 계층을 순회하며 메쉬, 카메라 기즈모, 선택 하이라이트를 그림."""
        if not node.is_renderable:
            return

        glPushMatrix()
        glMultMatrixf(node.local_matrix.T)

        if isinstance(node, Mesh_Node) and node.mesh is not None:
            if node is selected_node:
                glColor3f(1.0, 0.8, 0.2)
                glLineWidth(2.0)

                if self.render_mode == "SOLID":
                    glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
                    glDisable(GL_LIGHTING)
                    Draw_mesh(node.mesh)
                    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
                    glEnable(GL_LIGHTING)
                else:
                    Draw_mesh(node.mesh)
            else:
                glColor3f(0.6, 0.6, 0.6)
                Draw_mesh(node.mesh)

        if isinstance(node, Camera_Node):
            _intr = node.intrinsic
            Draw_camera_gizmo(
                fov=_intr.fov if _intr else 60.0,
                sensor_w=_intr.sensor_width if _intr else 36.0,
                sensor_h=_intr.sensor_height if _intr else 24.0,
                is_selected=(node is selected_node)
            )

        for _child in node.children:
            self._Render_scene_recursive(_child, selected_node)

        glPopMatrix()

    # ==========================================
    # 오프스크린 ID 렌더 패스 (픽킹용)
    # ==========================================

    def Render_id_pass(
        self, root_node: Scene_Node, camera: Orbit_Camera
    ) -> dict:
        """픽킹을 위한 ID 패스를 렌더링하고 컬러맵을 반환함."""
        glClearColor(0, 0, 0, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)
        glDisable(GL_MULTISAMPLE)

        camera.Apply_view()

        _id_map: dict = {}
        self._id_counter = 1
        self._Draw_id_recursive(root_node, _id_map)

        glFlush()

        glEnable(GL_LIGHTING)
        glEnable(GL_DITHER)
        glEnable(GL_MULTISAMPLE)

        return _id_map

    def _Draw_id_recursive(self, node: Scene_Node, id_map: dict) -> None:
        """고유 색상 기반의 ID 메쉬를 그림."""
        if not node.is_renderable:
            return

        glPushMatrix()
        glMultMatrixf(node.local_matrix.T)

        if isinstance(node, Mesh_Node) and node.mesh is not None:
            _idx = self._id_counter
            _r = _idx & 0xFF
            _g = (_idx >> 8) & 0xFF
            _b = (_idx >> 16) & 0xFF
            _color_key = (_r, _g, _b)

            id_map[_color_key] = node
            glColor3ub(_r, _g, _b)

            Draw_mesh(node.mesh)
            self._id_counter += 1

        for _child in node.children:
            self._Draw_id_recursive(_child, id_map)

        glPopMatrix()

    # ==========================================
    # 그리드
    # ==========================================

    def _Draw_ground_grid(self, cover_range: int = 10) -> None:
        """레이아웃 배치를 위한 Z=0 기준 평면 그리드를 그림."""
        glDisable(GL_LIGHTING)
        glColor3f(0.3, 0.3, 0.3)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for i in range(-cover_range, cover_range + 1):
            glVertex3f(float(i), 0.0, -float(cover_range))
            glVertex3f(float(i), 0.0, float(cover_range))
            glVertex3f(-float(cover_range), 0.0, float(i))
            glVertex3f(float(cover_range), 0.0, float(i))
        glEnd()
        glEnable(GL_LIGHTING)
