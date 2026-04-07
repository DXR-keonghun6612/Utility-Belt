from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QApplication
from PySide6.QtCore import Slot

# 코어 데이터 매니저
from data.node.stage import Stage_Controller
from data.asset import Asset_Cache

# 분리된 UI 위젯들 임포트
from .viewer import Viewer_Panel
from .sidebar.widget import Main_Sidebar


class Main_Window(QMainWindow):
    """
    VS Code 스타일의 레이아웃 사령탑.
    [Activity/Side Bar (좌)] | [3D Viewer (우)] 구조로 배치함.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Engine Editor")
        self.resize(1280, 720)

        self.stage = Stage_Controller()
        self.asset_cache = Asset_Cache()

        self._Setup_ui()
        self._Connect_signals()

    def _Setup_ui(self):
        self.holder = QWidget()
        self.setCentralWidget(self.holder)
        
        # 여백과 간격을 0으로 설정하여 사이드바와 뷰어를 밀착시킴
        _main_layout = QHBoxLayout(self.holder)
        _main_layout.setContentsMargins(0, 0, 0, 0)
        _main_layout.setSpacing(0)

        # 2. 위젯 생성
        self.sidebar = Main_Sidebar(self.stage, self.asset_cache)
        self.viewer = Viewer_Panel(self.stage)

        # 3. 레이아웃에 배치
        _main_layout.addWidget(self.sidebar)
        _main_layout.addWidget(self.viewer)

        # 4. [핵심] 뷰어에게 모든 확장 우선순위를 부여함 (Stretch Factor)
        # 사이드바는 내용물 크기(고정)만큼만 차지하고, 뷰어는 남은 공간을 100% 점유함
        _main_layout.setStretch(0, 0) # Sidebar
        _main_layout.setStretch(1, 1) # Viewer

    def _Connect_signals(self):
        # 1. 선택 (Viewer -> Sidebar)
        self.viewer.node_selected_signal.connect(self._On_viewer_node_selected)
        # 2. 선택 (Sidebar -> Viewer)
        self.sidebar.scene_page.selection_changed.connect(self._On_sidebar_selection_changed)
        # 3. 속성 수정 -> 화면 갱신
        self.sidebar.scene_page.property_changed.connect(self.viewer.update)
        # 4. 에셋 추가 -> 씬 배치
        self.sidebar.asset_page.instantiate_requested.connect(self._On_asset_instantiated)
        # 5. 장면 로드 -> 뷰어 갱신
        self.sidebar.scene_page.scene_loaded.connect(self._On_scene_loaded)
        # 6. 뷰포트 카메라 패널 바인딩
        self.sidebar.camera_page.Bind_camera(self.viewer.camera)
        self.sidebar.camera_page.camera_changed.connect(self._On_camera_changed)
        # 7. 뷰어 마우스 조작 → 카메라 패널 UI 동기화
        self.viewer.camera_moved_signal.connect(self.sidebar.camera_page.Refresh)
    # ==========================================
    # 글로벌 중재자 슬롯 (Mediator Slots)
    # ==========================================

    @Slot(object)
    def _On_viewer_node_selected(self, node):
        """뷰어에서 픽킹된 단일 노드를 씬 페이지(리스트 요구) 규격에 맞춰 전달함."""
        _nodes = [node] if node else []
        self.sidebar.scene_page.Set_external_selection(_nodes)

    @Slot(list)
    def _On_sidebar_selection_changed(self, nodes):
        """사이드바에서 선택된 노드를 뷰어의 Selection_Controller에 강제 주입함."""
        self.viewer.selection.selected_node = nodes[0] if len(nodes) == 1 else None
        self.viewer.update()

    @Slot()
    def _On_scene_loaded(self):
        """장면 파일 로드 후 이전 에셋 캐시 및 뷰어 선택 상태를 초기화하고 화면을 갱신함."""
        self.sidebar.asset_page.Clear_assets()
        self.viewer.selection.selected_node = None
        self.viewer.update()

    @Slot()
    def _On_camera_changed(self):
        """카메라 패널에서 값 변경 시 뷰어 projection 갱신 및 리페인트."""
        self.viewer.camera.Update_projection(self.viewer.width(), self.viewer.height())
        self.viewer.update()

    @Slot(object)
    def _On_asset_instantiated(self, node):
        """에셋 브라우저에서 인스턴스화 요청된 노드를 씬에 배치하고 화면을 갱신함."""
        # 1. 아웃라이너에서 현재 선택된 노드를 부모로 삼음 (선택 없으면 root)
        _selected = self.sidebar.scene_page.outliner.tree_widget.Get_selected_nodes()
        _parent = _selected[0] if _selected else self.stage.root
        
        # 2. 씬에 노드 추가
        self.stage.Add_node(node, _parent)
        
        # 3. UI 갱신 (아웃라이너 패널의 Refresh 메서드 호출)
        self.sidebar.scene_page.outliner.Refresh()
        self.viewer.update()
