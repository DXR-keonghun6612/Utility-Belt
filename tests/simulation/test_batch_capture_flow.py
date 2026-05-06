from __future__ import annotations

from pathlib import Path

import simulation as simulation_module
from simulation.engine import Run_batch_capture, _Read_sim_config


def test_simulation_package_reexports_capture_entrypoints():
    _public = simulation_module.__all__
    assert "Sim_Config" in _public
    assert "Blender_Capture_Engine" in _public
    assert "Result_Exporter" in _public


def test_read_sim_config_restores_sim_config_from_json(tmp_path):
    _cfg_path = tmp_path / "config.json"
    _cfg_path.write_text(
        '{"scene_path":"scene.json","target_label":"target","camera_labels":["main_camera"],"num_samples":2}',
        encoding="utf-8",
    )

    _cfg = _Read_sim_config(_cfg_path)

    assert _cfg.scene_path == "scene.json"
    assert _cfg.camera_labels == ["main_camera"]
    assert _cfg.num_samples == 2


def test_run_batch_capture_loads_config_imports_scene_and_calls_engine(monkeypatch, tmp_path):
    _scene_path = tmp_path / "demo_scene.json"
    _scene_path.write_text("{}", encoding="utf-8")

    _captured: dict[str, object] = {}

    class _Config:
        scene_path = str(_scene_path)

    class _Fake_Controller:
        def __init__(self):
            _captured["scene_instance"] = self

        def Import(self, path):
            _captured["import_path"] = path

    class _Fake_Engine:
        def __init__(self, channels=None):
            _captured["channels"] = channels

        def Capture(self, scene, config, output_dir, progress_callback=None):
            _captured["capture_scene"] = scene
            _captured["capture_config"] = config
            _captured["capture_output_dir"] = output_dir
            _captured["capture_progress_callback"] = progress_callback

    monkeypatch.setattr("simulation.engine._Read_sim_config", lambda path: _Config())
    monkeypatch.setattr("simulation.engine.Controller", _Fake_Controller)
    monkeypatch.setattr("simulation.engine.Blender_Capture_Engine", _Fake_Engine)

    _progress = lambda current, total, message: None
    Run_batch_capture(Path("config.json"), progress_callback=_progress)

    assert _captured["import_path"] == _scene_path.resolve()
    assert _captured["channels"] == ["rgb", "depth", "normal", "segmentation"]
    assert _captured["capture_scene"] is _captured["scene_instance"]
    assert _captured["capture_output_dir"] == _scene_path.parent / _scene_path.stem
    assert _captured["capture_progress_callback"] is _progress


def test_run_batch_capture_uses_scene_stem_as_output_dir(monkeypatch, tmp_path):
    _scene_path = tmp_path / "nested" / "sample_scene.json"
    _scene_path.parent.mkdir(parents=True)
    _scene_path.write_text("{}", encoding="utf-8")

    _outputs: list[Path] = []

    class _Config:
        scene_path = str(_scene_path)

    class _Fake_Controller:
        def Import(self, path):
            return None

    class _Fake_Engine:
        def __init__(self, channels=None):
            _outputs.append(channels)

        def Capture(self, scene, config, output_dir, progress_callback=None):
            _outputs.append(output_dir)

    monkeypatch.setattr("simulation.engine._Read_sim_config", lambda path: _Config())
    monkeypatch.setattr("simulation.engine.Controller", _Fake_Controller)
    monkeypatch.setattr("simulation.engine.Blender_Capture_Engine", _Fake_Engine)

    Run_batch_capture(Path("render_cfg.json"))

    assert _outputs == [["rgb", "depth", "normal", "segmentation"], _scene_path.parent / "sample_scene"]
