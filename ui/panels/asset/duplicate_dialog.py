from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QStackedLayout,
    QWidget
)
from PySide6.QtCore import Slot

from spatial_toolbox.scene import ASSET_CACHE
from spatial_toolbox.scene.asset import Mesh as Mesh_Asset
from spatial_toolbox.scene.asset.utils import Is_exact_match, Calculate_match_rate

class Duplicate_Dialog(QDialog):
    """에셋 중복 검출 파라미터를 설정하고 결과를 표시하는 다이얼로그."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find Duplicate Assets")
        self.resize(720, 500)
        self.setMinimumSize(520, 380)

        self._root_layout = QVBoxLayout(self)
        self._stack = QStackedLayout()
        self._root_layout.addLayout(self._stack)

        self._Setup_config_page()
        self._Setup_result_page()
        self._stack.setCurrentIndex(0)

    def _Setup_config_page(self) -> None:
        _page = QWidget()
        _layout = QVBoxLayout(_page)

        _group = QGroupBox("Detection Parameters")
        _form = QFormLayout(_group)

        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setDecimals(6); self.spin_tol.setRange(0.0, 1.0)
        self.spin_tol.setValue(1e-5); self.spin_tol.setSingleStep(1e-5)
        _form.addRow("Exact Match Tolerance:", self.spin_tol)

        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(100, 50000); self.spin_samples.setValue(5000)
        self.spin_samples.setSingleStep(500)
        _form.addRow("Surface Samples:", self.spin_samples)

        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setDecimals(4); self.spin_threshold.setRange(0.0001, 1.0)
        self.spin_threshold.setValue(0.01); self.spin_threshold.setSingleStep(0.005)
        _form.addRow("Distance Threshold (m):", self.spin_threshold)

        _layout.addWidget(_group)
        _layout.addStretch()

        _btn_layout = QHBoxLayout()
        _btn_layout.addStretch()
        self.btn_run = QPushButton("Run")
        self.btn_run.setFixedWidth(120)
        self.btn_run.clicked.connect(self._on_run_clicked)
        _btn_layout.addWidget(self.btn_run)
        
        _layout.addLayout(_btn_layout)
        self._stack.addWidget(_page)

    def _Setup_result_page(self) -> None:
        _page = QWidget()
        _layout = QVBoxLayout(_page)

        self.result_label = QLabel()
        _layout.addWidget(self.result_label)

        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["Name", "Source", "Score"])
        self.result_tree.setColumnCount(3)
        self.result_tree.setAlternatingRowColors(True)
        _header = self.result_tree.header()
        _header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        _header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        _header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        _header.setStretchLastSection(False)
        _header.setMinimumSectionSize(60)
        self.result_tree.setColumnWidth(0, 160)
        self.result_tree.setColumnWidth(1, 460)
        _layout.addWidget(self.result_tree)

        _btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.setFixedWidth(80)
        self.btn_back.clicked.connect(self._on_back_clicked)

        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)

        _btn_layout.addWidget(self.btn_back)
        _btn_layout.addStretch()
        _btn_layout.addWidget(self.btn_close)
        
        _layout.addLayout(_btn_layout)
        self._stack.addWidget(_page)

    @Slot()
    def _on_run_clicked(self) -> None:
        _tol = self.spin_tol.value()
        _samples = self.spin_samples.value()
        _threshold = self.spin_threshold.value()

        _groups = self._Find_exact_groups(_tol)
        self.result_tree.clear()

        if not _groups:
            self.result_label.setText("No duplicates found.")
        else:
            self.result_label.setText(f"{len(_groups)} duplicate group(s) detected.")
            for _idx, _group in enumerate(_groups, 1):
                _ref = _group[0]
                _parent = QTreeWidgetItem([f"Group {_idx}  ({len(_group)} assets)", "", ""])
                _ref_item = QTreeWidgetItem(_parent, [_ref.label, _ref.source_path or "", "ref"])
                _ref_item.setToolTip(1, _ref.source_path or "")

                for _asset in _group[1:]:
                    _rate = 0.0
                    if _ref.geometry is not None and _asset.geometry is not None:
                        _rate = Calculate_match_rate(
                            _ref.geometry, _asset.geometry,
                            num_samples=_samples, threshold=_threshold
                        )
                    _item = QTreeWidgetItem(_parent, [_asset.label, _asset.source_path or "", f"{_rate:.2%}"])
                    _item.setToolTip(1, _asset.source_path or "")
                self.result_tree.addTopLevelItem(_parent)
            self.result_tree.expandAll()

        self._stack.setCurrentIndex(1)

    @Slot()
    def _on_back_clicked(self) -> None:
        self._stack.setCurrentIndex(0)

    def _Find_exact_groups(self, tol: float) -> list[list[Mesh_Asset]]:
        _meshes = ASSET_CACHE.Get_by_type(Mesh_Asset)
        _visited: set[int] = set()
        _groups: list[list[Mesh_Asset]] = []

        for i, _a in enumerate(_meshes):
            _idx_a = id(_a)
            if _idx_a in _visited:
                continue

            _group = [_a]
            _visited.add(_idx_a)

            for j in range(i + 1, len(_meshes)):
                _b = _meshes[j]
                _idx_b = id(_b)
                if _idx_b in _visited: continue

                if (_a.geometry is not None and _b.geometry is not None
                        and Is_exact_match(_a.geometry, _b.geometry, tol)):
                    _group.append(_b)
                    _visited.add(_idx_b)

            if len(_group) > 1:
                _groups.append(_group)

        return _groups