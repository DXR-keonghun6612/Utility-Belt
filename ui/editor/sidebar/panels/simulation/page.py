# Simulation Panel Package
port traceback

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal

from simulation.engine import Run_batch_capture

class Simulation_Worker(QThread):
    progress = Signal(int, int, str)
    finished_sig = Signal(bool, str)

    def __init__(self, config_path: Path):
        super().__init__()
        self.config_path = config_path

    def run(self):
        try:
            Run_batch_capture(self.config_path, progress_callback=self._emit_progress)
            self.finished_sig.emit(True, "시뮬레이션이 성공적으로 완료되었습니다.")
        except Exception as e:
            err = traceback.format_exc()
            self.finished_sig.emit(False, f"{str(e)}\n\n{err}")

    def _emit_progress(self, current: int, total: int, message: str):
        self.progress.emit(current, total, message)


class Simulation_Page(QWidget):
    """시뮬레이션(렌더링 파이프라인) 설정을 로드하고 실행하는 UI 패널."""
    def __init__(self):
        super().__init__()
        self._init_ui()
        self.worker = None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.title_label = QLabel("Simulation Engine")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        layout.addWidget(self.title_label)

        self.config_path_label = QLabel("선택된 Config 없음")
        self.config_path_label.setWordWrap(True)
        self.config_path_label.setStyleSheet("color: #aaaaaa; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(self.config_path_label)

        self.btn_select_config = QPushButton("Render Config 선택 (JSON)")
        self.btn_select_config.setFixedHeight(30)
        self.btn_select_config.clicked.connect(self._select_config)
        layout.addWidget(self.btn_select_config)

        self.btn_run = QPushButton("시뮬레이션 시작")
        self.btn_run.setFixedHeight(40)
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._run_simulation)
        self.btn_run.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(self.btn_run)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("margin-top: 5px;")
        layout.addWidget(self.status_label)

        self.config_path = None

    def _select_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Render Config 파일 선택", "", "JSON Files (*.json)")
        if path:
            self.config_path = Path(path)
            self.config_path_label.setText(str(self.config_path))
            self.btn_run.setEnabled(True)

    def _run_simulation(self):
        if not self.config_path:
            return

        self.btn_run.setEnabled(False)
        self.btn_select_config.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("시뮬레이션 초기화 중...")

        self.worker = Simulation_Worker(self.config_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_sig.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, current: int, total: int, message: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.status_label.setText(message)

    def _on_finished(self, success: bool, message: str):
        self.btn_run.setEnabled(True)
        self.btn_select_config.setEnabled(True)
        
        if success:
            self.status_label.setText("완료됨!")
            QMessageBox.information(self, "성공", message)
        else:
            self.status_label.setText("실패!")
            QMessageBox.critical(self, "오류", f"시뮬레이션 실패:\n{message}")
        
        self.worker = None
