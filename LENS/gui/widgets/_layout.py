"""레이아웃 / 위젯 수명 헬퍼 — 위젯을 떼고 파괴하거나 레이아웃을 재배치한다."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def drop(*widgets: QWidget) -> None:
    """위젯을 부모에서 떼고 삭제를 예약한다.

    ``setParent(None)`` 로 분리한 뒤 ``deleteLater()`` 로 Qt 이벤트 루프에 파괴를 맡긴다.

    Args:
        *widgets: 제거할 위젯들.
    """
    for _w in widgets:
        _w.setParent(None)
        _w.deleteLater()


def reorder(layout, widgets, *, stretch: bool = False) -> None:
    """레이아웃을 비우고 ``widgets`` 를 순서대로 다시 채운다 (위젯은 파괴하지 않음).

    Args:
        layout: 재배치 대상 레이아웃.
        widgets: 새 순서대로 추가할 위젯 시퀀스.
        stretch: True면 끝에 신축 스페이서를 둬 위젯들을 위로 밀착시킨다.
    """
    while layout.count():
        _item = layout.takeAt(0)
        if _item.widget() is not None:
            _item.widget().setParent(None)
    for _w in widgets:
        layout.addWidget(_w)
    if stretch:
        layout.addStretch(1)
