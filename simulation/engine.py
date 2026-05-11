"""캡처 CLI 진입점 및 배치 렌더링 엔진."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal

from python_toolbox.file import Read_from
from spatial_toolbox.scene import Controller
from spatial_toolbox.simulation import (
    Blender_Capture_Engine,
    OpenGL_Capture_Engine,
    Sim_Config,
)

Render_Profile = Literal["blender", "opengl"]
Context_Path = Literal["auto", "egl", "embedded"]

Progress_Callback = Callable[[int, int, str], None]


def _Read_sim_config(config_path: Path) -> Sim_Config:
    _is_ok, _data = Read_from(config_path)
    if not _is_ok:
        raise ValueError(f"failed to read config file: {config_path}")
    if not isinstance(_data, dict):
        raise ValueError(f"config file must contain a mapping: {config_path}")
    return Sim_Config(**_data)


def _Build_engine(
    profile: Render_Profile,
    width: int,
    height: int,
    context_type: Context_Path,
    channels: list[str] | None,
):
    if profile == "opengl":
        return OpenGL_Capture_Engine(
            width=width,
            height=height,
            context_type=context_type,
            channels=channels,
        )
    return Blender_Capture_Engine(channels=channels)


def Run_batch_capture(
    config_path: Path,
    profile: Render_Profile = "blender",
    width: int = 640,
    height: int = 480,
    context_type: Context_Path = "auto",
    output_dir: Path | None = None,
    channels: list[str] | None = None,
    progress_callback: Progress_Callback | None = None,
) -> None:
    if progress_callback is not None:
        progress_callback(0, 0, "Config 읽는 중...")

    _cfg = _Read_sim_config(config_path)
    _scene_path = Path(_cfg.scene_path).resolve()
    _output_dir = output_dir if output_dir is not None else config_path.parent / config_path.stem

    if progress_callback is not None:
        progress_callback(0, 0, "Scene 불러오는 중...")

    _scene = Controller()
    _scene.Import(str(_scene_path))

    if progress_callback is not None:
        progress_callback(0, 0, "Simulation 준비 중...")

    _engine = _Build_engine(profile, width, height, context_type, channels)
    _engine.Capture(_scene, _cfg, _output_dir, progress_callback)
