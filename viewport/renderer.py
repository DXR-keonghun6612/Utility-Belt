from OpenGL.GL import *
from scene.node import Scene_Node
from viewport.view import Orbit_Camera

class Scene_Renderer:
    """OpenGL 고정 파이프라인을 활용하여 씬 검증 및 픽킹용 ID Pass를 렌더링하는 클래스."""
    
    def __init__(self):
        # 렌더링 검증 모드: "SOLID", "WIREFRAME"
        self.render_mode = "SOLID"
        self._bg_color = (0.15, 0.15, 0.15, 1.0)

    def Initialize(self):
        """초기 OpenGL 컨텍스트 및 조명 상태를 설정함 (위젯 초기화 시 1회 호출)."""
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_LIGHTING)
        # glEnable(GL_LIGHT0)
        
        # 기본 조명 설정 (단순 검증용이므로 하드코딩)
        glLightfv(GL_LIGHT0, GL_POSITION, [1.0, 1.0, 1.0, 0.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])

    # ==========================================
    # 메인 렌더 패스 (시각적 검증용)
    # ==========================================

    def Render_frame(self, root_node: Scene_Node, camera: Orbit_Camera, selected_node: Scene_Node | None):
        """메인 뷰포트 화면을 갱신함."""
        glClearColor(*self._bg_color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # 카메라 시점 적용
        camera.Apply_view()
        
        self._Draw_ground_grid()
        
        # 렌더 모드 분기 (검증 목적)
        if self.render_mode == "WIREFRAME":
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glDisable(GL_LIGHTING)
            glColor3f(0.8, 0.8, 0.8) # 와이어프레임 기본 색상
        else:
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glEnable(GL_LIGHTING)

        # 트리 순회 렌더링 시작
        self._Render_scene_recursive(root_node, selected_node)

    def _Render_scene_recursive(self, node: Scene_Node, selected_node: Scene_Node | None):
        """노드 계층을 순회하며 메쉬 및 선택 하이라이트를 그림."""
        glPushMatrix()
        
        # 현재 노드의 로컬 변환을 OpenGL 상태 머신에 곱함 (우측 곱셈)
        glMultMatrixf(node.local_matrix.T)

        if node.mesh:
            if node is selected_node:
                # 선택된 노드 하이라이트 (노란색 선)
                glColor3f(1.0, 0.8, 0.2)
                glLineWidth(2.0)
                
                # 솔리드 모드일 때도 선택된 객체는 와이어프레임 덧그리기
                if self.render_mode == "SOLID":
                    glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
                    glDisable(GL_LIGHTING)
                    self._Draw_mesh(node.mesh)
                    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
                    glEnable(GL_LIGHTING)
                else:
                    self._Draw_mesh(node.mesh)
            else:
                # 기본 솔리드 색상
                glColor3f(0.6, 0.6, 0.6)
                self._Draw_mesh(node.mesh)

        # 자식 노드 재귀 호출
        for _child in node.children:
            self._Render_scene_recursive(_child, selected_node)
            
        glPopMatrix()

    # ==========================================
    # 오프스크린 ID 렌더 패스 (픽킹용)
    # ==========================================

    def Render_id_pass(self, root_node: Scene_Node, camera: Orbit_Camera) -> dict:
        """픽킹을 위한 ID 패스를 렌더링하고 컬러맵을 반환함 (사용자에게 보이지 않음)."""
        glClearColor(0, 0, 0, 1) # 배경은 0번 ID (검은색)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # ID 패스에서는 조명과 안티앨리어싱이 색상 값을 훼손하므로 반드시 꺼야 함
        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)
        glDisable(GL_MULTISAMPLE)
        
        camera.Apply_view()
        
        _id_map = {}
        self._id_counter = 1 # 0은 배경이므로 1부터 시작
        self._Draw_id_recursive(root_node, _id_map)
        
        glFlush() # 프레임 버퍼에 강제 쓰기 완료
        
        # 상태 복구
        glEnable(GL_LIGHTING)
        glEnable(GL_DITHER)
        glEnable(GL_MULTISAMPLE)
        
        return _id_map

    def _Draw_id_recursive(self, node: Scene_Node, id_map: dict):
        """고유 색상 기반의 ID 메쉬를 그림."""
        glPushMatrix()
        glMultMatrixf(node.local_matrix.T)

        if node.mesh:
            # 카운터를 RGB 컬러 키로 인코딩
            _idx = self._id_counter
            _r = _idx & 0xFF
            _g = (_idx >> 8) & 0xFF
            _b = (_idx >> 16) & 0xFF
            _color_key = (_r, _g, _b)
            
            id_map[_color_key] = node
            glColor3ub(_r, _g, _b)
            
            self._Draw_mesh(node.mesh)
            self._id_counter += 1

        for _child in node.children:
            self._Draw_id_recursive(_child, id_map)
            
        glPopMatrix()

    # ==========================================
    # 코어 드로우 로직
    # ==========================================

    def _Draw_mesh(self, mesh):
        """Trimesh 지오메트리 데이터를 고정 파이프라인으로 렌더링함."""
        if mesh is None or not hasattr(mesh, 'vertices') or not hasattr(mesh, 'faces'): 
            return
            
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, mesh.vertices)
        
        # 노멀 데이터가 있다면 조명 연산을 위해 전달
        if hasattr(mesh, 'vertex_normals'):
            glEnableClientState(GL_NORMAL_ARRAY)
            glNormalPointer(GL_FLOAT, 0, mesh.vertex_normals)
            
        glDrawElements(GL_TRIANGLES, len(mesh.faces) * 3, GL_UNSIGNED_INT, mesh.faces)
        
        glDisableClientState(GL_VERTEX_ARRAY)
        if hasattr(mesh, 'vertex_normals'):
            glDisableClientState(GL_NORMAL_ARRAY)

    def _Draw_ground_grid(self):
        """레이아웃 배치를 위한 Z=0 기준 평면 그리드를 그림."""
        glDisable(GL_LIGHTING)
        glColor3f(0.3, 0.3, 0.3)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for i in range(-10, 11):
            # X축 평행선
            glVertex3f(float(i), 0.0, -10.0)
            glVertex3f(float(i), 0.0, 10.0)
            # Z축 평행선
            glVertex3f(-10.0, 0.0, float(i))
            glVertex3f(10.0, 0.0, float(i))
        glEnd()
        glEnable(GL_LIGHTING)