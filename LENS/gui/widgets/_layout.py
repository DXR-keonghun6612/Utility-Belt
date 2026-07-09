"""레이아웃 / 위젯 수명 헬퍼 — 위젯을 떼고 파괴하거나 레이아웃을 재배치한다."""

from __future__ import annotations

from PySide6.QtWidgets import QToolButton, QWidget


def move_buttons(on_up, on_down, on_remove) -> list[QToolButton]:
    """위/아래/삭제 툴버튼 ``[▲, ▼, ✕]`` 을 만들어 콜백에 연결해 돌려준다.

    ``reorder``/``drop`` 로 순서·수명을 관리하는 리스트 항목의 헤더에 붙인다.

    Args:
        on_up: ▲ 클릭 콜백.
        on_down: ▼ 클릭 콜백.
        on_remove: ✕ 클릭 콜백.

    Returns:
        연결된 ``QToolButton`` 세 개 ``[▲, ▼, ✕]``.
    """
    _result = []
    for _txt, _slot in (("▲", on_up), ("▼", on_down), ("✕", on_remove)):
        _b = QToolButton()
        _b.setText(_txt)
        _b.clicked.connect(_slot)
        _result.append(_b)
    return _result


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
