from __future__ import annotations

from viewport.utils.selection import Selection_Controller


class _Renderer:
    def __init__(self, id_map):
        self._id_map = id_map

    def Render_id_pass(self, root_node, camera):
        return self._id_map


def test_selection_pick_returns_node_from_color_id(monkeypatch):
    _node = object()
    _renderer = _Renderer({(1, 2, 3): _node})
    _selection = Selection_Controller()

    monkeypatch.setattr(
        "viewport.utils.selection.glReadPixels",
        lambda *args, **kwargs: bytes((1, 2, 3)),
    )

    _picked = _selection.Pick(10, 20, object(), object(), _renderer)

    assert _picked is _node
    assert _selection.selected_node is _node


def test_selection_pick_clears_state_when_readback_is_not_bytes(monkeypatch):
    _selection = Selection_Controller()
    _selection.selected_node = object()
    _renderer = _Renderer({})

    monkeypatch.setattr(
        "viewport.utils.selection.glReadPixels",
        lambda *args, **kwargs: (0, 0, 0),
    )

    _picked = _selection.Pick(10, 20, object(), object(), _renderer)

    assert _picked is None
    assert _selection.selected_node is None
