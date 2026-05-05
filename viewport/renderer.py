from OpenGL.GL import *
from spatial_toolbox.scene.node import Base_Node, Mesh, Camera
from spatial_toolbox.scene.node.utils.traversal import walk_nodes
from spatial_toolbox.render.openGL import OpenGL_Renderer

from .view import Orbit_Camera
from .node.grid import Ground_Grid
from .node.camera_frustum import Camera_Frustum


class Scene_Renderer:
    """OpenGL 고정 파이프라인을 활용하여 씬 검증 및 픽킹용 ID Pass를 렌더링하는 클래스."""

    def __init__(self, width: int = 800, height: int = 600):
        self.render_mode = "SOLID"
        self._bg_color = (0.15, 0.15, 0.15, 1.0)
        self._renderer = OpenGL_Renderer(width, height)
        self._selected_node: Base_Node | None = None
        self._grid = Ground_Grid()
        self._camera_frustum = Camera_Frustum()

    @property
    def config(self):
        """Viewer_Config 접근점 — Ground_Grid가 소유함."""
        return self._grid.config

    def Initialize(self) -> None:
        """초기 OpenGL 컨텍스트 및 조명 상태를 설정함 (위젯 초기화 시 1회 호출)."""
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_POLYGON_SMOOTH)
        self._renderer.light_position = [0.0, 1.0, 0.0, 0.0]
        self._renderer.light_ambient  = [1.0, 1.0, 1.0, 1.0]

    # ==========================================
    # 메인 렌더 패스
    # ==========================================

    def Render_frame(
        self, root_node: Base_Node,
        camera: Orbit_Camera, selected_node: Base_Node | None
    ) -> None:
        glClearColor(*self._bg_color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        camera.Apply_view()
        self._renderer.Apply_lighting()
        self._grid.Draw()

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
                    self._renderer.Draw(primitive="mesh", data=_asset.geometry)
                    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
                    glEnable(GL_LIGHTING)
                else:
                    self._renderer.Draw(primitive="mesh", data=_asset.geometry)
            else:
                glColor3f(0.6, 0.6, 0.6)
                self._renderer.Draw(primitive="mesh", data=_asset.geometry)

            glPopMatrix()
            return

        if isinstance(node, Camera):
            glPushMatrix()
            glMultMatrixf(node.world_matrix.T)
            self._camera_frustum.Draw(
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
                    self._renderer.Draw(
                        primitive="mesh", data=_asset.geometry,
                        mode="id_color", node=node
                    )
                    glPopMatrix()

        glFlush()

        glEnable(GL_LIGHTING)
        glEnable(GL_DITHER)
        glEnable(GL_MULTISAMPLE)

        return self._renderer.id_map
