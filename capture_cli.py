"""헤드리스 데이터셋 생성 진입점.

Usage:
    python capture_cli.py --capture path/to/render_config.json

장면 컨벤션:
    root
    ├── camera_node (Render_Config.camera_label)
    └── target (label="target", prim_type="Xform")
        ├── object_a   ─┐
        ├── object_b    ├ 직속 1계층 자식들 — 객체별 visible 토글 순회
        └── object_c   ─┘

각 직속 자식을 단독으로 visible=True로 두고 카메라 델타 적용 후 num_samples
프레임을 캡처함.
"""

import sys
import argparse
from pathlib import Path

from PySide6.QtWidgets import QApplication

from python_toolbox.project import Project_Template, Read_from_file

from data.node import Base_Node, walk_nodes
from data.node.stage import Stage_Controller
from data.io.loader import Resolve_meshes
from graphics.render.config import Render_Config, Sample_delta_matrix
from graphics.render.pipeline import Render_Pipeline
from graphics.render.exporter import Result_Exporter


# ==========================================
# 노드 탐색 헬퍼
# ==========================================

def _Find_camera_node(root: Base_Node, label: str) -> Base_Node | None:
    """장면 트리에서 지정된 라벨의 카메라 노드를 탐색함."""
    _is_cam = lambda n: n.label == label and n.prim_type == "Camera"
    return next(walk_nodes(root, _is_cam), None)


def _Find_target_group(root: Base_Node) -> Base_Node | None:
    """label='target', prim_type='Xform'인 컬렉션 그룹을 탐색함."""
    _is_target = lambda n: n.label == "target" and n.prim_type == "Xform"
    return next(walk_nodes(root, _is_target), None)


def _Resolve_render_size(camera_node: Base_Node) -> tuple[int, int]:
    """카메라 intrinsic에서 렌더 해상도를 취득함. 없으면 기본 1920x1080."""
    _intr = getattr(camera_node, "intrinsic", None)
    if _intr is None:
        return 1920, 1080
    return _intr.width, _intr.height


def _Set_isolated_visibility(
    target_group: Base_Node, active_index: int
) -> None:
    """target 직속 자식 중 active_index만 visible=True, 나머지는 False."""
    for _i, _child in enumerate(target_group.children):
        _child.visible = (_i == active_index)


# ==========================================
# Capture 프로젝트
# ==========================================

class Capture_Project(Project_Template):
    """단일 장면 + target 그룹 순회 기반 다중 패스 오프스크린 렌더링."""

    def __init__(self, config: Render_Config):
        super().__init__("capture")
        self._config = config
        self._pipeline = Render_Pipeline(config)

    def Render_target(
        self, target_group: Base_Node, root: Base_Node,
        camera: Base_Node, width: int, height: int,
    ) -> None:
        """target 그룹 직속 자식을 순회하며 객체별로 N프레임 캡처함."""
        if not self._is_setup_done:
            raise RuntimeError(
                "[ERROR] 'Capture_Project.Render_target()' invoked before '_Setup()' completed."
            )

        if not target_group.children:
            print("[WARN] target 그룹에 자식 노드가 없음. 캡처 스킵.")
            return

        self._pipeline.Setup_headless_context(width, height)

        try:
            _flat_counter = 0
            _base_matrix = camera.local_matrix.copy()

            for _obj_idx, _child in enumerate(target_group.children):
                _Set_isolated_visibility(target_group, _obj_idx)
                _exporter = self._Build_exporter(_child.label)

                print(
                    f"\n[INFO] === [{_obj_idx + 1}/{len(target_group.children)}] "
                    f"{_child.label} ==="
                )

                for _sample_idx in range(self._config.num_samples):
                    camera.local_matrix = (
                        _base_matrix @ Sample_delta_matrix(self._config)
                    )

                    _results = self._pipeline.Execute(root, camera, width, height)

                    _frame_id = (
                        _flat_counter
                        if self._config.output_layout == "flat"
                        else _sample_idx
                    )
                    _extra = {
                        "target_object_label": _child.label,
                        "object_index": _obj_idx,
                        "sample_index": _sample_idx,
                    }
                    _exporter.Save(
                        _frame_id, _results, camera, self._config, _extra
                    )
                    _flat_counter += 1

                    print(
                        f"[INFO]   [{_sample_idx + 1}/{self._config.num_samples}] "
                        f"frame={_frame_id:06d}"
                    )
        finally:
            self._pipeline.Teardown_headless_context()

    def _Build_exporter(self, object_label: str) -> Result_Exporter:
        """output_layout에 따라 객체별 또는 평탄 디렉토리에 익스포터를 구성함."""
        if self._config.output_layout == "per_object":
            return Result_Exporter(self.workspace / object_label)
        return Result_Exporter(self.workspace)


# ==========================================
# 배치 캡처 실행
# ==========================================

def Run_batch_capture(config_path: Path) -> None:
    """Render_Config를 로드하고 target 그룹 순회 기반 캡처를 실행함.

    Args:
        config_path: Render_Config JSON 파일 경로.
    """
    _cfg = Read_from_file(Render_Config, config_path)
    _base_dir = config_path.parent.resolve()

    _scene_path = (_base_dir / _cfg.scene_path).resolve()
    _stage = Stage_Controller()
    _stage.Load(_scene_path)
    Resolve_meshes(_stage.root)

    _root = _stage.root

    _camera = _Find_camera_node(_root, _cfg.camera_label)
    if _camera is None:
        raise ValueError(
            f"[ERROR] 카메라 노드 '{_cfg.camera_label}'을(를) 장면에서 찾을 수 없음."
        )

    _target = _Find_target_group(_root)
    if _target is None:
        raise ValueError(
            "[ERROR] target 그룹(label='target', prim_type='Xform')이 장면에 없음."
        )

    _w, _h = _Resolve_render_size(_camera)

    _project = Capture_Project(_cfg)
    _project._Setup()

    print(f"[INFO] 워크스페이스: {_project.workspace}")
    print(f"[INFO] 장면: {_scene_path}")
    print(f"[INFO] 해상도: {_w}x{_h}")
    print(f"[INFO] target 객체 수: {len(_target.children)}")
    print(f"[INFO] 객체당 샘플 수: {_cfg.num_samples}")
    print(f"[INFO] 출력 레이아웃: {_cfg.output_layout}")

    _project.Render_target(_target, _root, _camera, _w, _h)

    _total = len(_target.children) * _cfg.num_samples
    print(f"\n[INFO] 배치 캡처 완료. 총 {_total}프레임.")


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
