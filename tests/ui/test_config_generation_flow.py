from __future__ import annotations

import numpy as np

from spatial_toolbox.scene import Controller
from spatial_toolbox.scene.node import Camera, Group
from ui.panels.simulation.dialog import Generate_Config_Dialog


def _append_child(parent, child):
    child.Set_parent(parent)
    parent.children.append(child)


def _build_stage():
    _stage = Controller()
    _target = Group(label="target")
    _other = Group(label="other")
    _camera = Camera(label="main_camera")
    _append_child(_stage.root, _target)
    _append_child(_stage.root, _other)
    _append_child(_stage.root, _camera)
    return _stage


def test_generate_config_dialog_populates_target_and_camera_choices(qapp):
    _dialog = Generate_Config_Dialog(_build_stage())

    assert _dialog.cb_target.count() == 2
    assert _dialog.cb_camera.count() == 1
    assert _dialog.cb_target.currentText() == "target"
    assert _dialog.cb_camera.currentText() == "main_camera"


def test_generate_config_dialog_builds_sim_config_from_widget_state(qapp):
    _dialog = Generate_Config_Dialog(_build_stage())
    _dialog.spin_samples.setValue(7)
    _dialog.cb_layout.setCurrentText("flat")
    _dialog.chk_seed.setChecked(True)
    _dialog.spin_seed.setValue(99)
    _dialog.chk_physics_drop.setChecked(True)
    _dialog.spin_floor_z.setValue(-0.25)
    _dialog.spin_settle_frames.setValue(48)
    _dialog.cb_collision_shape.setCurrentText("BOX")
    _dialog.spin_mass.setValue(2.5)
    _dialog.spin_friction.setValue(0.8)
    _dialog.spin_restitution.setValue(0.1)
    _dialog.spin_steps_per_second.setValue(240)
    _dialog.spin_solver_iterations.setValue(30)
    _dialog.spin_linear_damping.setValue(0.2)
    _dialog.spin_angular_damping.setValue(0.3)
    _dialog.chk_ground_plane.setChecked(False)
    _dialog.chk_collide_with_scene.setChecked(False)

    _dialog._obj_controls["tx"][1].setValue(1.5)
    _dialog._cam_controls["ry"][0].setChecked(True)
    _dialog._cam_controls["ry"][1].setValue(-45.0)
    _dialog._cam_controls["ry"][2].setValue(45.0)

    _cfg = _dialog.Get_config()

    assert _cfg.target_label == "target"
    assert _cfg.camera_labels == ["main_camera"]
    assert _cfg.num_samples == 7
    assert _cfg.output_layout == "flat"
    assert _cfg.seed == 99
    assert _cfg.obj.tx == 1.5
    assert np.allclose(_cfg.cam.ry, [np.radians(-45.0), np.radians(45.0)])
    assert _cfg.physics_drop.enabled is True
    assert _cfg.physics_drop.floor_z == -0.25
    assert _cfg.physics_drop.settle_frames == 48
    assert _cfg.physics_drop.collision_shape == "BOX"
    assert _cfg.physics_drop.mass == 2.5
    assert _cfg.physics_drop.friction == 0.8
    assert _cfg.physics_drop.restitution == 0.1
    assert _cfg.physics_drop.steps_per_second == 240
    assert _cfg.physics_drop.solver_iterations == 30
    assert _cfg.physics_drop.linear_damping == 0.2
    assert _cfg.physics_drop.angular_damping == 0.3
    assert _cfg.physics_drop.use_ground_plane is False
    assert _cfg.physics_drop.collide_with_scene is False
