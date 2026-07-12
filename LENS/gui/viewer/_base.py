"""뷰어 계약 + 레지스트리 — LEAF 의 handler type 이 **어떻게 보이는가**를 정한다.

core 의 ``HANDLER_REGISTRY`` 와 **짝**이다: handler 가 "이 값을 어떻게 디스크에 담나"를 정하면, 뷰어는
"이 값을 어떻게 화면에 그리고 고치나"를 정한다. 그래서 **새 handler 를 떨구면 뷰어 하나만 더하면
UI 가 따라온다.** 예전엔 새 종류가 생겨도 붙일 자리가 없었다 — frame leaf·객체·params 를 각각 다른
패널이 **하드코딩해** 그렸고(같은 재귀 타입인데), 그래서 순서도 확장성도 없었다.

한 노드는 두 가지로 보인다 (해당되는 것만 구현한다):

- **layer** — 캔버스에 겹쳐 그릴 raster. 노드 트리의 **체크박스가 표시 여부**다. (image·segmap·rle)
- **panel** — 선택했을 때 뜨는 값 편집 위젯. (attr·array·docs)

**편집기는 여기 없다.** 한때 뷰어가 편집 툴바(``tools()``)를 만들어 냈는데, 그건 편집이 타입마다 다른
일인 척한 것이다. 실제로 편집 대상은 언제나 **라스터**고 객체는 그 안의 **라벨**이다 — 즉 편집은
타입별이 아니라 **구조적**이다. 그래서 편집기는 [`_raster_edit.Mask_editor`](_raster_edit.py) 하나뿐이고
**앱에 하나만 산다**(`Data_view` 가 소유). 뷰어는 ``EDITABLE`` 로 "이 노드를 조준할 수 있다"만 말한다.
"""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
from PySide6.QtWidgets import QWidget

from core.schema import Data_Ref

#: BRANCH(컨테이너) 뷰어의 등록 key — LEAF 는 handler key 로, BRANCH 는 이걸로 찾는다.
#: 객체는 payload 가 없지만 **편집 주체**다(그 객체의 mask 와 bbox 를 고친다) — 그래서 뷰어를 가질 수 있다.
BRANCH = "__branch__"

VIEWERS: dict[str, type["Node_viewer"]] = {}   # 등록 key → 뷰어 (하나가 여러 타입을 맡을 수 있다)


def Register(*types: str):
    """뷰어를 handler type 에 등록하는 데코레이터 (``@Register("image", "segmap")``)."""
    def _deco(cls: type["Node_viewer"]) -> type["Node_viewer"]:
        cls.TYPES = types
        for _t in types:
            if _t in VIEWERS:
                raise KeyError(f"type '{_t}' 뷰어가 이미 등록됨: {VIEWERS[_t].__name__}")
            VIEWERS[_t] = cls
        return cls
    return _deco


def Viewer_for(ref: Data_Ref) -> type["Node_viewer"] | None:
    """노드의 뷰어 — LEAF 는 handler key 로, BRANCH 는 ``BRANCH`` key 로 (없으면 None)."""
    return VIEWERS.get(ref.format[0] if ref.format else BRANCH)


class Node_viewer:
    """한 노드 종류를 **보여주는** 법. 상태가 없어 ``classmethod`` 로 부른다.

    뷰어는 **payload 만 본다** — 이미 디코드된 값을 받고, 경로도 store 도 모른다(그건 store 의 일이다).
    """

    TYPES: ClassVar[tuple[str, ...]] = ()

    #: 캔버스에 그릴 수 있나 — 노드 트리가 **체크박스를 붙일지** 이걸로 정한다.
    RASTER: ClassVar[bool] = False
    #: 캔버스 편집기가 **조준할 수 있나** — 선택하면 `Mask_editor` 가 이 노드를 겨눈다.
    #: 무엇을 겨누는지는 구조가 정한다: 객체(BRANCH)면 프레임의 라벨맵 + 그 객체의 라벨,
    #: 이진 mask leaf 면 그 라스터 자체.
    EDITABLE: ClassVar[bool] = False

    @classmethod
    def layer(cls, value: Any, ref: Data_Ref) -> np.ndarray | None:
        """캔버스에 겹칠 raster — ``(H, W)`` 이진/라벨 mask 또는 ``(H, W, 3)`` BGR (없으면 None).

        ``RASTER`` 뷰어만 의미가 있다. 체크된 노드들의 layer 를 트리 순서대로 합성한다.
        """
        return None

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx: dict | None = None,
              on_change=None) -> QWidget | None:
        """선택 시 뜨는 값 편집/표시 위젯 (없으면 None).

        Args:
            value: 디코드된 payload (store 가 풀어 준 것).
            ref: 그 LEAF 의 서술자 — ``format[1]``(detail)이 위젯을 가른다(attr 의 str vs xyxy).
            ctx: 표시에 필요한 주변 정보 (예: ``{"candidates": [...]}`` — id_map 의 class 후보).
            on_change: 값이 편집되면 부를 콜백 ``(새 값) -> None``.
        """
        return None

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        """트리에 한 줄로 보일 요약 (기본: ``handler(detail)``)."""
        _handler = ref.format[0] if ref.format else "?"
        _detail = ref.format[1] if len(ref.format) > 1 and ref.format[1] else ""
        return f"{_handler}({_detail})" if _detail else _handler
