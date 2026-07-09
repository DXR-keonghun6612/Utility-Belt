"""meta 값(dict/list/Data_Ref[leaf|stem]/스칼라)을 재귀적으로 트리 아이템으로 변환하는 도메인 헬퍼."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QTreeWidgetItem

from core.data.handler import Data_Ref
from core.data.schema import Attr

# dict/list/Data_Ref 이 아닌 값 = 더 펼칠 것이 없는 말단 값 (컨테이너 stem 도 Data_Ref).
_CONTAINER = (dict, list, tuple, Data_Ref)


def _is_scalar(val: Any) -> bool:
    """더 펼칠 자식이 없는 말단 값인지 판단한다."""
    return not isinstance(val, _CONTAINER)


def _data_ref_text(val: Data_Ref) -> str:
    """Data_Ref 를 한 줄 요약 문자열로 만든다.

    인라인(attr 등 ``info["value"]`` 보유)이면 값을, 디스크면 ``type(.format) @dir`` 을 보인다.
    """
    if "value" in val.info:                                   # 인라인 payload
        return f"{val.type}: {val.info['value']!r}"
    _fmt = f"(.{val.format})" if val.format else ""
    _dir = val.info.get("dir")
    _suffix = f"  @{_dir}" if _dir else ""
    return f"{val.type}{_fmt}{_suffix}"


def value_node(key: Any, value: Any, key_col: int = 0) -> QTreeWidgetItem:
    """``key``/``value`` 쌍을 (필요하면 재귀적으로) 트리 아이템으로 만든다.

    key 텍스트는 ``key_col``, value 텍스트는 ``key_col + 1`` 컬럼에 들어간다.
    그 앞 컬럼(예: datas 의 stem 컬럼)은 비워 둬 트리 들여쓰기 전용으로 쓴다.
    중첩된 자식은 같은 ``key_col`` 을 그대로 써서 계층은 들여쓰기로만 표현한다.

    Args:
        key: key 컬럼에 표시할 키(문자열/인덱스).
        value: value 컬럼/자식으로 펼칠 값.
        key_col: key 텍스트가 들어갈 컬럼 인덱스.

    Returns:
        값의 종류에 맞게 자식까지 구성된 ``QTreeWidgetItem``.
    """
    _val_col = key_col + 1

    def _make(val_text: str) -> QTreeWidgetItem:
        _texts = [""] * (_val_col + 1)
        _texts[key_col] = str(key)
        _texts[_val_col] = val_text
        return QTreeWidgetItem(_texts)

    if isinstance(value, Data_Ref) and value.Is_stem():        # 컨테이너(obj/frame) — key = obj_id
        _item = _make(f"{Attr(value, 'class_id')}  (obj {key})")
        for _k, _v in value.info.items():
            _item.addChild(value_node(_k, _v, key_col))
        return _item

    if isinstance(value, Data_Ref):                            # leaf
        return _make(_data_ref_text(value))

    if isinstance(value, dict):
        _item = _make(f"{{{len(value)}}}")
        for _k, _v in value.items():
            _item.addChild(value_node(_k, _v, key_col))
        return _item

    if isinstance(value, (list, tuple)):
        # 스칼라로만 이뤄진 짧은 리스트(예: bbox)는 한 줄로 인라인.
        if all(_is_scalar(_v) for _v in value):
            return _make(repr(list(value)))
        _item = _make(f"[{len(value)}]")
        for _i, _v in enumerate(value):
            _item.addChild(value_node(_i, _v, key_col))
        return _item

    return _make(str(value))
