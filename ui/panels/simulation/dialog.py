import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QLabel,
    QTabWidget, QWidget, QCheckBox,
)

from spatial_toolbox.simulation import (
    Physics_Drop_Config,
    Randomize_Range,
    Sim_Config,
)
from spatial_toolbox.scene import Controller as Stage_Controller
from spatial_toolbox.scene.node import Camera as Camera_Node
from spatial_toolbox.scene.node.utils import walk_nodes


class Generate_Config_Dialog(QDialog):
    """현재 씬 정보를 기반으로 Sim_Config를 생성하는 다이얼로그."""

    def __init__(self, stage: Stage_Controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simulation Config 생성")
        self.setMinimumWidth(480)
        self.stage = stage

        self._cameras: list[Camera_Node] = []
        self._groups: list = []

        self._obj_controls: dict = {}
        self._cam_controls: dict = {}

        self._Setup_ui()
        self._Populate_nodes()

    # ==========================================
    # UI 구성
    # ==========================================

    def _Setup_ui(self) -> None:
        _layout = QVBoxLayout(self)
        _layout.setSpacing(10)

        _layout.addWidget(self._Build_scene_group())
        _layout.addWidget(self._Build_randomize_tabs())
        _layout.addWidget(self._Build_physics_group())

        _btn = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _btn.accepted.connect(self.accept)
        _btn.rejected.connect(self.reject)
        _layout.addWidget(_btn)

    def _Build_scene_group(self) -> QGroupBox:
        _group = QGroupBox("씬 설정")
        _form = QFormLayout(_group)
        _form.setSpacing(6)

        self.cb_target = QComboBox()
        self.cb_camera = QComboBox()

        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(1, 10000)
        self.spin_samples.setValue(10)

        self.cb_layout = QComboBox()
        self.cb_layout.addItems(["per_object", "flat"])

        # 시드 행 — 체크박스로 활성/비활성
        _seed_row = QHBoxLayout()
        self.chk_seed = QCheckBox("사용")
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(0, 2**31 - 1)
        self.spin_seed.setValue(1234)
        self.spin_seed.setEnabled(False)
        self.chk_seed.toggled.connect(self.spin_seed.setEnabled)
        _seed_row.addWidget(self.spin_seed)
        _seed_row.addWidget(self.chk_seed)

        _form.addRow("대상 그룹:", self.cb_target)
        _form.addRow("카메라:", self.cb_camera)
        _form.addRow("샘플 수:", self.spin_samples)
        _form.addRow("출력 구조:", self.cb_layout)
        _form.addRow("RNG 시드:", _seed_row)

        return _group

    def _Build_randomize_tabs(self) -> QTabWidget:
        _tabs = QTabWidget()

        _obj_tab, self._obj_controls = self._Build_dof_tab()
        _cam_tab, self._cam_controls = self._Build_dof_tab()

        _tabs.addTab(_obj_tab, "객체 변환")
        _tabs.addTab(_cam_tab, "카메라 변환")

        return _tabs

    def _Build_physics_group(self) -> QGroupBox:
        _group = QGroupBox("Physics Drop")
        _form = QFormLayout(_group)
        _form.setSpacing(6)

        self.chk_physics_drop = QCheckBox("사용")
        self.chk_ground_plane = QCheckBox("바닥 plane 추가")
        self.chk_ground_plane.setChecked(True)
        self.chk_collide_with_scene = QCheckBox("scene mesh와 충돌")
        self.chk_collide_with_scene.setChecked(True)

        self.spin_floor_z = QDoubleSpinBox()
        self.spin_floor_z.setRange(-9999.0, 9999.0)
        self.spin_floor_z.setDecimals(4)
        self.spin_floor_z.setValue(0.0)

        self.spin_settle_frames = QSpinBox()
        self.spin_settle_frames.setRange(1, 10000)
        self.spin_settle_frames.setValue(24)

        self.cb_collision_shape = QComboBox()
        self.cb_collision_shape.addItems(["CONVEX_HULL", "MESH", "BOX"])

        self.spin_mass = QDoubleSpinBox()
        self.spin_mass.setRange(0.001, 10000.0)
        self.spin_mass.setDecimals(4)
        self.spin_mass.setValue(1.0)

        self.spin_friction = QDoubleSpinBox()
        self.spin_friction.setRange(0.0, 1.0)
        self.spin_friction.setDecimals(4)
        self.spin_friction.setValue(0.5)

        self.spin_restitution = QDoubleSpinBox()
        self.spin_restitution.setRange(0.0, 1.0)
        self.spin_restitution.setDecimals(4)
        self.spin_restitution.setValue(0.0)

        self.spin_steps_per_second = QSpinBox()
        self.spin_steps_per_second.setRange(1, 10000)
        self.spin_steps_per_second.setValue(120)

        self.spin_solver_iterations = QSpinBox()
        self.spin_solver_iterations.setRange(1, 1000)
        self.spin_solver_iterations.setValue(20)

        self.spin_linear_damping = QDoubleSpinBox()
        self.spin_linear_damping.setRange(0.0, 1.0)
        self.spin_linear_damping.setDecimals(4)
        self.spin_linear_damping.setValue(0.04)

        self.spin_angular_damping = QDoubleSpinBox()
        self.spin_angular_damping.setRange(0.0, 1.0)
        self.spin_angular_damping.setDecimals(4)
        self.spin_angular_damping.setValue(0.1)

        _controls = [
            self.chk_ground_plane,
            self.chk_collide_with_scene,
            self.spin_floor_z,
            self.spin_settle_frames,
            self.cb_collision_shape,
            self.spin_mass,
            self.spin_friction,
            self.spin_restitution,
            self.spin_steps_per_second,
            self.spin_solver_iterations,
            self.spin_linear_damping,
            self.spin_angular_damping,
        ]
        self.chk_physics_drop.toggled.connect(
            lambda enabled: [control.setEnabled(enabled) for control in _controls]
        )
        self.chk_physics_drop.setChecked(False)

        _form.addRow("물리 드롭:", self.chk_physics_drop)
        _form.addRow("바닥 높이:", self.spin_floor_z)
        _form.addRow("정착 프레임:", self.spin_settle_frames)
        _form.addRow("충돌 shape:", self.cb_collision_shape)
        _form.addRow("질량:", self.spin_mass)
        _form.addRow("마찰:", self.spin_friction)
        _form.addRow("반발:", self.spin_restitution)
        _form.addRow("초당 스텝:", self.spin_steps_per_second)
        _form.addRow("solver 반복:", self.spin_solver_iterations)
        _form.addRow("선형 damping:", self.spin_linear_damping)
        _form.addRow("회전 damping:", self.spin_angular_damping)
        _form.addRow("", self.chk_ground_plane)
        _form.addRow("", self.chk_collide_with_scene)

        return _group

    def _Build_dof_tab(self) -> tuple[QWidget, dict]:
        """위치(m) / 회전(°) 두 그룹으로 나뉜 6-DoF 입력 탭을 생성함."""
        _tab = QWidget()
        _outer = QVBoxLayout(_tab)
        _outer.setSpacing(8)

        _controls: dict = {}

        _trans_axes = [("tx", "X"), ("ty", "Y"), ("tz", "Z")]
        _rot_axes   = [("rx", "X"), ("ry", "Y"), ("rz", "Z")]

        _trans_group = QGroupBox("위치 (m)")
        _trans_form = QFormLayout(_trans_group)
        _trans_form.setSpacing(4)
        for _key, _label in _trans_axes:
            _row, _ctrl = self._Build_range_row(is_rotation=False)
            _trans_form.addRow(_label, _row)
            _controls[_key] = _ctrl

        _rot_group = QGroupBox("회전 (°)")
        _rot_form = QFormLayout(_rot_group)
        _rot_form.setSpacing(4)
        for _key, _label in _rot_axes:
            _row, _ctrl = self._Build_range_row(is_rotation=True)
            _rot_form.addRow(_label, _row)
            _controls[_key] = _ctrl

        _outer.addWidget(_trans_group)
        _outer.addWidget(_rot_group)

        return _tab, _controls

    def _Build_range_row(self, is_rotation: bool) -> tuple[QWidget, tuple]:
        """[min] ~ [max] [□ 범위] 한 행을 생성함. 컨트롤 튜플을 함께 반환함."""
        _container = QWidget()
        _row = QHBoxLayout(_container)
        _row.setContentsMargins(0, 0, 0, 0)
        _row.setSpacing(4)

        _limit = 360.0 if is_rotation else 9999.0
        _decimals = 1 if is_rotation else 4

        _spin_min = QDoubleSpinBox()
        _spin_min.setRange(-_limit, _limit)
        _spin_min.setDecimals(_decimals)
        _spin_min.setValue(0.0)

        _lbl = QLabel("~")
        _lbl.setFixedWidth(12)

        _spin_max = QDoubleSpinBox()
        _spin_max.setRange(-_limit, _limit)
        _spin_max.setDecimals(_decimals)
        _spin_max.setValue(0.0)
        _spin_max.setEnabled(False)

        _chk = QCheckBox("범위")
        _chk.toggled.connect(_spin_max.setEnabled)

        _row.addWidget(_spin_min, 3)
        _row.addWidget(_lbl)
        _row.addWidget(_spin_max, 3)
        _row.addWidget(_chk)

        return _container, (_chk, _spin_min, _spin_max, is_rotation)

    # ==========================================
    # 씬 트리 순회 및 콤보박스 채우기
    # ==========================================

    def _Populate_nodes(self) -> None:
        if not self.stage.root:
            return

        for _node in walk_nodes(self.stage.root, lambda n: True):
            if isinstance(_node, Camera_Node):
                self._cameras.append(_node)
                self.cb_camera.addItem(_node.label)
            elif _node.prim_type == "Xform" and _node is not self.stage.root:
                self._groups.append(_node)
                self.cb_target.addItem(_node.label)

        _idx = self.cb_target.findText("target")
        if _idx >= 0:
            self.cb_target.setCurrentIndex(_idx)

    # ==========================================
    # 값 추출
    # ==========================================

    def _Extract_randomize_range(self, controls: dict) -> Randomize_Range:
        _kwargs = {}
        for _key, (_chk, _s_min, _s_max, _is_rot) in controls.items():
            _v_min = _s_min.value()
            if _is_rot:
                _v_min = np.radians(_v_min)

            if _chk.isChecked():
                _v_max = _s_max.value()
                if _is_rot:
                    _v_max = np.radians(_v_max)
                _kwargs[_key] = [float(_v_min), float(_v_max)]
            else:
                _kwargs[_key] = float(_v_min)

        return Randomize_Range(**_kwargs)

    def Get_config(self) -> Sim_Config:
        return Sim_Config(
            target_label=self.cb_target.currentText(),
            camera_labels=[self.cb_camera.currentText()],
            num_samples=self.spin_samples.value(),
            output_layout=self.cb_layout.currentText(),
            seed=self.spin_seed.value() if self.chk_seed.isChecked() else None,
            obj=self._Extract_randomize_range(self._obj_controls),
            cam=self._Extract_randomize_range(self._cam_controls),
            physics_drop=Physics_Drop_Config(
                enabled=self.chk_physics_drop.isChecked(),
                floor_z=self.spin_floor_z.value(),
                use_ground_plane=self.chk_ground_plane.isChecked(),
                settle_frames=self.spin_settle_frames.value(),
                steps_per_second=self.spin_steps_per_second.value(),
                solver_iterations=self.spin_solver_iterations.value(),
                mass=self.spin_mass.value(),
                friction=self.spin_friction.value(),
                restitution=self.spin_restitution.value(),
                linear_damping=self.spin_linear_damping.value(),
                angular_damping=self.spin_angular_damping.value(),
                collision_shape=self.cb_collision_shape.currentText(),
                collide_with_scene=self.chk_collide_with_scene.isChecked(),
            ),
        )
