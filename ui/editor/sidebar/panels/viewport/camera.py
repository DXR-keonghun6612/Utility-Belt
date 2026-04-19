"""Orbit Camera 파라미터를 실시간 편집하는 뷰포트 카메라 컨트롤 패널."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QGroupBox, QPushButton
)
from PySide6.QtCore import Signal, Qt

from viewport.view import Orbit_Camera
from ui.style import (
    SPIN_BOX, Axis_label, LABEL, HEADER, GROUP_BOX, BUTTON, AXIS_COLORS
)


class Orbit_Camera_Panel(QWidget):
    """Orbit Camera의 시점/렌즈/민감도를 사이드바에서 직접 조작하는 패널."""

    # 카메라 값 변경 시 뷰어 갱신용
    camera_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._camera: Orbit_Camera | None = None
        self._block = False
        self._Setup_ui()

    def Bind_camera(self, camera: Orbit_Camera) -> None:
        """Viewer의 Orbit_Camera 인스턴스를 바인딩하고 UI에 현재 값을 반영함."""
        self._camera = camera
        self._Sync_from_camera()

    # ==========================================
    # UI 구성
    # ==========================================

    def _Setup_ui(self) -> None:
        _layout = QVBoxLayout(self)
        _layout.setContentsMargins(10, 10, 10, 10)
        _layout.setSpacing(12)
        _layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        _header = QLabel("Viewport Camera")
        _header.setStyleSheet(HEADER)
        _layout.addWidget(_header)

        # --- 시점 (Orbit) ---
        _orbit_group = QGroupBox("Orbit")
        _orbit_group.setStyleSheet(GROUP_BOX)
        _og = QVBoxLayout(_orbit_group)
        _og.setSpacing(6)

        self.target_spins = self._Create_xyz_row("Target", _og)
        self.distance_spin = self._Create_row("Distance", 0.1, 9999.0, 15.0, 0.5, _og)
        self.pitch_spin = self._Create_row("Pitch", -89.0, 89.0, 30.0, 1.0, _og)
        self.yaw_spin = self._Create_row("Yaw", -9999.0, 9999.0, 45.0, 1.0, _og)

        _layout.addWidget(_orbit_group)

        # --- 렌즈 (Lens) ---
        _lens_group = QGroupBox("Lens")
        _lens_group.setStyleSheet(GROUP_BOX)
        _lg = QVBoxLayout(_lens_group)
        _lg.setSpacing(6)

        self.fov_spin = self._Create_row("FOV", 1.0, 179.0, 45.0, 1.0, _lg)
        self.near_spin = self._Create_row("Near", 0.001, 1000.0, 0.1, 0.01, _lg)
        self.far_spin = self._Create_row("Far", 1.0, 100000.0, 1000.0, 10.0, _lg)

        _layout.addWidget(_lens_group)

        # --- 민감도 (Sensitivity) ---
        _sens_group = QGroupBox("Sensitivity")
        _sens_group.setStyleSheet(GROUP_BOX)
        _sg = QVBoxLayout(_sens_group)
        _sg.setSpacing(6)

        self.pan_speed_spin = self._Create_row("Pan", 0.001, 1.0, 0.01, 0.005, _sg)
        self.rot_speed_spin = self._Create_row("Rotate", 0.01, 5.0, 0.5, 0.05, _sg)
        self.zoom_speed_spin = self._Create_row("Zoom", 0.01, 5.0, 0.5, 0.05, _sg)

        _layout.addWidget(_sens_group)

        # --- 리셋 버튼 ---
        self.btn_reset = QPushButton("Reset Camera")
        self.btn_reset.setStyleSheet(BUTTON)
        self.btn_reset.clicked.connect(self._On_reset_clicked)
        _layout.addWidget(self.btn_reset)

    # ==========================================
    # 위젯 생성 헬퍼
    # ==========================================

    def _Create_row(
        self, label: str, min_v: float, max_v: float,
        default: float, step: float, parent: QVBoxLayout
    ) -> QDoubleSpinBox:
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
    # 데이터 바인딩
    # ==========================================

    def _Sync_from_camera(self) -> None:
        """카메라 인스턴스의 현재 값을 UI에 반영함."""
        if not self._camera:
            return
        self._block = True

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
        """UI 스핀박스 값 변경 시 카메라에 즉시 반영."""
        if self._block or not self._camera:
            return
        _c = self._camera

        _c.target = np.array(
            [s.value() for s in self.target_spins], dtype=np.float32)
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
        """카메라를 기본값으로 초기화."""
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
        """외부에서 카메라 값이 변경된 후 UI 동기화용."""
        self._Sync_from_camera()
