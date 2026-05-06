from __future__ import annotations

import numpy as np

from viewport.orbit_cam import Orbit_Camera


def test_orbit_camera_rotate_updates_yaw_and_pitch():
    _camera = Orbit_Camera()

    _camera.Rotate(dx=10.0, dy=-20.0)

    assert _camera.yaw == 40.0
    assert _camera.pitch == 40.0


def test_orbit_camera_pan_moves_target_in_view_plane():
    _camera = Orbit_Camera()
    _before = _camera.target.copy()

    _camera.Pan(dx=10.0, dy=-5.0)

    assert np.allclose(_camera.target, _before) is False


def test_orbit_camera_zoom_to_cursor_reduces_distance_and_shifts_target():
    _camera = Orbit_Camera()
    _before_target = _camera.target.copy()
    _before_distance = _camera.distance

    _camera.Zoom_to_cursor(delta=2.0, ndc_x=0.5, ndc_y=-0.25, aspect=16.0 / 9.0)

    assert _camera.distance < _before_distance
    assert np.allclose(_camera.target, _before_target) is False
