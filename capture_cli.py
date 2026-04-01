"""헤드리스 데이터셋 생성 진입점.

Usage:
    python capture_cli.py --config path/to/render_config.json --scene path/to/scene.json

    또는 Python 스크립트에서 직접:

    from capture_cli import Capture_Project
    from graphics.render.config import Render_Config
    from data.scene.node import Scene_Node

    config = Render_Config(width=640, height=480, passes=["rgb", "depth"])
    project = Capture_Project(config)
    project._Setup()
    project.Run(root_node, camera_node)
"""

import sys
import argparse
from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QApplication

from python_toolbox.project import Project_Template, Read_from_file

from data.scene.node import Scene_Node
from graphics.render.config import Render_Config
from graphics.render.pipeline import Render_Pipeline
from graphics.render.exporter import Result_Exporter


class Capture_Project(Project_Template):
    """단일 장면에 대한 다중 패스 오프스크린 렌더링 및 저장을 관리함.

    생명주기:
        project = Capture_Project(config)
        project._Setup()                     # 출력 워크스페이스 생성
        project.Run(root_node, camera_node)  # 렌더링 실행 및 저장
    """

    def __init__(self, config: Render_Config):
        super().__init__("capture")
        self._config = config
        self._pipeline = Render_Pipeline(config)
        self._exporter = Result_Exporter(self.workspace)
        self._frame_counter = 0

    def Run(self, root_node: Scene_Node, camera_node: Scene_Node) -> Path:
        """오프스크린 컨텍스트를 생성하고 렌더링 후 결과를 저장함.

        Args:
            root_node: 렌더링할 씬의 루트 노드.
            camera_node: 카메라 씬 노드 (intrinsic 필드 필수).

        Returns:
            Path: 저장된 프레임 디렉토리 경로.
        """
        if not self._is_setup_done:
            raise RuntimeError(
                "[ERROR] 'Capture_Project.Run()' invoked before '_Setup()' completed."
            )

        self._pipeline.Setup_headless_context()

        try:
            _results = self._pipeline.Execute(root_node, camera_node)
            _frame_dir = self._exporter.Save(
                self._frame_counter, _results, camera_node, self._config
            )
            self._frame_counter += 1
        finally:
            self._pipeline.Teardown_headless_context()

        return _frame_dir


# ==========================================
# CLI 진입점
# ==========================================

def _Build_arg_parser() -> argparse.ArgumentParser:
    _parser = argparse.ArgumentParser(
        description="FOCUS 헤드리스 렌더링 파이프라인"
    )
    _parser.add_argument(
        "--config", type=Path, required=True,
        help="Render_Config JSON 파일 경로"
    )
    return _parser


if __name__ == "__main__":
    _args = _Build_arg_parser().parse_args()

    # QApplication은 QOffscreenSurface 생성 전에 반드시 존재해야 함
    _app = QApplication.instance() or QApplication(sys.argv)

    _config = Read_from_file(Render_Config, _args.config)
    _project = Capture_Project(_config)
    _project._Setup()

    print(f"[INFO] 워크스페이스: {_project.workspace}")
    print("[INFO] 씬 및 카메라 노드를 직접 주입하여 project.Run()을 호출하세요.")
