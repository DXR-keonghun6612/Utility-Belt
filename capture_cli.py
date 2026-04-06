"""헤드리스 데이터셋 생성 진입점.

Usage:
    python capture_cli.py --capture path/to/render_config.json
"""

import sys
import argparse
from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QApplication

from python_toolbox.project import Project_Template, Read_from_file

from data.scene.node import Scene_Node
from data.scene.scene_file import load_scene
from data.io.loader import load_file
from graphics.render.config import Render_Config, Sample_delta_matrix
from graphics.render.pipeline import Render_Pipeline
from graphics.render.exporter import Result_Exporter


class Capture_Project(Project_Template):
    """단일 장면에 대한 다중 패스 오프스크린 렌더링 및 저장을 관리함."""

    def __init__(self, config: Render_Config):
        super().__init__("capture")
        self._config = config
        self._pipeline = Render_Pipeline(config)
        self._exporter = Result_Exporter(self.workspace)
        self._frame_counter = 0

    def Run(
        self, root_node: Scene_Node, camera_node: Scene_Node,
        width: int, height: int
    ) -> Path:
        """오프스크린 컨텍스트를 생성하고 렌더링 후 결과를 저장함.

        Args:
            root_node: 렌더링할 씬의 루트 노드.
            camera_node: 카메라 씬 노드 (intrinsic 필드 필수).
            width: 출력 해상도 너비 (px).
            height: 출력 해상도 높이 (px).

        Returns:
            Path: 저장된 출력 디렉토리 경로.
        """
        if not self._is_setup_done:
            raise RuntimeError(
                "[ERROR] 'Capture_Project.Run()' invoked before '_Setup()' completed."
            )

        self._pipeline.Setup_headless_context(width, height)

        try:
            _results = self._pipeline.Execute(root_node, camera_node, width, height)
            _frame_dir = self._exporter.Save(
                self._frame_counter, _results, camera_node, self._config
            )
            self._frame_counter += 1
        finally:
            self._pipeline.Teardown_headless_context()

        return _frame_dir


# ==========================================
# 유틸리티
# ==========================================

def _Find_camera_node(root: Scene_Node, label: str) -> Scene_Node | None:
    """장면 트리에서 지정된 라벨의 카메라 노드를 탐색함."""
    if root.label == label and root.prim_type == "Camera":
        return root
    for _child in root.children:
        _found = _Find_camera_node(_child, label)
        if _found is not None:
            return _found
    return None


def _Find_node_by_label(root: Scene_Node, label: str) -> Scene_Node | None:
    """장면 트리에서 지정된 라벨의 노드를 탐색함."""
    if root.label == label:
        return root
    for _child in root.children:
        _found = _Find_node_by_label(_child, label)
        if _found is not None:
            return _found
    return None


def _Inject_obj_into_scene(
    scene_root: Scene_Node, obj_node: Scene_Node,
    target_label: str
) -> None:
    """장면 트리의 대상 노드 자식을 교체하여 OBJ를 삽입함."""
    if not target_label:
        _cloned = obj_node.Clone()
        _cloned.Set_parent(scene_root)
        scene_root.children.append(_cloned)
        return

    _target = _Find_node_by_label(scene_root, target_label)
    if _target is None:
        raise ValueError(
            f"[ERROR] 대상 노드 '{target_label}'을(를) 장면에서 찾을 수 없음."
        )

    _target.children = [
        _c for _c in _target.children if _c.prim_type != "Mesh"
    ]

    if obj_node.prim_type in ("Xform", "Stage"):
        for _child in obj_node.children:
            _cloned = _child.Clone()
            _cloned.Set_parent(_target)
            _target.children.append(_cloned)
    else:
        _cloned = obj_node.Clone()
        _cloned.Set_parent(_target)
        _target.children.append(_cloned)


# ==========================================
# 배치 캡처 실행
# ==========================================

def _Resolve_render_size(camera_node: Scene_Node) -> tuple[int, int]:
    """카메라 intrinsic에서 렌더 해상도를 취득함.

    intrinsic이 없으면 기본 1920x1080을 반환함.
    """
    _intr = getattr(camera_node, "intrinsic", None)
    if _intr is None:
        return 1920, 1080
    return _intr.width, _intr.height


