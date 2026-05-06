from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ui.sidebar.container import Page_Config, Sidebar_Container


def test_sidebar_toggle_opens_requested_page_and_sets_width(qapp):
    _page_a = QWidget()
    _page_b = QWidget()
    _sidebar = Sidebar_Container([
        Page_Config("a", "A", "Page A", _page_a),
        Page_Config("b", "B", "Page B", _page_b),
    ])

    _sidebar._Toggle_panel("a")

    assert _sidebar.side_bar.isHidden() is False
    assert _sidebar.side_bar.currentWidget() is _page_a
    assert _sidebar.width() == 350
    assert _sidebar.nav_buttons["a"].isChecked() is True
    assert _sidebar.nav_buttons["b"].isChecked() is False


def test_sidebar_toggle_same_page_closes_panel(qapp):
    _sidebar = Sidebar_Container([
        Page_Config("a", "A", "Page A", QWidget()),
    ])

    _sidebar._Toggle_panel("a")
    _sidebar._Toggle_panel("a")

    assert _sidebar.side_bar.isHidden() is True
    assert _sidebar.width() == 50
    assert _sidebar.nav_buttons["a"].isChecked() is False


def test_sidebar_switches_active_page_without_closing(qapp):
    _page_a = QWidget()
    _page_b = QWidget()
    _sidebar = Sidebar_Container([
        Page_Config("a", "A", "Page A", _page_a),
        Page_Config("b", "B", "Page B", _page_b),
    ])

    _sidebar._Toggle_panel("a")
    _sidebar._Toggle_panel("b")

    assert _sidebar.side_bar.isHidden() is False
    assert _sidebar.side_bar.currentWidget() is _page_b
    assert _sidebar.nav_buttons["a"].isChecked() is False
    assert _sidebar.nav_buttons["b"].isChecked() is True
