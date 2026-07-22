"""객체 뷰어 — **객체가 편집의 주체다.**

객체는 payload 가 없다(BRANCH). 그런데도 뷰어를 갖는 건, 편집기가 겨누는 게 **객체**이기 때문이다:

- **mask** — 칠하면 프레임의 ``segment`` 에 **그 객체의 라벨**(= obj_id + 1)이 찍힌다. 라벨을 손으로
  고를 일이 없다(객체가 곧 라벨이다).
- **bbox** — 캔버스에서 드래그해 그린다. 그 객체의 ``bbox``(``("region","bbox","xyxy")`` = 코너 4개)가 진실이다.

그래서 "대상 라벨 스핀박스" 같은 게 없다 — 예전 편집기가 객체별 mask 를 따로 들고 저장 때 합치던 것도,
라벨을 손으로 고르던 것도, **객체가 편집 단위**임을 UI 가 몰라서 생긴 우회였다.

무엇을 어떻게 겨누는지는 여기가 아니라 [`_data_view`](../meta_page/view/_data_view.py) 가 정한다 —
그건 **트리 구조**의 일이고(객체 ↔ 프레임의 라벨맵), 뷰어는 트리를 모른다.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLabel, QWidget

from core.schema import Data_Ref

from ._base import BRANCH, Node_viewer, Register


@Register(BRANCH)
class Object_viewer(Node_viewer):
    """객체(BRANCH) — payload 는 없지만 **편집 주체**다 (그 객체의 mask 와 bbox)."""

    EDITABLE = True

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        _cls = ref.Attr("class_id")
        return f"{_cls or '미분류'}  ({len(ref.info)})"

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx=None, on_change=None) -> QWidget | None:
        _l = QLabel("mask 는 칠하고, bbox 는 드래그로 그립니다 — 값은 아래 자식 노드에서 편집.")
        _l.setStyleSheet("color: #888;")
        _l.setWordWrap(True)
        return _l
