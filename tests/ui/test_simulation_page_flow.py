from __future__ import annotations

from pathlib import Path

from spatial_toolbox.scene import Controller
from spatial_toolbox.simulation import Sim_Config
from ui.event_bus import EVENT_BUS
from ui.panels.simulation.page import Simulation_Page


def test_simulation_page_select_config_enables_run(monkeypatch, qapp, tmp_path):
    _cfg = tmp_path / "sim.json"
    _cfg.write_text("{}", encoding="utf-8")
    _page = Simulation_Page(Controller())

    monkeypatch.setattr(
        "ui.panels.simulation.page.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(_cfg), "JSON Files (*.json)"),
    )

    _page._select_config()

    assert _page.config_path == _cfg
    assert _page.btn_run.isEnabled() is True
    assert _page.config_path_label.text() == f"Render Config: {_cfg}"


def test_simulation_page_generate_config_saves_and_enables_run(monkeypatch, qapp, tmp_path):
    class _Dummy_Dialog:
        def __init__(self, stage, parent=None):
            pass

        def exec(self):
            from PySide6.QtWidgets import QDialog
            return QDialog.DialogCode.Accepted

        def Get_config(self):
            return Sim_Config(num_samples=3)

    monkeypatch.setattr("ui.panels.simulation.page.Generate_Config_Dialog", _Dummy_Dialog)
    monkeypatch.setattr(
        "ui.panels.simulation.page.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "render_config.json"), "JSON Files (*.json)"),
    )
    monkeypatch.setattr("spatial_toolbox.simulation.Sim_Config.Write_to", lambda *args, **kwargs: None)

    _page = Simulation_Page(Controller())
    _page.current_scene_path = tmp_path / "scene.usda"
    _page._generate_config()

    assert _page.config_path == tmp_path / "render_config.json"
    assert _page.btn_run.isEnabled() is True
    assert _page.config_path_label.text() == f"Render Config: {tmp_path / 'render_config.json'}"


def test_simulation_page_generate_config_requires_scene_path(monkeypatch, qapp):
    _warnings: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "ui.panels.simulation.page.QMessageBox.warning",
        lambda parent, title, text: _warnings.append((title, text)),
    )

    _page = Simulation_Page(Controller())
    _page._generate_config()

    assert _warnings
    assert "scene 경로" in _warnings[0][1]


def test_simulation_page_tracks_scene_path_from_event(qapp, tmp_path):
    _page = Simulation_Page(Controller())
    _scene = tmp_path / "scene.usda"
    EVENT_BUS.scene_path_changed.emit(str(_scene))
    assert _page.current_scene_path == _scene


def test_simulation_page_run_disables_controls_and_starts_worker(monkeypatch, qapp, tmp_path):
    _events: dict[str, object] = {}

    class _Dummy_Signal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

    class _Dummy_Worker:
        def __init__(self, config_path: Path):
            _events["config_path"] = config_path
            self.progress = _Dummy_Signal()
            self.finished_sig = _Dummy_Signal()

        def start(self):
            _events["started"] = True

    monkeypatch.setattr("ui.panels.simulation.page.Simulation_Worker", _Dummy_Worker)

    _page = Simulation_Page(Controller())
    _page.config_path = tmp_path / "sim.json"
    _page.btn_run.setEnabled(True)

    _page._run_simulation()

    assert _events["config_path"] == _page.config_path
    assert _events["started"] is True
    assert _page.btn_run.isEnabled() is False
    assert _page.btn_generate_config.isEnabled() is False
    assert _page.btn_select_config.isEnabled() is False
    assert _page.status_label.text() == "시뮬레이션 초기화 중..."

def test_simulation_page_tracks_scene_path_from_event_updates_label(qapp, tmp_path):
    _page = Simulation_Page(Controller())
    _scene = tmp_path / "scene.usda"
    EVENT_BUS.scene_path_changed.emit(str(_scene))
    assert _page.current_scene_path == _scene
    assert _page.scene_path_label.text() == f"Scene: {_scene}"
