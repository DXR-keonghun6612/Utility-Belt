from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Signal, Slot, Qt
# 도메인 구조에 맞게 임포트 경로 조정 가정
from asset.registry import Asset_Registry
from scene.node import Scene_Node

class Asset_Browser_Panel(QWidget):
    """에셋 라이브러리 목록을 시각화하고 씬으로의 인스턴스화 요청을 담당하는 패널임."""
    
    # 에셋이 씬에 배치되어야 할 때 (예: 뷰포트로 인스턴스화) 방출하는 시그널
    instantiate_requested = Signal(Scene_Node) 
    asset_removed = Signal(str)

    def __init__(self, asset_registry: Asset_Registry, parent=None):
        super().__init__(parent)
        self.res_manager = asset_registry
        self._init_ui()

    def _init_ui(self):
        _layout = QVBoxLayout(self)
        _layout.setContentsMargins(5, 5, 5, 5)
        
        # 1. 제어 버튼 영역
        _btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Import Asset")
        self.btn_remove = QPushButton("Remove")
        _btn_layout.addWidget(self.btn_load)
        _btn_layout.addWidget(self.btn_remove)
        _layout.addLayout(_btn_layout)

        # 2. 에셋 목록 테이블 영역
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Path"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # [UX 최적화] 읽기 전용 및 행 단위 선택 설정
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        _layout.addWidget(self.table)

        # 3. 이벤트 와이어링
        self.btn_load.clicked.connect(self._on_load_clicked)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        # 테이블의 에셋을 더블 클릭했을 때 씬에 노드 추가를 요청하도록 분리
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

    @Slot()
    def _on_load_clicked(self):
        """파일을 선택하여 리소스 매니저 메모리에 등록함."""
        _files, _ = QFileDialog.getOpenFileNames(
            self, "Import 3D Asset", "", "OBJ (*.obj)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        for f in _files:
            # TODO: 로직 레이어에서 load_asset이 Scene_Node가 아닌 Asset Data를 반환하도록 수정 권장
            _node = self.res_manager.Get(f)
            if _node:
                self._update_table(_node.label, f)
                # 여기서 바로 씬에 추가하지 않고 목록에만 등록함

    @Slot(QTableWidgetItem)
    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """목록의 에셋을 더블 클릭 시, 해당 에셋을 씬에 인스턴스화하도록 요청함."""
        _row = item.row()
        _path_item = self.table.item(_row, 1)
        if _path_item:
            _path_key = _path_item.text()
            # 매니저에서 해당 에셋 데이터를 가져와 클론(Clone) 노드를 생성하여 방출
            # (현재 로직 레이어의 구조에 맞춰 임시로 node를 가져온다고 가정)
            _node_to_instantiate = self.res_manager.Get(_path_key)
            if _node_to_instantiate:
                self.instantiate_requested.emit(_node_to_instantiate.Clone())

    @Slot()
    def _on_remove_clicked(self):
        """선택된 에셋을 라이브러리에서 제거함."""
        _selected = self.table.selectedItems()
        if not _selected: return

        _row = _selected[0].row()
        _path_item = self.table.item(_row, 1)
        if not _path_item: return
            
        _path_key = _path_item.text()

        if self.res_manager.Remove(_path_key):
            self.table.removeRow(_row)
            self.asset_removed.emit(_path_key)
            
    def _update_table(self, name: str, path: str):
        """성공적으로 로드된 정보를 UI에 반영함."""
        _row = self.table.rowCount()
        self.table.insertRow(_row)
        self.table.setItem(_row, 0, QTableWidgetItem(name))
        self.table.setItem(_row, 1, QTableWidgetItem(path))