def Run_batch_capture(config_path: Path) -> None:
    """Render_Config를 로드하고 배치 렌더링을 실행함.

    Args:
        config_path: Render_Config JSON 파일 경로.
    """
    _cfg = Read_from_file(Render_Config, config_path)
    _base_dir = config_path.parent.resolve()

    if _cfg.obj_dir:
        _obj_dir = (_base_dir / _cfg.obj_dir).resolve()
        _obj_files = sorted(_obj_dir.glob("*.obj"))

        if not _obj_files:
            print(f"[WARN] OBJ 파일 없음: {_obj_dir}")
            return

        print(f"[INFO] OBJ 디렉토리: {_obj_dir}")
        print(f"[INFO] 발견된 OBJ 수: {len(_obj_files)}")
        print(f"[INFO] OBJ당 샘플 수: {_cfg.num_samples}")

        _project = Capture_Project(_cfg)
        for _obj_idx, _obj_path in enumerate(_obj_files):
            _obj_name = _obj_path.stem
            print(f"\n[INFO] === [{_obj_idx + 1}/{len(_obj_files)}] {_obj_name} ===")

            _scene_path = (_base_dir / _cfg.scene_path).resolve()
            _root = load_scene(_scene_path)

            _obj_node = load_file(_obj_path)
            _Inject_obj_into_scene(_root, _obj_node, _cfg.target_node_label)

            _camera = _Find_camera_node(_root, _cfg.camera_label)
            if _camera is None:
                print(f"[WARN] 카메라 '{_cfg.camera_label}' 없음. 건너뜀.")
                continue

            _w, _h = _Resolve_render_size(_camera)

            _project._Setup()
            _obj_workspace = _project.workspace / _obj_name
            _obj_workspace.mkdir(parents=True, exist_ok=True)
            _project._exporter = Result_Exporter(_obj_workspace)
            _project._frame_counter = 0
            _base_matrix = _camera.local_matrix.copy()

            for _i in range(_cfg.num_samples):
                _camera.local_matrix = _base_matrix @ Sample_delta_matrix(_cfg)
                _frame_dir = _project.Run(_root, _camera, _w, _h)
                print(f"[INFO]   [{_i + 1}/{_cfg.num_samples}] {_frame_dir}")

        print(f"\n[INFO] 전체 배치 완료. OBJ {len(_obj_files)}개 x {_cfg.num_samples}샘플.")

    else:
        _scene_path = (_base_dir / _cfg.scene_path).resolve()
        _root = load_scene(_scene_path)

        _camera = _Find_camera_node(_root, _cfg.camera_label)
        if _camera is None:
            raise ValueError(
                f"[ERROR] 카메라 노드 '{_cfg.camera_label}'을(를) 장면에서 찾을 수 없음."
            )

        _w, _h = _Resolve_render_size(_camera)

        _project = Capture_Project(_cfg)
        _project._Setup()

        print(f"[INFO] 워크스페이스: {_project.workspace}")
        print(f"[INFO] 장면: {_scene_path}")
        print(f"[INFO] 해상도: {_w}x{_h}")
        print(f"[INFO] 샘플 수: {_cfg.num_samples}")
        _base_matrix = _camera.local_matrix.copy()

        for _i in range(_cfg.num_samples):
            _camera.local_matrix = _base_matrix @ Sample_delta_matrix(_cfg)
            _frame_dir = _project.Run(_root, _camera, _w, _h)
            print(f"[INFO] [{_i + 1}/{_cfg.num_samples}] 저장 완료: {_frame_dir}")

        print(f"[INFO] 배치 캡처 완료. 총 {_cfg.num_samples}프레임.")


# ==========================================
# CLI 진입점
# ==========================================

def _Build_arg_parser() -> argparse.ArgumentParser:
    _parser = argparse.ArgumentParser(
        description="FOCUS 헤드리스 렌더링 파이프라인"
    )
    _parser.add_argument(
        "--capture", type=Path, default=None,
        help="Render_Config JSON 파일 경로 (배치 캡처)"
    )
    return _parser


if __name__ == "__main__":
    _args = _Build_arg_parser().parse_args()

    _app = QApplication.instance() or QApplication(sys.argv)

    if _args.capture:
        Run_batch_capture(_args.capture)
    else:
        print("[ERROR] --capture 옵션을 지정해야 함.")
        sys.exit(1)
