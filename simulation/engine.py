from __future__ import annotations

from pathlib import Path
from typing import Callable

from python_toolbox.file import Read_from
from spatial_toolbox.render import DEPTH, NORMAL, RGB, SEGMENTATION
from spatial_toolbox.scene import Controller
from spatial_toolbox.scene.node.utils import walk_nodes
from spatial_toolbox.simulation import Blender_Capture_Engine, Sim_Config

_DEFAULT_CAPTURE_CHANNELS = [RGB, DEPTH, NORMAL, SEGMENTATION]


def _Read_sim_config(config_path: Path) -> Sim_Config:
    _is_ok, _data = Read_from(config_path)
    if not _is_ok:
        raise ValueError(f"failed to read config file: {config_path}")
    if not isinstance(_data, dict):
        raise ValueError(f"config file must contain a mapping: {config_path}")
    return Sim_Config(**_data)


def Run_batch_capture(
    config_path: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> None:
    if progress_callback is not None:
        progress_callback(0, 0, "Config 읽는 중...")

    _cfg = _Read_sim_config(config_path)
    _scene_path = Path(_cfg.scene_path).resolve()

    if progress_callback is not None:
        progress_callback(0, 0, "Scene 불러오는 중...")

    _scene = Controller()
    _scene.Import(_scene_path)

    _total = 0
    if hasattr(_scene, "root") and hasattr(_cfg, "target_label") and hasattr(_cfg, "num_samples"):
        _target = next(
            walk_nodes(
                _scene.root,
                lambda n: n.label == _cfg.target_label and n.prim_type == "Xform",
            ),
            None,
        )
        if _target is not None and hasattr(_target, "children"):
            _total = len(_target.children) * _cfg.num_samples
    if progress_callback is not None:
        if _total > 0:
            progress_callback(0, _total, "Simulation 준비 중...")
        else:
            progress_callback(0, 0, "Simulation 준비 중...")

    _output_dir = _scene_path.parent / _scene_path.stem

    _engine = Blender_Capture_Engine(channels=_DEFAULT_CAPTURE_CHANNELS)
    _engine.Capture(
        scene=_scene,
        config=_cfg,
        output_dir=_output_dir,
        progress_callback=progress_callback,
    )
