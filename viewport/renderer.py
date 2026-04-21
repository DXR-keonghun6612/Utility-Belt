from OpenGL.GL import *
from spatial_toolbox.scene.node import Base_Node
from spatial_toolbox.scene.node import Mesh
from spatial_toolbox.scene.node import Camera
from spatial_toolbox.scene.node.utils.traversal import walk_nodes
from spatial_toolbox.graphics.openGL.renderer import OpenGL_Renderer

from .view import Orbit_Camera
from .tool.camera_gizmo import Draw_camera_gizmo

class Scene_Renderer:
    """OpenGL 고정 파이프라인을 활용하여 씬 검증 및 픽킹용 ID Pass를 렌더링하는 클래스."""

    def __init__(self, width: int = 800, height: int = 600):
        self.render_mode = "SOLID"
        self._bg_color = (0.15, 0.15, 0.15, 1.0)
        self._renderer = OpenGL_Renderer(width, height)
        self._selected_node: Base_Node | None = None

    def Initialize(self) -> None:
        """초기 OpenGL 컨텍스트 및 조명 상태를 설정함 (위젯 초기화 시 1회 호출)."""
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_POLYGON_SMOOTH)

        # viewport는 발광에 가까운 ambient(=1.0)로 객체를 항상 식별 가능하게 유지
        self._renderer.light_position = [0.0, 1.0, 0.0, 0.0]
        self._renderer.light_ambient = [1.0, 1.0, 1.0, 1.0]

    # ==========================================
    # 메인 렌더 패스 (시각적 검증용)
    # ==========================================

    def Render_frame(
        self, root_node: Base_Node,
        camera: Orbit_Camera, selected_node: Base_Node | None
    ) -> None:
        """메인 뷰포트 화면을 갱신함."""
        glClearColor(*self._bg_color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        camera.Apply_view()
        self._renderer.Apply_lighting()
        self._Draw_ground_grid()

        if self.render_mode == "WIREFRAME":
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glDisable(GL_LIGHTING)
            glColor3f(0.8, 0.8, 0.8)
        else:
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glEnable(GL_LIGHTING)

        self._selected_node = selected_node
        
        for node in walk_nodes(root_node, lambda _: True):
            self._On_main_node(node)

    def _On_main_node(self, node: Base_Node) -> None:
        """메인 패스 콜백 — 메시/카메라 기즈모/선택 하이라이트 분기."""
        from spatial_toolbox.scene import ASSET_CACHE

        if isinstance(node, Mesh) and node.source_key is not None:
            _asset = ASSET_CACHE.Get(node.source_key, is_hold=True)
            if _asset is None or _asset.geometry is None:
                return

            glPushMatrix()
            glMultMatrixf(node.world_matrix.T)

            if node is self._selected_node:
                glColor3f(1.0, 0.8, 0.2)
                glLineWidth(2.0)

                if self.render_mode == "SOLID":
                    glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
                    glDisable(GL_LIGHTING)
                    self._renderer.Draw_mesh(_asset.geometry)
                    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
                    glEnable(GL_LIGHTING)
                else:
                    self._renderer.Draw_mesh(_asset.geometry)
            else:
                glColor3f(0.6, 0.6, 0.6)
                self._renderer.Draw_mesh(_asset.geometry)
                
            glPopMatrix()
            return

        if isinstance(node, Camera):
            glPushMatrix()
            glMultMatrixf(node.world_matrix.T)
            Draw_camera_gizmo(
                intrinsic=node.intrinsic,
                is_selected=(node is self._selected_node)
            )
            glPopMatrix()

    # ==========================================
    # 오프스크린 ID 렌더 패스 (픽킹용)
    # ==========================================

    def Render_id_pass(
        self, root_node: Base_Node, camera: Orbit_Camera
    ) -> dict:
        """픽킹을 위한 ID 패스를 렌더링하고 컬러맵을 반환함."""
        glClearColor(0, 0, 0, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)
        glDisable(GL_MULTISAMPLE)

        camera.Apply_view()

        self._renderer.Reset_id_state()
        
        from spatial_toolbox.scene import ASSET_CACHE
        for node in walk_nodes(root_node, lambda x: isinstance(x, Mesh)):
            if node.source_key is not None:
                _asset = ASSET_CACHE.Get(node.source_key, is_hold=True)
                if _asset is not None and _asset.geometry is not None:
                    glPushMatrix()
                    glMultMatrixf(node.world_matrix.T)
                    self._renderer.Draw_mesh(_asset.geometry, mode="id_color", node=node)
                    glPopMatrix()

        glFlush()

        glEnable(GL_LIGHTING)
        glEnable(GL_DITHER)
        glEnable(GL_MULTISAMPLE)

        return self._renderer.id_map

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
