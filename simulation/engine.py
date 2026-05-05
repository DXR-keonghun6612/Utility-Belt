from __future__ import annotations

from pathlib import Path
from typing import Callable

from python_toolbox.project import Read_from_file
from spatial_toolbox.scene import Controller
from spatial_toolbox.simulation import Blender_Capture_Engine, Sim_Config


def Run_batch_capture(
    config_path: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> None:
    _cfg = Read_from_file(Sim_Config, config_path)
    _scene_path = Path(_cfg.scene_path).resolve()

    _scene = Controller()
    _scene.Import(_scene_path)

    _output_dir = _scene_path.parent / _scene_path.stem

    _engine = Blender_Capture_Engine()
    _engine.Capture(
        scene=_scene,
        config=_cfg,
        output_dir=_output_dir,
        progress_callback=progress_callback,
    )
