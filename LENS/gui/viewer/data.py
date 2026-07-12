"""값 뷰어 — 캔버스에 안 그려지는 것들 (``array`` · ``docs``).

캔버스가 없어도 **볼 자리가 있다**는 게 요점이다. 예전엔 이런 종류가 생기면 붙일 데가 없어 트리에
`array(npy)` 같은 서술자만 뜨고 값은 볼 수 없었다.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtWidgets import QHeaderView, QLabel, QTreeWidgetItem, QVBoxLayout, QWidget

from core.schema import Data_Ref
from gui.widgets import make_tree

from ._base import Node_viewer, Register


@Register("array")
class Array_viewer(Node_viewer):
    """npy 배열 — 모양·dtype·통계 요약 (히트맵은 추후)."""

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        if not isinstance(value, np.ndarray):
            return "array (로드 실패)"
        return f"array {tuple(value.shape)} {value.dtype}"

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx=None, on_change=None) -> QWidget | None:
        if not isinstance(value, np.ndarray):
            return QLabel("array — 로드 실패")
        _text = (f"shape={tuple(value.shape)}  dtype={value.dtype}\n"
                 f"min={value.min():.4g}  max={value.max():.4g}  mean={value.mean():.4g}")
        _lbl = QLabel(_text)
        _lbl.setStyleSheet("font-family: monospace;")
        return _lbl


@Register("docs")
class Docs_viewer(Node_viewer):
    """중첩 구조(yaml/json) — 트리로 펼친다 (id_map 등)."""

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        if isinstance(value, dict):
            return f"docs · {len(value)} entries"
        if isinstance(value, list):
            return f"docs · [{len(value)}]"
        return "docs"

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx=None, on_change=None) -> QWidget | None:
        _w = QWidget()
        _lay = QVBoxLayout(_w)
        _lay.setContentsMargins(0, 0, 0, 0)
        _tree = make_tree(headers=["key", "value"],
                          resize=[QHeaderView.ResizeToContents, QHeaderView.Stretch])
        _fill(_tree.invisibleRootItem(), value)
        _lay.addWidget(_tree)
        return _w


def _fill(parent: QTreeWidgetItem, value: Any, key: str = "") -> None:
    """dict/list 를 재귀로 트리에 펼친다 (말단은 한 줄)."""
    if isinstance(value, dict):
        _node = QTreeWidgetItem([str(key), f"{{{len(value)}}}"]) if key != "" else parent
        for _k, _v in value.items():
            _fill(_node, _v, str(_k))
        if _node is not parent:
            parent.addChild(_node)
            _node.setExpanded(True)
    elif isinstance(value, list):
        _node = QTreeWidgetItem([str(key), f"[{len(value)}]"])
        for _i, _v in enumerate(value):
            _fill(_node, _v, str(_i))
        parent.addChild(_node)
    else:
        parent.addChild(QTreeWidgetItem([str(key), str(value)]))
