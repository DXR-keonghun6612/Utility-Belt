"""Render Config 생성 다이얼로그 모듈."""
import numpy as np

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QLabel,
    QTabWidget, QWidget, QCheckBox
)

from simulation.config import Render_Config, Randomize_Range
from spatial_toolbox.scene import Controller as Stage_Controller
from spatial_toolbox.scene.node import Camera as Camera_Node, Base_Node
from spatial_toolbox.scene.node.utils import walk_nodes


class Generate_Config_Dialog(QDialog):
    """현재 씬 정보를 기반으로 6-DoF 범위를 설정하여 Render_Config를 생성하는 다이얼로그."""

    def __init__(self, stage: Stage_Controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Render Config 생성")
        self.setMinimumWidth(450)
        self.stage = stage

        self._cameras: list[Base_Node] = []
        self._groups: list[Base_Node] = []
        
        # 6-DoF UI 컨트롤 참조 저장소 (객체, 카메라)
        self._obj_controls: dict = {}
        self._cam_controls: dict = {}
        
        self._Setup_ui()
        self._Populate_nodes()

    def _Setup_ui(self) -> None:
        """다이얼로그 레이아웃 및 탭 위젯 구성."""
        _layout = QVBoxLayout(self)

        # 1. 씬 타겟 설정
        _scene_group = QGroupBox("Scene Targets")
        _scene_form = QFormLayout(_scene_group)
        
        self.cb_camera = QComboBox()
        self.cb_target = QComboBox()
        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(1, 10000); self.spin_samples.setValue(10)

        _scene_form.addRow("촬영 카메라:", self.cb_camera)
        _scene_form.addRow("대상 그룹:", self.cb_target)
        _scene_form.addRow("객체당 샘플 수:", self.spin_samples)
        _layout.addWidget(_scene_group)

        # 2. 6-DoF 랜덤화 탭 설정
        self.tabs = QTabWidget()
        
        _obj_tab, self._obj_controls = self._Create_6dof_tab()
        _cam_tab, self._cam_controls = self._Create_6dof_tab()
        
        self.tabs.addTab(_obj_tab, "객체 (Object)")
        self.tabs.addTab(_cam_tab, "카메라 (Camera)")
        
        _layout.addWidget(self.tabs)

        # 3. 하단 버튼
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        _layout.addWidget(self.button_box)

    def _Create_6dof_tab(self) -> tuple[QWidget, dict]:
        """6자유도(XYZ 위치, XYZ 회전) 입력 폼을 생성하고 컨트롤 딕셔너리를 반환함."""
        _tab = QWidget()
        _layout = QFormLayout(_tab)
        _controls = {}

        _dofs = [
            ("tx", "X 이동 (m)"), ("ty", "Y 이동 (m)"), ("tz", "Z 이동 (m)"),
            ("rx", "X 회전 (Deg)"), ("ry", "Y 회전 (Deg)"), ("rz", "Z 회전 (Deg)")
        ]

        for _key, _label in _dofs:
            _row_layout = QHBoxLayout()
            
            _chk_range = QCheckBox("범위")
            
            _spin_min = QDoubleSpinBox()
            _spin_min.setRange(-9999.0, 9999.0)
            _spin_min.setDecimals(3)
            _spin_min.setValue(0.0)

            _lbl_tilde = QLabel("~")

            _spin_max = QDoubleSpinBox()
            _spin_max.setRange(-9999.0, 9999.0)
            _spin_max.setDecimals(3)
            _spin_max.setValue(0.0)
            _spin_max.setEnabled(False) # 체크 전에는 비활성화

            # 범위 체크박스 토글 시 최대값 스핀박스 활성화 동기화
            _chk_range.toggled.connect(_spin_max.setEnabled)

            _row_layout.addWidget(_chk_range)
            _row_layout.addWidget(_spin_min)
            _row_layout.addWidget(_lbl_tilde)
            _row_layout.addWidget(_spin_max)

            _layout.addRow(_label, _row_layout)
            _controls[_key] = (_chk_range, _spin_min, _spin_max)

        return _tab, _controls

    def _Populate_nodes(self) -> None:
        """씬 트리를 순회하여 유효한 카메라 및 그룹 노드를 콤보박스에 바인딩함."""
        if not self.stage.root:
            return

        for _node in walk_nodes(self.stage.root, lambda n: True):
            if isinstance(_node, Camera_Node):
                self._cameras.append(_node)
                self.cb_camera.addItem(_node.label)
            elif _node.prim_type == "Xform" and _node is not self.stage.root:
                self._groups.append(_node)
                self.cb_target.addItem(_node.label)

        _target_idx = self.cb_target.findText("target")
        if _target_idx >= 0:
            self.cb_target.setCurrentIndex(_target_idx)

    def _Extract_range_data(self, controls: dict) -> Randomize_Range:
        """UI 컨트롤 딕셔너리에서 값들을 추출하여 Randomize_Range 객체로 변환함."""
        _kwargs = {}
        for _key, (_chk, _s_min, _s_max) in controls.items():
            _val1 = _s_min.value()
            _is_rot = _key in ('rx', 'ry', 'rz')
            
            if _is_rot:
                _val1 = np.radians(_val1)

            if _chk.isChecked():
                _val2 = _s_max.value()
                if _is_rot:
                    _val2 = np.radians(_val2)
                _kwargs[_key] = [float(_val1), float(_val2)]
            else:
                _kwargs[_key] = float(_val1)
                
        return Randomize_Range(**_kwargs)

    def Get_config(self) -> Render_Config:
        """UI 입력 상태를 반영하여 최종 Render_Config 객체를 반환함."""
        _cam_label = self.cb_camera.currentText()
        
        _obj_range = self._Extract_range_data(self._obj_controls)
        _cam_range = self._Extract_range_data(self._cam_controls)

        return Render_Config(
            camera_label=_cam_label,
            num_samples=self.spin_samples.value(),
            output_layout="per_object",
            scene_path="scene.json", 
            obj=_obj_range,
            cam=_cam_range
        )