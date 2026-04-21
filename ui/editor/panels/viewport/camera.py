"""Orbit Camera 파라미터를 실시간 편집하는 뷰포트 카메라 컨트롤 패널."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QGroupBox, QPushButton
)
from PySide6.QtCore import Qt

from viewport.view import Orbit_Camera
from ui.style import (
    SPIN_BOX, Axis_label, LABEL, HEADER, GROUP_BOX, BUTTON, AXIS_COLORS
)
from ui.core.base_panel import Base_Panel


class Orbit_Camera_Panel(Base_Panel):
    """
    Orbit Camera의 시점/렌즈/민감도를 독립적으로 조작하는 도메인 패널.

    Attributes:
        _camera (Orbit_Camera | None): 바인딩된 뷰포트 카메라 인스턴스.
        _block (bool): UI 업데이트 중 시그널 무한 루프 방지 플래그.
    """

    def __init__(self, parent: QWidget | None = None):
        """초기화 및 부모 클래스 규격 상속."""
        self._camera: Orbit_Camera | None = None
        self._block = False
        super().__init__(parent)

    def Bind_camera(self, camera: Orbit_Camera) -> None:
        """
        Viewer의 Orbit_Camera 인스턴스를 바인딩하고 UI 상태를 동기화함.

        Args:
            camera: 조작 대상 카메라 인스턴스.
        """
        self._camera = camera
        self._Sync_from_camera()
        # 뷰포트 마우스 조작 → 패널 스핀박스 역방향 동기화
        self.bus.camera_moved.connect(self.Refresh)

    # ==========================================
    # UI 구성 (Base_Panel 훅 오버라이드)
    # ==========================================

    def _setup_ui(self) -> None:
        """위젯 생성 및 self.main_layout 부착."""
        
        _header = QLabel("Viewport Camera")
        _header.setStyleSheet(HEADER)
        self.main_layout.addWidget(_header)

        # --- 시점 (Orbit) 그룹 ---
        _orbit_group = QGroupBox("Orbit")
        _orbit_group.setStyleSheet(GROUP_BOX)
        _og = QVBoxLayout(_orbit_group)
        _og.setSpacing(6)

        self.target_spins = self._Create_xyz_row("Target", _og)
        self.distance_spin = self._Create_row("Distance", 0.1, 9999.0, 15.0, 0.5, _og)
        self.pitch_spin = self._Create_row("Pitch", -89.0, 89.0, 30.0, 1.0, _og)
        self.yaw_spin = self._Create_row("Yaw", -9999.0, 9999.0, 45.0, 1.0, _og)

        self.main_layout.addWidget(_orbit_group)

        # --- 렌즈 (Lens) 그룹 ---
        _lens_group = QGroupBox("Lens")
        _lens_group.setStyleSheet(GROUP_BOX)
        _lg = QVBoxLayout(_lens_group)
        _lg.setSpacing(6)

        self.fov_spin = self._Create_row("FOV", 1.0, 179.0, 45.0, 1.0, _lg)
        self.near_spin = self._Create_row("Near (m)", 0.001, 1000.0, 0.1, 0.01, _lg)
        self.far_spin = self._Create_row("Far (m)", 1.0, 100000.0, 1000.0, 10.0, _lg)

        self.main_layout.addWidget(_lens_group)

        # --- 민감도 (Sensitivity) 그룹 ---
        _sens_group = QGroupBox("Sensitivity")
        _sens_group.setStyleSheet(GROUP_BOX)
        _sg = QVBoxLayout(_sens_group)
        _sg.setSpacing(6)

        self.pan_speed_spin = self._Create_row("Pan", 0.001, 1.0, 0.01, 0.005, _sg)
        self.rot_speed_spin = self._Create_row("Rotate", 0.01, 5.0, 0.5, 0.05, _sg)
        self.zoom_speed_spin = self._Create_row("Zoom", 0.01, 5.0, 0.5, 0.05, _sg)

        self.main_layout.addWidget(_sens_group)

        # --- 리셋 버튼 ---
        self.btn_reset = QPushButton("Reset Camera")
        self.btn_reset.setStyleSheet(BUTTON)
        self.btn_reset.clicked.connect(self._On_reset_clicked)
        self.main_layout.addWidget(self.btn_reset)
        
        # 여백 확보
        self.main_layout.addStretch()

    # ==========================================
    # 위젯 생성 헬퍼
    # ==========================================

    def _Create_row(
        self, label: str, min_v: float, max_v: float,
        default: float, step: float, parent: QVBoxLayout
    ) -> QDoubleSpinBox:
        """단일 파라미터 스핀박스 UI 행 생성."""
        _row = QHBoxLayout()
        _row.setSpacing(4)

        _lbl = QLabel(label)
        _lbl.setFixedWidth(65)
        _lbl.setStyleSheet(LABEL)
        _row.addWidget(_lbl)

        _spin = QDoubleSpinBox()
        _spin.setRange(min_v, max_v)
        _spin.setDecimals(3)
        _spin.setSingleStep(step)
        _spin.setValue(default)
        _spin.setStyleSheet(SPIN_BOX)
        _spin.valueChanged.connect(self._On_value_edited)
        _row.addWidget(_spin)

        parent.addLayout(_row)
        return _spin

    def _Create_xyz_row(
        self, label: str, parent: QVBoxLayout
    ) -> list[QDoubleSpinBox]:
        """XYZ 3축 파라미터 스핀박스 UI 행 생성."""
        _row = QHBoxLayout()
        _row.setSpacing(4)

        _lbl = QLabel(label)
        _lbl.setFixedWidth(65)
        _lbl.setStyleSheet(LABEL)
        _row.addWidget(_lbl)

        _spins: list[QDoubleSpinBox] = []
        for _axis, _color in zip(['X', 'Y', 'Z'], AXIS_COLORS):
            _axis_lbl = QLabel(_axis)
            _axis_lbl.setStyleSheet(Axis_label(_color))
            _axis_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _row.addWidget(_axis_lbl)

            _spin = QDoubleSpinBox()
            _spin.setRange(-9999.0, 9999.0)
            _spin.setDecimals(3)
            _spin.setSingleStep(0.1)
            _spin.setValue(0.0)
            _spin.setStyleSheet(SPIN_BOX)
            _spin.valueChanged.connect(self._On_value_edited)
            _row.addWidget(_spin)
            _spins.append(_spin)

        parent.addLayout(_row)
        return _spins

    # ==========================================
    # 데이터 바인딩 및 이벤트
    # ==========================================

    def _Sync_from_camera(self) -> None:
        """카메라 인스턴스의 현재 값을 UI 스핀박스에 동기화함."""
        if not self._camera:
            return
        
        self._block = True # 시그널 무한 루프 차단

        _c = self._camera
        for i in range(3):
            self.target_spins[i].setValue(float(_c.target[i]))
        self.distance_spin.setValue(_c.distance)
        self.pitch_spin.setValue(_c.pitch)
        self.yaw_spin.setValue(_c.yaw)

        self.fov_spin.setValue(_c.fov)
        self.near_spin.setValue(_c.near_clip)
        self.far_spin.setValue(_c.far_clip)

        self.pan_speed_spin.setValue(_c.pan_speed)
        self.rot_speed_spin.setValue(_c.rot_speed)
        self.zoom_speed_spin.setValue(_c.zoom_speed)

        self._block = False

    def _On_value_edited(self) -> None:
        """스핀박스 값 변경 이벤트를 카메라 객체에 반영하고 전역 시그널을 발행함."""
        if self._block or not self._camera:
            return
        _c = self._camera

        _c.target = np.array([s.value() for s in self.target_spins], dtype=np.float32)
        _c.distance = self.distance_spin.value()
        _c.pitch = self.pitch_spin.value()
        _c.yaw = self.yaw_spin.value()

        _c.fov = self.fov_spin.value()
        _c.near_clip = self.near_spin.value()
        _c.far_clip = self.far_spin.value()

        _c.pan_speed = self.pan_speed_spin.value()
        _c.rot_speed = self.rot_speed_spin.value()
        _c.zoom_speed = self.zoom_speed_spin.value()

        self.bus.camera_changed.emit()

    def _On_reset_clicked(self) -> None:
        """카메라 파라미터를 초기 기본값으로 복원함."""
        if not self._camera:
            return
        _c = self._camera
        
        _c.target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        _c.distance = 15.0
        _c.pitch = 30.0
        _c.yaw = 45.0
        _c.fov = 45.0
        _c.near_clip = 0.1
        _c.far_clip = 1000.0
        _c.pan_speed = 0.01
        _c.rot_speed = 0.5
        _c.zoom_speed = 0.5

        self._Sync_from_camera()
        self.bus.camera_changed.emit()

    def Refresh(self) -> None:
        """마우스 조작 등 외부 요인으로 카메라 값이 변경되었을 때 UI를 동기화함."""
        self._Sync_from_camera()