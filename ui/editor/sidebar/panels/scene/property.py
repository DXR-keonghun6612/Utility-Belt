import numpy as np
from scipy.spatial.transform import Rotation as R
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QDoubleSpinBox, QGroupBox, QFrame
)
from PySide6.QtCore import Signal, Qt

from scene.node import Scene_Node

class Property_Panel(QWidget):
    """선택된 3D 객체의 속성을 표시하며, 회전은 Quaternion(W, X, Y, Z) 기반으로 제어함."""

    property_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node: Scene_Node | None = None
        self._Setup_ui()

    def _Setup_ui(self):
        _layout = QVBoxLayout(self)
        _layout.setContentsMargins(10, 10, 10, 10)
        _layout.setSpacing(15)
        _layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 1. 헤더 (이름 및 타입)
        self.lbl_node_name = QLabel("No Selection")
        self.lbl_node_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #E0E0E0;")
        self.lbl_node_type = QLabel("Type: None")
        self.lbl_node_type.setStyleSheet("color: #888888;")

        _layout.addWidget(self.lbl_node_name)
        _layout.addWidget(self.lbl_node_type)

        _line = QFrame()
        _line.setFrameShape(QFrame.Shape.HLine)
        _line.setStyleSheet("color: #444444;")
        _layout.addWidget(_line)

        # 2. Transform 컨트롤 그룹
        self.transform_group = QGroupBox("Transform (Quaternion)")
        self.transform_group.setStyleSheet("QGroupBox { font-weight: bold; color: #CCCCCC; }")
        _tg_layout = QVBoxLayout(self.transform_group)
        
        # Location (X, Y, Z), Rotation (W, X, Y, Z), Scale (X, Y, Z) 동적 생성
        self.loc_spins = self._Create_input_row(
            "Location",
            ['X', 'Y', 'Z'],
            ['#FF5555', '#55FF55', '#5555FF'],
            _tg_layout
        )
        self.rot_spins = self._Create_input_row(
            "Rotation",
            ['W', 'X', 'Y', 'Z'],
            ['#AAAAAA', '#FF5555', '#55FF55', '#5555FF'],
            _tg_layout,
            default_val=[1.0, 0.0, 0.0, 0.0]
        )
        self.scale_spins = self._Create_input_row(
            "Scale",
            ['X', 'Y', 'Z'],
            ['#FF5555', '#55FF55', '#5555FF'],
            _tg_layout,
            default_val=[1.0, 1.0, 1.0]
        )

        _layout.addWidget(self.transform_group)

        # self.setLayout(_layout)
        self.setEnabled(False)

    def _Create_input_row(
        self, label: str, axes: list, colors: list, parent_layout: QVBoxLayout,
        default_val: list | None = None
    ) -> list[QDoubleSpinBox]:
        """축의 개수(3개 또는 4개)에 맞춰 스핀박스를 생성하는 유연한 헬퍼 함수."""
        if default_val is None:
            default_val = [0.0] * len(axes)

        _row = QHBoxLayout()
        _lbl = QLabel(label)
        _lbl.setFixedWidth(60)
        _row.addWidget(_lbl)

        _spins = []
        for i, (_axis, _color) in enumerate(zip(axes, colors)):
            _spin = QDoubleSpinBox()
            _spin.setRange(-99999.0, 99999.0)
            _spin.setDecimals(4) # 쿼터니언 정밀도를 위해 소수점 4자리로 증가
            _spin.setSingleStep(0.05)
            _spin.setValue(default_val[i])
            # 축 식별을 위한 언더바 색상
            _spin.setStyleSheet(f"QDoubleSpinBox {{ border-bottom: 2px solid {_color}; }}")
            _spin.valueChanged.connect(self._On_value_edited)
            
            _row.addWidget(_spin)
            _spins.append(_spin)
            
        parent_layout.addLayout(_row)
        return _spins

    # ==========================================
    # 데이터 바인딩 (UI 동기화)
    # ==========================================

    def Update_info(self, node: Scene_Node | None):
        self.current_node = node
        if not node:
            self.lbl_node_name.setText("No Selection")
            self.lbl_node_type.setText("Type: None")
            self.setEnabled(False)
            return

        self.setEnabled(True)
        self.lbl_node_name.setText(node.label)
        self.lbl_node_type.setText(f"Type: {node.prim_type}")

        # 행렬 -> T, R(Quat), S 분해
        _loc, _quat, _scale = self._TRS_from(node.local_matrix)

        self._Block_spin_signals(True)
        
        for i in range(3):
            self.loc_spins[i].setValue(_loc[i])
            self.scale_spins[i].setValue(_scale[i])
        for i in range(4):
            self.rot_spins[i].setValue(_quat[i])
            
        self._Block_spin_signals(False)

    def _Block_spin_signals(self, block: bool):
        for _spins in [self.loc_spins, self.rot_spins, self.scale_spins]:
            for _spin in _spins:
                _spin.blockSignals(block)

    def _On_value_edited(self):
        """사용자 입력 시 노드 행렬 갱신."""
        if not self.current_node: return

        _loc = [s.value() for s in self.loc_spins]
        _quat = [s.value() for s in self.rot_spins]
        _scale = [s.value() for s in self.scale_spins]

        _new_matrix = self._Matrix_from(_loc, _quat, _scale)
        self.current_node.local_matrix = _new_matrix
        self.property_changed.emit()

    # ==========================================
    # 수학 연산 (Scipy 최신 API 적용)
    # ==========================================

    def _TRS_from(self, matrix: np.ndarray) -> tuple[list, list, list]:
        """4x4 행렬에서 Location(3), Quaternion(4), Scale(3)을 추출함."""
        # 1. Location
        _loc = matrix[0:3, 3].tolist()
        
        # 2. Scale
        _sx = np.linalg.norm(matrix[0:3, 0])
        _sy = np.linalg.norm(matrix[0:3, 1])
        _sz = np.linalg.norm(matrix[0:3, 2])
        _scale = [_sx, _sy, _sz]
        
        # 3. 순수 회전 행렬 (스케일 제거)
        _m = np.eye(3)
        _m[:, 0] = matrix[0:3, 0] / _sx if _sx > 1e-6 else [1, 0, 0]
        _m[:, 1] = matrix[0:3, 1] / _sy if _sy > 1e-6 else [0, 1, 0]
        _m[:, 2] = matrix[0:3, 2] / _sz if _sz > 1e-6 else [0, 0, 1]

        # 4. Scipy Rotation (scalar_first=True 로 WXYZ 규격 다이렉트 매핑)
        try:
            _rot = R.from_matrix(_m)
            # as_quat()에 옵션을 주어 [W, X, Y, Z] 형태로 바로 뽑아냄
            _quat = _rot.as_quat(scalar_first=True).tolist() 
        except ValueError:
            # 특이점 붕괴 시 안전한 기본 쿼터니언 반환
            _quat = [1.0, 0.0, 0.0, 0.0] 

        return _loc, _quat, _scale

    def _Matrix_from(self, loc: list, quat: list, scale: list) -> np.ndarray:
        """Location, Quaternion(WXYZ), Scale을 조합하여 새로운 4x4 행렬을 생성함."""
        
        # 1. Scipy Quaternion to Matrix
        try:
            # 입력값 quat이 [W, X, Y, Z]이므로 scalar_first=True 옵션으로 그대로 밀어넣음
            _rot = R.from_quat(quat, scalar_first=True) 
            _rot_mat = _rot.as_matrix()
        except ValueError:
            # 사용자 입력 정규화 실패 시 기본 단위 행렬로 방어
            _rot_mat = np.eye(3)

        # 2. T * R * S 조합
        _mat = np.eye(4, dtype=np.float32)
        
        # 회전 행렬에 스케일 곱하기
        _mat[0:3, 0] = _rot_mat[:, 0] * scale[0]
        _mat[0:3, 1] = _rot_mat[:, 1] * scale[1]
        _mat[0:3, 2] = _rot_mat[:, 2] * scale[2]
        
        # 평행 이동
        _mat[0:3, 3] = loc
        
        return _mat