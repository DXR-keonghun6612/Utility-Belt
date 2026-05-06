"""시뮬레이션 패널 메인 레이아웃 및 제어 모듈."""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox,
    QHBoxLayout, QVBoxLayout, QGroupBox, QDialog,
)

from spatial_toolbox.scene import Controller as Stage_Controller
from ui.panels._base import Base_Panel

from .dialog import Generate_Config_Dialog
from .worker import Simulation_Worker


class Simulation_Page(Base_Panel):
    """시뮬레이션 파이프라인 설정을 로드/생성하고 워커를 제어하는 메인 UI 패널."""

    def __init__(self, stage: Stage_Controller, parent: QWidget | None = None):
        self.stage = stage
        self.worker: Simulation_Worker | None = None
        self.scene_usd_path: Path | None = None
        self.config_path: Path | None = None
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """메인 레이아웃 구성."""
        self.title_label = QLabel("Simulation Engine")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        self.main_layout.addWidget(self.title_label)

        self.main_layout.addWidget(self._Build_scene_group())
        self.main_layout.addWidget(self._Build_config_group())

        self.btn_run = QPushButton("시뮬레이션 시작")
        self.btn_run.setFixedHeight(40)
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._run_simulation)
        self.btn_run.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.main_layout.addWidget(self.btn_run)

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

        _layout.addLayout(_btn_layout)
        return _group

    def _connect_signals(self) -> None:
        pass

    def _load_scene_usd(self) -> None:
        """저장된 USD 파일을 씬 경로로 등록함."""
        _path, _ = QFileDialog.getOpenFileName(
            self, "씬 USD 파일 선택", "", "USD Files (*.usd *.usda *.usdc)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not _path:
            return
        self.scene_usd_path = Path(_path)
        self.scene_path_label.setText(f"Scene USD: {self.scene_usd_path}")
        self.status_label.setText("씬 USD 로드됨.")

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

    def _run_simulation(self) -> None:
        """워커 스레드 인스턴스화 및 렌더링 비동기 실행."""
        if not self.config_path:
            return

        self.btn_run.setEnabled(False)
        self.btn_export_scene.setEnabled(False)
        self.btn_generate_config.setEnabled(False)
        self.btn_select_config.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.status_label.setText("시뮬레이션 초기화 중...")
        self.bus.simulation_progress.emit(0, 0, "시뮬레이션 초기화 중...")

        self.worker = Simulation_Worker(self.config_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_sig.connect(self._on_finished)
        self.worker.start()

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
        self.btn_export_scene.setEnabled(True)
        self.btn_generate_config.setEnabled(True)
        self.btn_select_config.setEnabled(True)

        if success:
            self.status_label.setText("완료됨!")
            self.bus.simulation_progress.emit(1, 1, "완료됨!")
            QMessageBox.information(self, "성공", message)
        else:
            self.status_label.setText("실패!")
            self.bus.simulation_progress.emit(0, 0, "실패!")
            QMessageBox.critical(self, "오류", f"시뮬레이션 실패:\n{message}")

        self.worker = None
