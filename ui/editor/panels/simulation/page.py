"""Simulation Panel Package"""
import traceback
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox
)
from PySide6.QtCore import QThread, Signal

from simulation.engine import Run_batch_capture
from ui.core.base_panel import Base_Panel


class Simulation_Worker(QThread):
    """백그라운드 스레드에서 렌더링 파이프라인(시뮬레이션)을 비동기로 실행함."""
    
    progress = Signal(int, int, str)
    finished_sig = Signal(bool, str)

    def __init__(self, config_path: Path):
        super().__init__()
        self.config_path = config_path

    def run(self):
        try:
            # 렌더링 엔진 호출. 진행률은 콜백을 통해 UI 스레드로 시그널 발행.
            Run_batch_capture(self.config_path, progress_callback=self._emit_progress)
            self.finished_sig.emit(True, "시뮬레이션이 성공적으로 완료됨.")
        except Exception as e:
            err = traceback.format_exc()
            self.finished_sig.emit(False, f"{str(e)}\n\n{err}")

    def _emit_progress(self, current: int, total: int, message: str):
        self.progress.emit(current, total, message)


class Simulation_Page(Base_Panel):
    """시뮬레이션(렌더링 파이프라인) 설정을 로드하고 실행하는 UI 도메인 패널."""
    
    def __init__(self, parent: QWidget | None = None):
        self.worker: Simulation_Worker | None = None
        self.config_path: Path | None = None
        super().__init__(parent)

    # ==========================================
    # UI 구성 (Base_Panel 훅 오버라이드)
    # ==========================================

    def _setup_ui(self) -> None:
        """위젯 생성 및 self.main_layout 부착."""
        
        self.title_label = QLabel("Simulation Engine")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        self.main_layout.addWidget(self.title_label)

        self.config_path_label = QLabel("선택된 Config 없음")
        self.config_path_label.setWordWrap(True)
        self.config_path_label.setStyleSheet("color: #aaaaaa; font-size: 12px; margin-bottom: 10px;")
        self.main_layout.addWidget(self.config_path_label)

        self.btn_select_config = QPushButton("Render Config 선택 (JSON)")
        self.btn_select_config.setFixedHeight(30)
        self.btn_select_config.clicked.connect(self._select_config)
        self.main_layout.addWidget(self.btn_select_config)

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
        
        # 여백 확보
        self.main_layout.addStretch()

    # ==========================================
    # 이벤트 및 로직
    # ==========================================

    def _select_config(self) -> None:
        """JSON 설정 파일을 선택하고 경로를 검증함."""
        _path, _ = QFileDialog.getOpenFileName(
            self, "Render Config 파일 선택", "", "JSON Files (*.json)"
        )
        if _path:
            self.config_path = Path(_path)
            self.config_path_label.setText(str(self.config_path))
            self.btn_run.setEnabled(True)

    def _run_simulation(self) -> None:
        """워커 스레드를 초기화하고 비동기 렌더링 작업을 시작함."""
        if not self.config_path:
            return

        # UI 잠금 처리
        self.btn_run.setEnabled(False)
        self.btn_select_config.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("시뮬레이션 초기화 중...")

        # 비동기 스레드 실행
        self.worker = Simulation_Worker(self.config_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_sig.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, current: int, total: int, message: str) -> None:
        """워커 스레드로부터 진행 상황을 전달받아 UI를 갱신함."""
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.status_label.setText(message)

    def _on_finished(self, success: bool, message: str) -> None:
        """워커 스레드 종료 시 UI 잠금을 해제하고 결과를 알림."""
        self.btn_run.setEnabled(True)
        self.btn_select_config.setEnabled(True)
        
        if success:
            self.status_label.setText("완료됨!")
            QMessageBox.information(self, "성공", message)
        else:
            self.status_label.setText("실패!")
            QMessageBox.critical(self, "오류", f"시뮬레이션 실패:\n{message}")
        
        self.worker = None