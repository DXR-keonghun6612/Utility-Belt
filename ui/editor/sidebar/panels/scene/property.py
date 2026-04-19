import numpy as np
from scipy.spatial.transform import Rotation as R
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QGroupBox, QFrame
)
from PySide6.QtCore import Qt

from spatial_toolbox.scene.node import Base_Node, Camera as Camera_Node
from ui.style import (
    SPIN_BOX, Spin_box_accented, Axis_label, LABEL,
    HEADER, SUB_HEADER, GROUP_BOX, SEPARATOR, AXIS_COLORS, AXIS_COLORS_WXYZ
)
from ui.core.base_panel import Base_Panel

class Property_Panel(Base_Panel):
    """선택된 3D 객체의 속성을 표시하며, 회전은 Quaternion(W, X, Y, Z) 기반으로 제어함."""

    def __init__(self, parent: QWidget | None = None):
        self.current_node: Base_Node | None = None
        super().__init__(parent)

    def _setup_ui(self) -> None:
        _layout = QVBoxLayout(self)
        _layout.setContentsMargins(10, 10, 10, 10)
        _layout.setSpacing(12)
        _layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 1. 헤더
        self.lbl_node_name = QLabel("No Selection")
        self.lbl_node_name.setStyleSheet(HEADER)
        self.lbl_node_type = QLabel("Type: None")
        self.lbl_node_type.setStyleSheet(SUB_HEADER)

        _layout.addWidget(self.lbl_node_name)
        _layout.addWidget(self.lbl_node_type)

        _line = QFrame()
        _line.setFrameShape(QFrame.Shape.HLine)
        _line.setStyleSheet(SEPARATOR)
        _layout.addWidget(_line)

        # 2. Transform 그룹
        self.transform_group = QGroupBox("Transform")
        self.transform_group.setStyleSheet(GROUP_BOX)
        _tg_layout = QVBoxLayout(self.transform_group)
        _tg_layout.setSpacing(6)

        self.loc_spins = self._Create_input_row(
            "Location", ['X', 'Y', 'Z'], AXIS_COLORS,
            _tg_layout, decimals=3, step=0.1
        )
        self.rot_spins = self._Create_input_row(
            "Rotation", ['W', 'X', 'Y', 'Z'], AXIS_COLORS_WXYZ,
            _tg_layout, default_val=[1.0, 0.0, 0.0, 0.0],
            decimals=4, step=0.01
        )
        self.scale_spins = self._Create_input_row(
            "Scale", ['X', 'Y', 'Z'], AXIS_COLORS,
            _tg_layout, default_val=[1.0, 1.0, 1.0],
            decimals=3, step=0.1
        )

        _layout.addWidget(self.transform_group)

        # 3. Camera Intrinsic 그룹 (Camera 노드 전용) — K 모델
        self.camera_group = QGroupBox("Camera Intrinsic (K model)")
        self.camera_group.setStyleSheet(GROUP_BOX)
        _cg_layout = QVBoxLayout(self.camera_group)
        _cg_layout.setSpacing(6)

        # 해상도
        self.res_w_spin = self._Create_single_row(
            "Width (px)", 1.0, 16384.0, 1920.0, 1.0, 0, _cg_layout)
        self.res_h_spin = self._Create_single_row(
            "Height (px)", 1.0, 16384.0, 1080.0, 1.0, 0, _cg_layout)

        # 초점거리
        self.fx_spin = self._Create_single_row(
            "fx", 1.0, 100000.0, 1000.0, 1.0, 3, _cg_layout)
        self.fy_spin = self._Create_single_row(
            "fy", 1.0, 100000.0, 1000.0, 1.0, 3, _cg_layout)

        # 주점
        self.cx_spin = self._Create_single_row(
            "cx", 0.0, 16384.0, 960.0, 1.0, 3, _cg_layout)
        self.cy_spin = self._Create_single_row(
            "cy", 0.0, 16384.0, 540.0, 1.0, 3, _cg_layout)

        # 클리핑
        self.near_spin = self._Create_single_row(
            "Near Clip", 0.001, 1000.0, 0.1, 0.01, 3, _cg_layout)
        self.far_spin = self._Create_single_row(
            "Far Clip", 1.0, 100000.0, 1000.0, 10.0, 1, _cg_layout)

        # 산출 FOV (read-only)
        self.lbl_fov_x = QLabel("FOV X: —")
        self.lbl_fov_x.setStyleSheet(LABEL)
        _cg_layout.addWidget(self.lbl_fov_x)

        self.lbl_fov_y = QLabel("FOV Y: —")
        self.lbl_fov_y.setStyleSheet(LABEL)
        _cg_layout.addWidget(self.lbl_fov_y)

        self.camera_group.setVisible(False)
        _layout.addWidget(self.camera_group)

        self.setEnabled(False)

    # ==========================================
    # 위젯 생성 헬퍼
    # ==========================================

    def _Create_input_row(
        self, label: str, axes: list[str], colors: list[str],
        parent_layout: QVBoxLayout,
        default_val: list[float] | None = None,
        decimals: int = 3, step: float = 0.1
    ) -> list[QDoubleSpinBox]:
        """축별 라벨 + 스핀박스 행을 생성함. decimals/step을 행 단위로 차등 적용."""
        if default_val is None:
            default_val = [0.0] * len(axes)

        _row = QHBoxLayout()
        _row.setSpacing(4)

        _lbl = QLabel(label)
        _lbl.setFixedWidth(65)
        _lbl.setStyleSheet(LABEL)
        _row.addWidget(_lbl)

        _spins: list[QDoubleSpinBox] = []
        for i, (_axis, _color) in enumerate(zip(axes, colors)):
            _axis_lbl = QLabel(_axis)
            _axis_lbl.setStyleSheet(Axis_label(_color))
            _axis_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _row.addWidget(_axis_lbl)

            _spin = QDoubleSpinBox()
            _spin.setRange(-99999.0, 99999.0)
            _spin.setDecimals(decimals)
            _spin.setSingleStep(step)
            _spin.setValue(default_val[i])
            _spin.setStyleSheet(Spin_box_accented(_color))
            _spin.valueChanged.connect(self._On_value_edited)

            _row.addWidget(_spin)
            _spins.append(_spin)

        parent_layout.addLayout(_row)
        return _spins

    def _Create_single_row(
        self, label: str, min_val: float, max_val: float,
        default: float, step: float, decimals: int,
        parent_layout: QVBoxLayout
    ) -> QDoubleSpinBox:
        """단일 파라미터용 라벨 + 스핀박스 행을 생성함."""
        _row = QHBoxLayout()
        _row.setSpacing(4)

        _lbl = QLabel(label)
        _lbl.setFixedWidth(80)
        _lbl.setStyleSheet(LABEL)
        _row.addWidget(_lbl)

        _spin = QDoubleSpinBox()
        _spin.setRange(min_val, max_val)
        _spin.setDecimals(decimals)
        _spin.setSingleStep(step)
        _spin.setValue(default)
        _spin.setStyleSheet(SPIN_BOX)
        _spin.valueChanged.connect(self._On_camera_value_edited)
        _row.addWidget(_spin)

        parent_layout.addLayout(_row)
        return _spin

    # ==========================================
    # 데이터 바인딩
    # ==========================================

    def Update_info(self, node: Base_Node | None) -> None:
        self.current_node = node
        if not node:
            self.lbl_node_name.setText("No Selection")
            self.lbl_node_type.setText("Type: None")
            self.camera_group.setVisible(False)
            self.setEnabled(False)
            return

        self.setEnabled(True)
        self.lbl_node_name.setText(node.label)
        self.lbl_node_type.setText(f"Type: {node.prim_type}")

        _loc, _quat, _scale = self._TRS_from(node.local_matrix)

        self._Block_spin_signals(True)

        for i in range(3):
            self.loc_spins[i].setValue(_loc[i])
            self.scale_spins[i].setValue(_scale[i])
        for i in range(4):
            self.rot_spins[i].setValue(_quat[i])

        # Camera 노드일 때 intrinsic 패널 표시
        _is_camera = isinstance(node, Camera_Node) and node.intrinsic is not None
        self.camera_group.setVisible(_is_camera)
        if _is_camera:
            _intr = node.intrinsic
            self.res_w_spin.setValue(float(_intr.width))
            self.res_h_spin.setValue(float(_intr.height))
            self.fx_spin.setValue(_intr.fx)
            self.fy_spin.setValue(_intr.fy)
            self.cx_spin.setValue(_intr.cx)
            self.cy_spin.setValue(_intr.cy)
            self.near_spin.setValue(_intr.near_clip)
            self.far_spin.setValue(_intr.far_clip)
            self._Refresh_fov_labels(_intr)

        self._Block_spin_signals(False)

    def _Block_spin_signals(self, block: bool) -> None:
        for _spins in [self.loc_spins, self.rot_spins, self.scale_spins]:
            for _spin in _spins:
                _spin.blockSignals(block)
        for _spin in [self.res_w_spin, self.res_h_spin,
                      self.fx_spin, self.fy_spin,
                      self.cx_spin, self.cy_spin,
                      self.near_spin, self.far_spin]:
            _spin.blockSignals(block)

    def _On_camera_value_edited(self) -> None:
        """카메라 intrinsic 스핀박스 값 변경 시 노드에 반영하고 fov 라벨을 갱신."""
        if not isinstance(self.current_node, Camera_Node) or self.current_node.intrinsic is None:
            return
        _intr = self.current_node.intrinsic
        _intr.width = int(self.res_w_spin.value())
        _intr.height = int(self.res_h_spin.value())
        _intr.fx = self.fx_spin.value()
        _intr.fy = self.fy_spin.value()
        _intr.cx = self.cx_spin.value()
        _intr.cy = self.cy_spin.value()
        _intr.near_clip = self.near_spin.value()
        _intr.far_clip = self.far_spin.value()
        self._Refresh_fov_labels(_intr)
        self.property_changed.emit()

    def _Refresh_fov_labels(self, intrinsic) -> None:
        """K로부터 산출된 fov_x/fov_y를 라벨에 표시함."""
        self.lbl_fov_x.setText(f"FOV X: {intrinsic.fov_x:.2f}°")
        self.lbl_fov_y.setText(f"FOV Y: {intrinsic.fov_y:.2f}°")

    def _On_value_edited(self) -> None:
        """Transform 스핀박스 값 변경 시 노드 행렬 갱신."""
        if not self.current_node:
            return

        _loc = [s.value() for s in self.loc_spins]
        _quat = [s.value() for s in self.rot_spins]
        _scale = [s.value() for s in self.scale_spins]

        self.current_node.local_matrix = self._Matrix_from(_loc, _quat, _scale)
        self.property_changed.emit()

    # ==========================================
    # 수학 연산
    # ==========================================

    def _TRS_from(self, matrix: np.ndarray) -> tuple[list, list, list]:
        """4x4 행렬에서 Location(3), Quaternion(4), Scale(3)을 추출함."""
        _slice_xyz = slice(0, 3)
        _loc = matrix[_slice_xyz, 3].tolist()

        _sx = np.linalg.norm(matrix[_slice_xyz, 0])
        _sy = np.linalg.norm(matrix[_slice_xyz, 1])
        _sz = np.linalg.norm(matrix[_slice_xyz, 2])
        _scale = [_sx, _sy, _sz]

        _m = np.eye(3)
        _m[:, 0] = matrix[_slice_xyz, 0] / _sx if _sx > 1e-6 else [1, 0, 0]
        _m[:, 1] = matrix[_slice_xyz, 1] / _sy if _sy > 1e-6 else [0, 1, 0]
        _m[:, 2] = matrix[_slice_xyz, 2] / _sz if _sz > 1e-6 else [0, 0, 1]

        try:
            _rot = R.from_matrix(_m)
            _quat = _rot.as_quat(scalar_first=True).tolist()
        except ValueError:
            _quat = [1.0, 0.0, 0.0, 0.0]

        return _loc, _quat, _scale

    def _Matrix_from(self, loc: list, quat: list, scale: list) -> np.ndarray:
        """Location, Quaternion(WXYZ), Scale을 조합하여 4x4 행렬을 생성함."""
        try:
            _rot = R.from_quat(quat, scalar_first=True)
            _rot_mat = _rot.as_matrix()
        except ValueError:
            _rot_mat = np.eye(3)

        _mat = np.eye(4, dtype=np.float32)

        _slice_xyz = slice(0, 3)
        _mat[_slice_xyz, 0] = _rot_mat[:, 0] * scale[0]
        _mat[_slice_xyz, 1] = _rot_mat[:, 1] * scale[1]
        _mat[_slice_xyz, 2] = _rot_mat[:, 2] * scale[2]
        _mat[_slice_xyz, 3] = loc

        return _mat
3] = loc

        return _mat
