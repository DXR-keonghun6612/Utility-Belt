"""시뮬레이션 패널 메인 레이아웃 및 제어 모듈."""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox,
    QHBoxLayout, QVBoxLayout, QGroupBox, QDialog, QComboBox, QSpinBox, QFormLayout,
    QCheckBox,
)

from python_toolbox.file import Read_from
from spatial_toolbox.scene import Controller as Stage_Controller
from spatial_toolbox.scene.asset.cache import ASSET_CACHE
from spatial_toolbox.simulation import Sim_Config
from ui.panels._base import Base_Panel

from .dialog import Generate_Config_Dialog
from .worker import Simulation_Worker

_PROFILES = [
    ("Blender - 객체별 렌더링", "blender"),
    ("OpenGL - 객체별 렌더링", "opengl"),
]
_CONTEXT_OPTIONS = [
    ("자동 (EGL → Embedded)", "auto"),
    ("EGL (헤드리스)", "egl"),
    ("Embedded (Qt 컨텍스트)", "embedded"),
]


class Simulation_Page(Base_Panel):
    """시뮬레이션 파이프라인 설정을 로드/생성하고 워커를 제어하는 메인 UI 패널."""

    def __init__(self, stage: Stage_Controller, parent: QWidget | None = None):
        self.stage = stage
        self.worker: Simulation_Worker | None = None
        self.scene_usd_path: Path | None = None
        self.config_path: Path | None = None
        self.output_dir: Path | None = None
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """메인 레이아웃 구성."""
        self.title_label = QLabel("Simulation Engine")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        self.main_layout.addWidget(self.title_label)

        self.main_layout.addWidget(self._Build_scene_group())
        self.main_layout.addWidget(self._Build_config_group())
        self.main_layout.addWidget(self._Build_output_group())
        self.main_layout.addWidget(self._Build_profile_group())

        _btn_row = QHBoxLayout()
        self.btn_run = QPushButton("시뮬레이션 시작")
        self.btn_run.setFixedHeight(40)
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._run_simulation)
        self.btn_run.setStyleSheet("font-weight: bold; margin-top: 10px;")
        _btn_row.addWidget(self.btn_run)

        self.btn_stop = QPushButton("정지")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setFixedWidth(70)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_simulation)
        self.btn_stop.setStyleSheet("color: #ff6666; margin-top: 10px;")
        _btn_row.addWidget(self.btn_stop)
        self.main_layout.addLayout(_btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("margin-top: 5px;")
        self.main_layout.addWidget(self.status_label)

        self.main_layout.addStretch()

    def _Build_scene_group(self) -> QGroupBox:
        _group = QGroupBox("씬")
        _layout = QVBoxLayout(_group)

        self.scene_path_label = QLabel("Scene USD: 없음")
        self.scene_path_label.setWordWrap(True)
        self.scene_path_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        _layout.addWidget(self.scene_path_label)

        _btn_layout = QHBoxLayout()

        self.btn_export_scene = QPushButton("씬 USD 내보내기")
        self.btn_export_scene.setFixedHeight(30)
        self.btn_export_scene.clicked.connect(self._export_scene_usd)
        _btn_layout.addWidget(self.btn_export_scene)

        self.btn_load_scene = QPushButton("씬 USD 로드")
        self.btn_load_scene.setFixedHeight(30)
        self.btn_load_scene.clicked.connect(self._load_scene_usd)
        _btn_layout.addWidget(self.btn_load_scene)

        _layout.addLayout(_btn_layout)
        return _group

    def _Build_config_group(self) -> QGroupBox:
        _group = QGroupBox("Render Config")
        _layout = QVBoxLayout(_group)

        self.config_path_label = QLabel("Config: 없음")
        self.config_path_label.setWordWrap(True)
        self.config_path_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        _layout.addWidget(self.config_path_label)

        _btn_layout = QHBoxLayout()

        self.btn_generate_config = QPushButton("Config 생성")
        self.btn_generate_config.setFixedHeight(30)
        self.btn_generate_config.clicked.connect(self._generate_config)
        _btn_layout.addWidget(self.btn_generate_config)

        self.btn_select_config = QPushButton("Config 로드")
        self.btn_select_config.setFixedHeight(30)
        self.btn_select_config.clicked.connect(self._select_config)
        _btn_layout.addWidget(self.btn_select_config)

        self.btn_edit_config = QPushButton("Config 편집")
        self.btn_edit_config.setFixedHeight(30)
        self.btn_edit_config.clicked.connect(self._edit_config)
        _btn_layout.addWidget(self.btn_edit_config)

        _layout.addLayout(_btn_layout)
        return _group

    def _Build_output_group(self) -> QGroupBox:
        _group = QGroupBox("출력 폴더")
        _layout = QVBoxLayout(_group)

        self.output_dir_label = QLabel("Config 파일 경로 기준 (자동)")
        self.output_dir_label.setWordWrap(True)
        self.output_dir_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        _layout.addWidget(self.output_dir_label)

        _btn_layout = QHBoxLayout()
        self.btn_select_output = QPushButton("폴더 선택")
        self.btn_select_output.setFixedHeight(30)
        self.btn_select_output.clicked.connect(self._select_output_dir)
        _btn_layout.addWidget(self.btn_select_output)

        self.btn_reset_output = QPushButton("자동으로 초기화")
        self.btn_reset_output.setFixedHeight(30)
        self.btn_reset_output.setEnabled(False)
        self.btn_reset_output.clicked.connect(self._reset_output_dir)
        _btn_layout.addWidget(self.btn_reset_output)

        _layout.addLayout(_btn_layout)
        return _group

    def _Build_profile_group(self) -> QGroupBox:
        _group = QGroupBox("렌더 프로필")
        _layout = QVBoxLayout(_group)
        _layout.setSpacing(8)

        self.profile_combo = QComboBox()
        for _label, _ in _PROFILES:
            self.profile_combo.addItem(_label)
        _layout.addWidget(self.profile_combo)

        # OpenGL 전용 옵션 (profile = opengl 일 때만 활성)
        self._opengl_options = QWidget()
        _form = QFormLayout(self._opengl_options)
        _form.setContentsMargins(0, 0, 0, 0)
        _form.setSpacing(4)

        self.cb_context = QComboBox()
        for _label, _ in _CONTEXT_OPTIONS:
            self.cb_context.addItem(_label)
        _form.addRow("컨텍스트:", self.cb_context)

        self.spin_width = QSpinBox()
        self.spin_width.setRange(64, 8192)
        self.spin_width.setValue(640)
        self.spin_height = QSpinBox()
        self.spin_height.setRange(64, 8192)
        self.spin_height.setValue(480)
        _form.addRow("W (px):", self.spin_width)
        _form.addRow("H (px):", self.spin_height)

        _layout.addWidget(self._opengl_options)
        self._opengl_options.setVisible(False)

        # 렌더 패스 선택 (Blender / OpenGL 공통)
        _pass_group = QGroupBox("렌더 패스")
        _pass_row = QHBoxLayout(_pass_group)
        _pass_row.setSpacing(12)
        self.chk_rgb   = QCheckBox("RGB");         self.chk_rgb.setChecked(True)
        self.chk_depth = QCheckBox("Depth");       self.chk_depth.setChecked(True)
        self.chk_normal = QCheckBox("Normal");     self.chk_normal.setChecked(True)
        self.chk_seg   = QCheckBox("Segmentation"); self.chk_seg.setChecked(True)
        for _chk in (self.chk_rgb, self.chk_depth, self.chk_normal, self.chk_seg):
            _pass_row.addWidget(_chk)
        _pass_row.addStretch()
        _layout.addWidget(_pass_group)

        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)

        return _group

    def _on_profile_changed(self, index: int) -> None:
        _, _key = _PROFILES[index]
        self._opengl_options.setVisible(_key == "opengl")

    def _select_output_dir(self) -> None:
        """결과 저장 폴더를 수동으로 지정함."""
        _path = QFileDialog.getExistingDirectory(
            self, "출력 폴더 선택", "",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not _path:
            return
        self.output_dir = Path(_path)
        self.output_dir_label.setText(str(self.output_dir))
        self.output_dir_label.setStyleSheet("font-size: 12px;")
        self.btn_reset_output.setEnabled(True)

    def _reset_output_dir(self) -> None:
        """출력 폴더를 씬 경로 기준 자동 모드로 복원함."""
        self.output_dir = None
        self.output_dir_label.setText("Config 파일 경로 기준 (자동)")
        self.output_dir_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self.btn_reset_output.setEnabled(False)

    def _connect_signals(self) -> None:
        self.bus.scene_path_changed.connect(self._on_scene_path_changed)

    def _on_scene_path_changed(self, path: str) -> None:
        self.scene_usd_path = Path(path)
        self.scene_path_label.setText(f"Scene USD: {self.scene_usd_path}")
        if self.config_path:
            self.btn_run.setEnabled(True)

    def _load_scene_usd(self) -> None:
        """USD 파일에서 씬 그래프와 에셋 캐시를 복원함."""
        _path, _ = QFileDialog.getOpenFileName(
            self, "씬 USD 파일 선택", "", "USD Files (*.usd *.usda *.usdc)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not _path:
            return

        self.scene_usd_path = Path(_path)
        self.scene_path_label.setText(f"Scene USD: {self.scene_usd_path}")

        self.status_label.setText("씬 로드 중...")
        ASSET_CACHE.Clear()
        try:
            self.stage.Import(str(self.scene_usd_path))
        except Exception as e:
            QMessageBox.critical(self, "오류", f"씬 로드 실패:\n{e}")
            self.status_label.setText("씬 로드 실패.")
            return

        self.bus.scene_loaded.emit()
        self.bus.scene_path_changed.emit(str(self.scene_usd_path))
        self.status_label.setText("씬 로드 완료.")

    def _export_scene_usd(self) -> None:
        """현재 씬을 메쉬 포함 USD로 내보내고 경로를 등록함."""
        if not self.stage.root:
            QMessageBox.warning(self, "경고", "활성화된 씬이 없음.")
            return

        _save_path, _ = QFileDialog.getSaveFileName(
            self, "씬 USD 저장", "scene.usd", "USD Files (*.usd *.usda *.usdc)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not _save_path:
            return

        _usd_path = Path(_save_path)
        self.stage.Export(str(_usd_path))
        self.scene_usd_path = _usd_path
        self.scene_path_label.setText(f"Scene USD: {_usd_path}")
        self.status_label.setText("씬 USD 저장됨.")

    def _generate_config(self) -> None:
        """등록된 씬 USD 경로를 기반으로 Config를 생성하여 저장함."""
        if not self.stage.root:
            QMessageBox.warning(self, "경고", "활성화된 씬이 없음.")
            return
        if self.scene_usd_path is None:
            QMessageBox.warning(self, "경고", "먼저 씬 USD를 내보내야 함.")
            return

        _dialog = Generate_Config_Dialog(self.stage, self)
        if _dialog.exec() != QDialog.DialogCode.Accepted:
            return

        _cfg = _dialog.Get_config()

        _save_path, _ = QFileDialog.getSaveFileName(
            self, "Render Config 저장", "render_config.json", "JSON Files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not _save_path:
            return

        _out_path = Path(_save_path)
        _cfg.scene_path = str(self.scene_usd_path)
        _cfg.Write_to(_out_path.name, _out_path.parent)

        self.config_path = _out_path
        self.config_path_label.setText(f"Config: {self.config_path}")
        self.btn_run.setEnabled(True)
        self.status_label.setText("Config 저장됨.")

    def _select_config(self) -> None:
        """기존 Config 파일 로드 처리."""
        _path, _ = QFileDialog.getOpenFileName(
            self, "Render Config 파일 선택", "", "JSON Files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not _path:
            return

        self.config_path = Path(_path)
        self.config_path_label.setText(f"Config: {self.config_path}")
        self.btn_run.setEnabled(True)
        self.status_label.setText("Config 로드됨.")

    def _edit_config(self) -> None:
        """기존 Config 파일을 불러와 편집 후 저장함."""
        _path, _ = QFileDialog.getOpenFileName(
            self, "편집할 Config 선택", "", "JSON Files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not _path:
            return

        _ok, _data = Read_from(Path(_path))
        if not _ok or not isinstance(_data, dict):
            QMessageBox.warning(self, "경고", "Config 파일 읽기 실패.")
            return

        _cfg = Sim_Config(**_data)

        _dialog = Generate_Config_Dialog(self.stage, self)
        _dialog.Set_config(_cfg)
        if _dialog.exec() != QDialog.DialogCode.Accepted:
            return

        _edited = _dialog.Get_config()
        _edited.scene_path = _cfg.scene_path

        _save_path, _ = QFileDialog.getSaveFileName(
            self, "Config 저장", _path, "JSON Files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not _save_path:
            return

        _out = Path(_save_path)
        _edited.Write_to(_out.name, _out.parent)

        self.config_path = _out
        self.config_path_label.setText(f"Config: {self.config_path}")
        self.btn_run.setEnabled(True)
        self.status_label.setText("Config 편집 완료.")

    def _run_simulation(self) -> None:
        """워커 스레드 인스턴스화 및 렌더링 비동기 실행."""
        if not self.config_path:
            return

        _profile_idx = self.profile_combo.currentIndex()
        _, _profile_key = _PROFILES[_profile_idx]
        _context_idx = self.cb_context.currentIndex()
        _, _context_key = _CONTEXT_OPTIONS[_context_idx]

        _channels = [
            ch for ch, chk in (
                ("rgb", self.chk_rgb),
                ("depth", self.chk_depth),
                ("normal", self.chk_normal),
                ("segmentation", self.chk_seg),
            ) if chk.isChecked()
        ]
        if not _channels:
            QMessageBox.warning(self, "경고", "최소 하나의 렌더 패스를 선택해야 함.")
            return

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_export_scene.setEnabled(False)
        self.btn_generate_config.setEnabled(False)
        self.btn_select_config.setEnabled(False)
        self.btn_edit_config.setEnabled(False)
        self.btn_select_output.setEnabled(False)
        self.btn_reset_output.setEnabled(False)
        self.profile_combo.setEnabled(False)
        self._opengl_options.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.status_label.setText("시뮬레이션 초기화 중...")
        self.bus.simulation_progress.emit(0, 0, "시뮬레이션 초기화 중...")

        self.worker = Simulation_Worker(
            self.config_path,
            profile=_profile_key,
            width=self.spin_width.value(),
            height=self.spin_height.value(),
            context_type=_context_key,
            output_dir=self.output_dir,
            channels=_channels,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_sig.connect(self._on_finished)
        self.worker.start()

    def _stop_simulation(self) -> None:
        """실행 중인 워커에 정지 요청을 보냄."""
        if self.worker is not None:
            self.btn_stop.setEnabled(False)
            self.status_label.setText("정지 요청 중...")
            self.worker.Request_stop()

    def _on_progress(self, current: int, total: int, message: str) -> None:
        """워커의 진행 상태 갱신 이벤트 처리."""
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
            self.status_label.setText(f"{message} ({current}/{total})")
        else:
            self.progress_bar.setRange(0, 0)
            self.status_label.setText(message)
        self.bus.simulation_progress.emit(current, total, message)

    def _on_finished(self, success: bool, message: str) -> None:
        """시뮬레이션 완료 상태 복구 이벤트 처리."""
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_export_scene.setEnabled(True)
        self.btn_generate_config.setEnabled(True)
        self.btn_select_config.setEnabled(True)
        self.btn_edit_config.setEnabled(True)
        self.btn_select_output.setEnabled(True)
        self.btn_reset_output.setEnabled(self.output_dir is not None)
        self.profile_combo.setEnabled(True)
        self._opengl_options.setEnabled(True)

        if success:
            self.status_label.setText("완료됨!")
            self.bus.simulation_progress.emit(1, 1, "완료됨!")
            QMessageBox.information(self, "성공", message)
        else:
            self.status_label.setText("실패!")
            self.bus.simulation_progress.emit(0, 0, "실패!")
            QMessageBox.critical(self, "오류", f"시뮬레이션 실패:\n{message}")

        self.worker = None
