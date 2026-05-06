from __future__ import annotations

import numpy as np

from spatial_toolbox.scene.node import Camera, Mesh
from viewport.renderer import Scene_Renderer


def test_scene_renderer_render_frame_runs_camera_lighting_grid_and_node_pass(monkeypatch):
    _renderer = Scene_Renderer()
    _events: list[object] = []
    _camera = type("CameraStub", (), {"Apply_view": lambda self: _events.append("apply_view")})()

    monkeypatch.setattr("viewport.renderer.glClearColor", lambda *args: _events.append("clear_color"))
    monkeypatch.setattr("viewport.renderer.glClear", lambda *args: _events.append("clear"))
    monkeypatch.setattr("viewport.renderer.glPolygonMode", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glDisable", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glEnable", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glColor3f", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.walk_nodes", lambda root, pred: ["mesh_a", "mesh_b"])

    _renderer._renderer = type(
        "OpenGLStub",
        (),
        {"Apply_lighting": lambda self: _events.append("lighting")},
    )()
    _renderer._grid = type("GridStub", (), {"Draw": lambda self: _events.append("grid")})()
    monkeypatch.setattr(_renderer, "_On_main_node", lambda node: _events.append(node))

    _renderer.Render_frame(object(), _camera, None)

    assert _events[:4] == ["clear_color", "clear", "apply_view", "lighting"]
    assert "grid" in _events
    assert "mesh_a" in _events and "mesh_b" in _events


def test_scene_renderer_clear_resources_delegates_to_backend():
    _renderer = Scene_Renderer()
    _events: list[str] = []
    _renderer._renderer = type(
        "OpenGLStub",
        (),
        {"Clear_resources": lambda self: _events.append("clear_resources")},
    )()

    _renderer.Clear_resources()

    assert _events == ["clear_resources"]


def test_scene_renderer_render_id_pass_resets_id_state_and_returns_id_map(monkeypatch):
    _renderer = Scene_Renderer()
    _mesh = Mesh(label="mesh", source_key="asset.obj")
    _mesh.local_rigid = np.eye(4, dtype=np.float32)
    _events: list[str] = []

    monkeypatch.setattr("viewport.renderer.glClearColor", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glClear", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glDisable", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glEnable", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glPushMatrix", lambda: None)
    monkeypatch.setattr("viewport.renderer.glPopMatrix", lambda: None)
    monkeypatch.setattr("viewport.renderer.glMultMatrixf", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glFlush", lambda: None)
    monkeypatch.setattr("viewport.renderer.walk_nodes", lambda root, pred: [_mesh])
    monkeypatch.setattr(
        "spatial_toolbox.scene.ASSET_CACHE.Get",
        lambda key, is_hold=True: type("AssetStub", (), {"geometry": object()})(),
    )

    _renderer._renderer = type(
        "OpenGLStub",
        (),
        {
            "id_map": {(9, 9, 9): _mesh},
            "Reset_id_state": lambda self: _events.append("reset"),
            "Draw": lambda self, **kwargs: _events.append("draw"),
        },
    )()
    _camera = type("CameraStub", (), {"Apply_view": lambda self: _events.append("apply_view")})()

    _id_map = _renderer.Render_id_pass(object(), _camera)

    assert _events[0] == "apply_view"
    assert "reset" in _events
    assert "draw" in _events
    assert _id_map == {(9, 9, 9): _mesh}


def test_scene_renderer_skips_hidden_node_in_main_and_id_pass(monkeypatch):
    _renderer = Scene_Renderer()
    _mesh = Mesh(label="mesh", source_key="asset.obj", visible=False)
    _mesh.local_rigid = np.eye(4, dtype=np.float32)
    _events: list[str] = []

    monkeypatch.setattr("viewport.renderer.glClearColor", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glClear", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glDisable", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glEnable", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glPolygonMode", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glColor3f", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glPushMatrix", lambda: None)
    monkeypatch.setattr("viewport.renderer.glPopMatrix", lambda: None)
    monkeypatch.setattr("viewport.renderer.glMultMatrixf", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.glFlush", lambda: None)
    monkeypatch.setattr("viewport.renderer.glLineWidth", lambda *args: None)
    monkeypatch.setattr("viewport.renderer.walk_nodes", lambda root, pred: [_mesh] if pred(_mesh) else [])
    monkeypatch.setattr(
        "spatial_toolbox.scene.ASSET_CACHE.Get",
        lambda key, is_hold=True: type("AssetStub", (), {"geometry": object()})(),
    )

    _renderer._renderer = type(
        "OpenGLStub",
        (),
        {
            "id_map": {},
            "Apply_lighting": lambda self: None,
            "Reset_id_state": lambda self: _events.append("reset"),
            "Draw": lambda self, **kwargs: _events.append("draw"),
        },
    )()
    _renderer._grid = type("GridStub", (), {"Draw": lambda self: None})()
    _camera = type("CameraStub", (), {"Apply_view": lambda self: None})()

    _renderer.Render_frame(object(), _camera, None)
    _renderer.Render_id_pass(object(), _camera)

    assert _events == ["reset"]
