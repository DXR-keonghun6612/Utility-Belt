"""시뮬레이션(렌더링 파이프라인) 엔동 로직.

이 엔진은 CLI와 UI 양쪽에서 모두 호출될 수 있도록 독립적으로 구현됨.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import numpy as np

import python_toolbox.project as _pt
from python_toolbox.project import Project_Template, Read_from_file

from spatial_toolbox.scene.node import Base_Node
from spatial_toolbox.scene.node.utils import walk_nodes
from spatial_toolbox.scene import Controller as Stage_Controller
from simulation.config import Render_Config, Sample_delta_matrix, Sample_translation
from simulation.pipeline import Render_Pipeline
from simulation.exporter import Result_Exporter

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

    def __init__(self, project_name: str, config: Render_Config):
        super().__init__(project_name)
        self._config = config
        self._pipeline = Render_Pipeline(config)

    def Render_target(
        self, target_group: Base_Node, root: Base_Node,
        camera: Base_Node, width: int, height: int,
        progress_callback: Callable[[int, int, str], None] | None = None
    ) -> None:
        """target 그룹 직속 자식을 순회하며 객체별로 N프레임 캡처함."""
        if not self._is_setup_done:
            raise RuntimeError(
                "[ERROR] 'Capture_Project.Render_target()' invoked before '_Setup()' completed."
            )

        if not target_group.children:
            msg = "[WARN] target 그룹에 자식 노드가 없음. 캡처 스킵."
            if progress_callback:
                progress_callback(0, 0, msg)
            return

        self._pipeline.Setup_headless_context(width, height)

        total_frames = len(target_group.children) * self._config.num_samples

        try:
            _flat_counter = 0
            _base_matrix = camera.local_matrix.copy()
            # 광원 기준 위치(방향광 w 포함)를 스냅샷하여 델타를 xyz 에만 적용
            _light_base = list(self._config.light_position)

            for _obj_idx, _child in enumerate(target_group.children):
                _Set_isolated_visibility(target_group, _obj_idx)
                _exporter = self._Build_exporter(_child.label)

                # 객체 base 스냅샷 — 샘플마다 이 행렬에 델타를 덮어씌움
                _obj_base = _child.local_matrix.copy()

                msg = f"렌더링 중: {_child.label} ({_obj_idx + 1}/{len(target_group.children)})"
                if progress_callback:
                    progress_callback(_flat_counter, total_frames, msg)

                for _sample_idx in range(self._config.num_samples):
                    camera.local_matrix = (
                        _base_matrix @ Sample_delta_matrix(self._config.cam)
                    )
                    _child.local_matrix = (
                        _obj_base @ Sample_delta_matrix(self._config.obj)
                    )

                    # 광원 기준 + xyz 델타. w 성분은 원본 유지 (방향광 0 / 점광 1).
                    _dx, _dy, _dz = Sample_translation(self._config.light)
                    self._pipeline.Set_light_position([
                        _light_base[0] + _dx,
                        _light_base[1] + _dy,
                        _light_base[2] + _dz,
                        _light_base[3],
                    ])

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
                        "segmentation_id_map": self._pipeline.Get_segmentation_id_map(),
                    }
                    _exporter.Save(
                        _frame_id, _results, camera, self._config, _extra
                    )
                    _flat_counter += 1

                    if progress_callback:
                        progress_callback(_flat_counter, total_frames, f"프레임 저장 완료: {_frame_id:06d}")
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

def Run_batch_capture(config_path: Path, progress_callback: Callable[[int, int, str], None] | None = None) -> None:
    """Render_Config를 로드하고 target 그룹 순회 기반 캡처를 실행함.

    Args:
        config_path: Render_Config JSON 파일 경로.
        progress_callback: 렌더링 진행률을 알리는 콜백 함수. UI 및 CLI용.
    """
    _cfg = Read_from_file(Render_Config, config_path)
    _scene_path = Path(_cfg.scene_path).resolve()

    _base_dir = _scene_path.parent

    # 결과 루트를 장면 파일 디렉토리로 전환. Project_Template 은
    # {RESULT_ROOT}/{project_name}/{run_id} 로 workspace 를 구성하므로
    # project_name 에 장면 파일 stem 을 주입하면 <scene_dir>/<stem>/<run_id>/ 가 됨.
    _pt.RESULT_ROOT = str(_base_dir)

    # 재현성 — 시드가 설정되어 있으면 전역 RNG에 주입
    if _cfg.seed is not None:
        np.random.seed(_cfg.seed)

    _stage = Stage_Controller()
    _stage.Load(_scene_path)

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

    _project = Capture_Project(_scene_path.stem, _cfg)
    _project._Setup()

    msg = (f"[INFO] 캡처 준비 완료: 해상도 {_w}x{_h}, "
           f"객체 수 {len(_target.children)}, 샘플 수 {_cfg.num_samples}")
    if progress_callback:
        progress_callback(0, len(_target.children) * _cfg.num_samples, msg)

    _project.Render_target(_target, _root, _camera, _w, _h, progress_callback)
