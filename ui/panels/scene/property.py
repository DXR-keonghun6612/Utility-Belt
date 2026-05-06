import numpy as np
from scipy.spatial.transform import Rotation as R
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QGroupBox, QFrame
)
from PySide6.QtCore import Qt

from spatial_toolbox.scene import Controller as Stage_Controller
from spatial_toolbox.scene.node import Base_Node, Camera as Camera_Node
from ui.style import (
    SPIN_BOX, Spin_box_accented, Axis_label, LABEL,
    HEADER, SUB_HEADER, GROUP_BOX, SEPARATOR, AXIS_COLORS, AXIS_COLORS_WXYZ
)
from ui.panels._base import Base_Panel

class Property_Panel(Base_Panel):
    """선택된 3D 객체의 속성을 표시하며, 회전은 Quaternion(W, X, Y, Z) 기반으로 제어함.

    루트(Stage) 노드 선택 시에는 Transform 대신 stage 단위 편집 UI를 노출함.
    """

    def __init__(self, stage: Stage_Controller, parent: QWidget | None = None):
        self.stage = stage
        self.current_node: Base_Node | None = None
        self._writing = False
        super().__init__(parent) # Base_Panel이 self.bus를 주입함

    def _setup_ui(self) -> None:
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(12)

        self.lbl_node_name = QLabel("No Selection")
        self.lbl_node_name.setStyleSheet(HEADER)
        self.lbl_node_type = QLabel("Type: None")
        self.lbl_node_type.setStyleSheet(SUB_HEADER)

        self.main_layout.addWidget(self.lbl_node_name)
        self.main_layout.addWidget(self.lbl_node_type)

        _line = QFrame()
        _line.setFrameShape(QFrame.Shape.HLine)
        _line.setStyleSheet(SEPARATOR)
        self.main_layout.addWidget(_line)

        self.transform_group = QGroupBox("Transform")
        self.transform_group.setStyleSheet(GROUP_BOX)
        _tg_layout = QVBoxLayout(self.transform_group)

        self.loc_spins = self._Create_input_row("Location", ['X', 'Y', 'Z'], AXIS_COLORS, _tg_layout, dec=3, step=0.1)
        self.rot_spins = self._Create_input_row("Rotation", ['W', 'X', 'Y', 'Z'], AXIS_COLORS_WXYZ, _tg_layout, default=[1,0,0,0], dec=4, step=0.01)
        self.scale_spins = self._Create_input_row("Scale", ['X', 'Y', 'Z'], AXIS_COLORS, _tg_layout, default=[1,1,1], dec=3, step=0.1)

        self.main_layout.addWidget(self.transform_group)

        # Stage 루트 전용 편집 그룹 (루트 선택 시에만 노출)
        self.stage_group = QGroupBox("Stage")
        self.stage_group.setStyleSheet(GROUP_BOX)
        _sg_layout = QVBoxLayout(self.stage_group)

        _unit_row = QHBoxLayout(); _unit_row.setSpacing(4)
        _unit_lbl = QLabel("Unit Length (m)")
        _unit_lbl.setFixedWidth(110); _unit_lbl.setStyleSheet(LABEL)
        _unit_row.addWidget(_unit_lbl)

        self.unit_length_spin = QDoubleSpinBox()
        self.unit_length_spin.setRange(1e-6, 1e6)
        self.unit_length_spin.setDecimals(6)
        self.unit_length_spin.setSingleStep(0.001)
        self.unit_length_spin.setValue(1.0)
        self.unit_length_spin.setStyleSheet(SPIN_BOX)
        self.unit_length_spin.valueChanged.connect(self._On_unit_length_edited)
        _unit_row.addWidget(self.unit_length_spin)
        _sg_layout.addLayout(_unit_row)

        self.stage_group.setVisible(False)
        self.main_layout.addWidget(self.stage_group)

        self.camera_group = QGroupBox("Camera Intrinsic (K model)")
        self.camera_group.setStyleSheet(GROUP_BOX)
        _cg_layout = QVBoxLayout(self.camera_group)

        self.res_w_spin = self._Create_single_row("Width (px)", 1, 16384, 1920, 1, 0, _cg_layout)
        self.res_h_spin = self._Create_single_row("Height (px)", 1, 16384, 1080, 1, 0, _cg_layout)
        self.fx_spin = self._Create_single_row("fx", 1, 100000, 1000, 1, 3, _cg_layout)
        self.fy_spin = self._Create_single_row("fy", 1, 100000, 1000, 1, 3, _cg_layout)
        self.cx_spin = self._Create_single_row("cx", 0, 16384, 960, 1, 3, _cg_layout)
        self.cy_spin = self._Create_single_row("cy", 0, 16384, 540, 1, 3, _cg_layout)
        self.near_spin = self._Create_single_row("Near Clip (m)", 0.001, 1000, 0.1, 0.01, 3, _cg_layout)
        self.far_spin = self._Create_single_row("Far Clip (m)", 1, 100000, 1000, 10, 1, _cg_layout)

        self.lbl_fov_x = QLabel("FOV X: —"); self.lbl_fov_x.setStyleSheet(LABEL); _cg_layout.addWidget(self.lbl_fov_x)
        self.lbl_fov_y = QLabel("FOV Y: —"); self.lbl_fov_y.setStyleSheet(LABEL); _cg_layout.addWidget(self.lbl_fov_y)

        self.camera_group.setVisible(False)
        self.main_layout.addWidget(self.camera_group)
        self.setEnabled(False)

    def _Create_input_row(self, label, axes, colors, layout, default=None, dec=3, step=0.1):
        _row = QHBoxLayout(); _row.setSpacing(4)
        _lbl = QLabel(label); _lbl.setFixedWidth(65); _lbl.setStyleSheet(LABEL); _row.addWidget(_lbl)
        _dft = default or [0.0]*len(axes)
        _spins = []
        for i, (_ax, _col) in enumerate(zip(axes, colors)):
            _albl = QLabel(_ax); _albl.setStyleSheet(Axis_label(_col)); _albl.setAlignment(Qt.AlignmentFlag.AlignCenter); _row.addWidget(_albl)
            _s = QDoubleSpinBox(); _s.setRange(-99999, 99999); _s.setDecimals(dec); _s.setSingleStep(step)
            _s.setValue(_dft[i]); _s.setStyleSheet(Spin_box_accented(_col)); _s.valueChanged.connect(self._On_value_edited)
            _row.addWidget(_s); _spins.append(_s)
        layout.addLayout(_row)
        return _spins

    def _Create_single_row(self, label, min_v, max_v, dft, step, dec, layout):
        _row = QHBoxLayout(); _row.setSpacing(4)
        _lbl = QLabel(label); _lbl.setFixedWidth(80); _lbl.setStyleSheet(LABEL); _row.addWidget(_lbl)
        _s = QDoubleSpinBox(); _s.setRange(min_v, max_v); _s.setDecimals(dec); _s.setSingleStep(step)
        _s.setValue(dft); _s.setStyleSheet(SPIN_BOX); _s.valueChanged.connect(self._On_camera_value_edited)
        _row.addWidget(_s); layout.addLayout(_row)
        return _s

    def Update_info(self, node: Base_Node | None):
        if self._writing:
            return
        _same_node = node is self.current_node
        self.current_node = node
        if not node:
            self.lbl_node_name.setText("No Selection"); self.lbl_node_type.setText("Type: None")
            self.transform_group.setVisible(True)
            self.camera_group.setVisible(False)
            self.stage_group.setVisible(False)
            self.setEnabled(False)
            return

        self.setEnabled(True)
        self.lbl_node_name.setText(node.label)
        self.lbl_node_type.setText(f"Type: {node.prim_type}")

        # 루트(Stage) 노드는 Transform 대신 stage 단위 편집을 노출
        _is_root = node is self.stage.root
        self.transform_group.setVisible(not _is_root)
        self.stage_group.setVisible(_is_root)
        if _is_root:
            self.camera_group.setVisible(False)
            self._Block_spin_signals(True)
            self.unit_length_spin.setValue(float(self.stage.unit_length))
            self._Block_spin_signals(False)
            return

        _loc, _quat = self._LR_from(node.local_rigid)
        _scale = node.scale.tolist()
        self._Block_spin_signals(True)

        for i in range(3):
            if not _same_node or not self.loc_spins[i].lineEdit().isModified():
                self.loc_spins[i].setValue(_loc[i])
            if not _same_node or not self.scale_spins[i].lineEdit().isModified():
                self.scale_spins[i].setValue(_scale[i])
        for i in range(4):
            if not _same_node or not self.rot_spins[i].lineEdit().isModified():
                self.rot_spins[i].setValue(_quat[i])

        _is_cam = isinstance(node, Camera_Node) and node.intrinsic is not None
        self.camera_group.setVisible(_is_cam)
        if _is_cam:
            _in = node.intrinsic
            self.res_w_spin.setValue(float(_in.width)); self.res_h_spin.setValue(float(_in.height))
            self.fx_spin.setValue(_in.fx); self.fy_spin.setValue(_in.fy)
            self.cx_spin.setValue(_in.cx); self.cy_spin.setValue(_in.cy)
            self.near_spin.setValue(_in.near_clip); self.far_spin.setValue(_in.far_clip)
            self._Refresh_fov_labels(_in)

        self._Block_spin_signals(False)

    def _Block_spin_signals(self, block: bool):
        for _spins in [self.loc_spins, self.rot_spins, self.scale_spins]:
            for _s in _spins: _s.blockSignals(block)
        for _s in [self.res_w_spin, self.res_h_spin, self.fx_spin, self.fy_spin, self.cx_spin, self.cy_spin, self.near_spin, self.far_spin, self.unit_length_spin]:
            _s.blockSignals(block)

    def _LR_from(self, matrix: np.ndarray) -> tuple[list, list]:
        """rigid 행렬에서 Location과 Quaternion(WXYZ)을 분해함."""
        _loc = matrix[:3, 3].tolist()
        try:
            _r = R.from_matrix(matrix[:3, :3]).as_quat() # SciPy 디폴트: XYZW
            _quat = [_r[3], _r[0], _r[1], _r[2]] # WXYZ로 변환
            # q와 -q는 같은 회전이므로 표시 부호를 고정해 UI 점프를 막음.
            if _quat[0] < 0:
                _quat = [-_v for _v in _quat]
        except ValueError:
            _quat = [1.0, 0.0, 0.0, 0.0]
        return _loc, _quat

    def _On_value_edited(self):
        if not self.current_node: return
        _l = [s.value() for s in self.loc_spins]
        _q = [s.value() for s in self.rot_spins] # UI는 WXYZ
        _s = [s.value() for s in self.scale_spins]

        try:
            _rot = R.from_quat([_q[1], _q[2], _q[3], _q[0]]).as_matrix() # XYZW로 복구하여 연산
        except ValueError:
            _rot = np.eye(3)

        _mat = np.eye(4, dtype=np.float32)
        _mat[:3, :3] = _rot
        _mat[:3, 3] = _l

        self.current_node.local_rigid = _mat
        self.current_node.scale = np.array(_s, dtype=np.float32)
        self._writing = True
        self.bus.property_changed.emit()
        self._writing = False

    def _On_camera_value_edited(self):
        if not isinstance(self.current_node, Camera_Node) or not self.current_node.intrinsic: return
        _in = self.current_node.intrinsic
        _in.width = int(self.res_w_spin.value()); _in.height = int(self.res_h_spin.value())
        _in.fx = self.fx_spin.value(); _in.fy = self.fy_spin.value()
        _in.cx = self.cx_spin.value(); _in.cy = self.cy_spin.value()
        _in.near_clip = self.near_spin.value(); _in.far_clip = self.far_spin.value()
        self._Refresh_fov_labels(_in)
        self._writing = True
        self.bus.property_changed.emit()
        self._writing = False

    def _On_unit_length_edited(self):
        """Stage 단위 편집: Controller setter가 하위 노드의 unit_scale 재계산을 트리거함."""
        self.stage.unit_length = self.unit_length_spin.value()
        self._writing = True
        self.bus.property_changed.emit()
        self._writing = False

    def _Refresh_fov_labels(self, intrinsic):
        self.lbl_fov_x.setText(f"FOV X: {intrinsic.fov_x:.2f}°")
        self.lbl_fov_y.setText(f"FOV Y: {intrinsic.fov_y:.2f}°")
