from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter, QHBoxLayout, QLineEdit, QPushButton)
from PySide6.QtCore import Qt, Signal, Slot

from data.scene.stage import Stage_Controller

from .scene_tree import Scene_Tree_Widget
from .property import Property_Panel


class Outliner_Panel(QWidget):
    """검색창, 조작 버튼, 내부 트리 위젯을 포함하는 전체 래퍼 패널."""
    
    selection_changed = Signal(list)

    def __init__(self, stage: Stage_Controller, parent=None):
        super().__init__(parent)
        self.stage = stage
        self._Setup_ui()

    def _Setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search nodes...")
        self.search_bar.textChanged.connect(self._On_search_text_changed)
        layout.addWidget(self.search_bar)

        self.tree_widget = Scene_Tree_Widget(self.stage)
        self.tree_widget.selection_changed.connect(self.selection_changed.emit)
        layout.addWidget(self.tree_widget)

        toolbar_layout = QHBoxLayout()
        self.btn_add_group = QPushButton("New Group")
        self.btn_add_group.clicked.connect(self._On_add_group_clicked)
        
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._On_delete_clicked)
        
        toolbar_layout.addWidget(self.btn_add_group)
        toolbar_layout.addWidget(self.btn_delete)
        layout.addLayout(toolbar_layout)

    def _On_search_text_changed(self, text: str):
        items = self.tree_widget.findItems(
            "", Qt.MatchFlag.MatchRecursive | Qt.MatchFlag.MatchContains)
        for item in items:
            is_visible = text.lower() in item.text(0).lower()
            item.setHidden(not is_visible)

    def _On_add_group_clicked(self):
        _selected_nodes = self.tree_widget.Get_selected_nodes()
        _parent_node = _selected_nodes[0] if _selected_nodes else self.stage.root
        self.tree_widget._Request_add(None, _parent_node)

    def _On_delete_clicked(self):
        # 헬퍼 메서드를 호출하여 다중 삭제 트랜잭션 실행
        self.tree_widget._Request_delete()

    def Refresh(self):
        self.tree_widget.Refresh_ui()


class Scene_Explorer_Page(QWidget):
    """Outliner(트리)와 Inspector(속성창)를 결합하고 내부 시그널을 중재하는 씬 탐색기 래퍼 패널."""
    
    # 아웃라이너의 선택 변경 사항을 외부(뷰어 등)로 패스스루하기 위한 시그널
    selection_changed = Signal(list)
    # 인스펙터의 속성 변경 사항을 외부(뷰어 렌더링 갱신 등)로 패스스루하기 위한 시그널
    property_changed = Signal()

    def __init__(self, stage: Stage_Controller, parent=None):
        super().__init__(parent)
        self.stage = stage
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        # 페이지 자체는 사이드바 안에 꽉 차야 하므로 여백을 0으로 설정
        _layout = QVBoxLayout(self)
        _layout.setContentsMargins(0, 0, 0, 0)
        _layout.setSpacing(0)

        # 위아래 크기 조절을 위한 수직 스플리터 생성
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 1. 자식 패널 인스턴스화
        self.outliner = Outliner_Panel(self.stage)
        self.inspector = Property_Panel()

        # 2. 스플리터에 조립
        self.splitter.addWidget(self.outliner)
        self.splitter.addWidget(self.inspector)
        
        # 3. 초기 화면 분할 비율 설정 (예: 아웃라이너 40%, 인스펙터 60%)
        self.splitter.setSizes([400, 600])

        _layout.addWidget(self.splitter)

    def _connect_signals(self):
        """내부 패널 간의 데이터 흐름을 중재하고 외부로 릴레이함."""
        
        # 1. 내부 와이어링: 아웃라이너 선택 변경 -> 중재 슬롯 호출
        self.outliner.selection_changed.connect(
            self._On_outliner_selection_changed)
        
        # 2. 외부 릴레이: 인스펙터에서 값이 바뀌면 외부로 방송
        self.inspector.property_changed.connect(self.property_changed.emit)

    @Slot(list)
    def _On_outliner_selection_changed(self, nodes: list):
        """아웃라이너에서 선택된 노드 리스트를 분석하여 인스펙터를 제어함."""
        
        # [핵심 로직] 다중 선택 시 인스펙터 비활성화, 단일 선택 시에만 정보 표시
        if len(nodes) == 1:
            self.inspector.Update_info(nodes[0])
        else:
            # 0개 선택되었거나, 2개 이상 다중 선택된 경우 인스펙터를 잠금(None 주입)
            # 향후 Multi-Edit 기능을 구현한다면 이 부분을 확장하면 됨
            self.inspector.Update_info(None)

        # 외부(메인 윈도우/뷰어)로도 선택된 리스트를 그대로 전파함
        self.selection_changed.emit(nodes)

    def Set_external_selection(self, nodes: list):
        """뷰포트 등 외부에서 객체를 직접 클릭(Picking)했을 때 호출되는 API."""
        # 이 메서드를 통해 뷰어에서 선택한 것도 아웃라이너 트리와 동기화되게 만들 수 있음
        # (아웃라이너의 트리 아이템 선택 상태를 코드로 변경하는 로직이 필요하다면 추가 가능)
        self._On_outliner_selection_changed(nodes)
