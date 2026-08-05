"""파라미터 spec 추출 + 타입 판별 — process/모델의 ``__init__`` 을 ``_Spec`` 으로 정규화 (설계는 README)."""

from __future__ import annotations

import inspect
import types
from dataclasses import dataclass
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

from core.typing import Arg_Info as UI

# 폼에 노출하지 않는 식별/구조 필드
_SKIP = frozenset({"config_type", "object_type", "name", "processes"})


@dataclass
class _Spec:
    """폼 위젯 하나를 만들 정규화된 파라미터 명세 (name·type·default·ui dict)."""

    name:    str
    type:    Any
    default: Any
    ui:      dict


def _ui_to_dict(ui: UI) -> dict:
    """``UI`` 메타데이터를 위젯 빌더용 평탄 dict(label/tip/min/max/step/kind)로 변환."""
    return {
        "label": ui.label, "tip": ui.tip,
        "min": ui.min, "max": ui.max, "step": ui.step, "kind": ui.kind,
    }


def _unwrap(ann) -> tuple[Any, dict]:
    """``Annotated[type, UI(...)]`` 을 ``(type, ui dict)`` 로 푼다 (일반 타입이면 ui={})."""
    if get_origin(ann) is Annotated:
        _args = get_args(ann)
        _ui: dict = {}
        for _m in _args[1:]:
            if isinstance(_m, UI):
                _ui = _ui_to_dict(_m)
        return _args[0], _ui
    return ann, {}


def _hints_of(cls: type) -> dict:
    """파라미터 이름 → 해소된 타입. **두 출처를 합친다** — 클래스가 이기고, 빈 자리를 ``__init__`` 이 채운다.

    한쪽만 보면 절반이 샌다: dataclass 는 필드가 **클래스** 어노테이션이라 생성된 ``__init__`` 을 보면
    ``Annotated`` 가 안 풀리고(NameError), 손으로 쓴 ``__init__`` 을 둔 일반 클래스(모델 빌더)는 클래스
    어노테이션이 **비어 있어** ``{}`` 가 나온다 — 예외가 아니라 빈 dict 라 fallback 도 안 걸리고,
    ``from __future__ import annotations`` 탓에 타입이 문자열(``"str"``)로 남아 폼이 렌더를 못 한다.
    """
    _hints: dict = {}
    for _src in (cls.__init__, cls):                 # 뒤가 이긴다 (클래스 우선)
        try:
            _hints |= get_type_hints(_src, include_extras=True)
        except Exception:                            # 한쪽이 안 풀려도 다른 쪽으로 간다
            continue
    return _hints


def specs_from_callable(cls: type) -> list[_Spec]:
    """callable class 의 ``__init__`` 시그니처에서 ``_Spec`` 목록을 뽑는다 (식별/구조 필드 제외)."""
    _sig = inspect.signature(cls)
    _hints = _hints_of(cls)
    _specs: list[_Spec] = []
    for _name, _p in _sig.parameters.items():
        if _name == "self" or _p.kind in (_p.VAR_KEYWORD, _p.VAR_POSITIONAL):
            continue
        if _name in _SKIP:
            continue
        _type, _ui = _unwrap(_hints.get(_name, _p.annotation))
        _default = None if _p.default is inspect.Parameter.empty else _p.default
        _specs.append(_Spec(_name, _type, _default, _ui))
    return _specs



# ── 타입 판별 ─────────────────────────────────────────────────────────────────

def _strip_optional(tp):
    """``X | None`` 이면 ``X`` 를, 아니면 그대로 — Optional 을 벗겨 본체 타입으로 판별한다.

    ``list[str] | None`` 같은 nullable 목록도 목록 위젯을 받게 한다(위젯이 안 생기면 그 필드는
    ``Config_form.get()`` 에서 통째로 빠져 config 에 유실된다 — gate 의 ``keep`` 이 그렇게 샜다).
    """
    _origin = get_origin(tp)
    _is_union = _origin is Union or (
        hasattr(types, "UnionType") and isinstance(tp, types.UnionType))
    if not _is_union:
        return tp
    _rest = [_a for _a in get_args(tp) if _a is not type(None)]
    return _rest[0] if len(_rest) == 1 else tp


def _list_str(tp) -> bool:
    """``list[str]``/``list[Any]`` (Optional 포함) — 쉼표 구분 한 줄 입력으로 편집."""
    _tp = _strip_optional(tp)
    return get_origin(_tp) is list and get_args(_tp) in ((str,), (Any,))


def _list_pair(tp) -> bool:
    _tp = _strip_optional(tp)
    return get_origin(_tp) is list and get_args(_tp) == (tuple[str, str],)


def _optional_float(tp) -> bool:
    _origin = get_origin(tp)
    _is_union = _origin is Union or (
        hasattr(types, "UnionType") and isinstance(tp, types.UnionType))
    return _is_union and set(get_args(tp)) == {float, type(None)}
