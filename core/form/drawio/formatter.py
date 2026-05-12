"""formatter.py: 텍스트 및 HTML 포맷팅 유틸리티."""
from typing import Final
from ...definition import Arg_Info, Method_Info
from .utils import Escape_str_for_xml
from .style import ROW_HEIGHT

BUILTIN_TYPES: Final[set[str]] = {
    "int", "str", "float", "bool", "list", "dict", "tuple", "set",
    "Any", "None", "Callable", "Optional", "Union", "Type", "type",
}


def F_type_ref(type_hint: str) -> str:
    """타입 힌트에서 사용자 정의 객체를 단순 이스케이프함."""
    if not type_hint or type_hint == "Any":
        return "Any"
    return Escape_str_for_xml(type_hint)


def F_attributes(
    attributes: list[Arg_Info], default_h: int = ROW_HEIGHT
) -> list[tuple[str, int, str]]:
    """속성 데이터를 HTML 문자열과 높이 정보로 포맷팅함."""
    _data = []
    for _a in attributes:
        _a_name = Escape_str_for_xml(_a.name)
        _a_type = F_type_ref(_a.type_hint)
        _data.append((f"+ {_a_name}: {_a_type}", default_h, "variable"))
    return _data


def F_methods(
    methods: list[Method_Info], default_h: int = ROW_HEIGHT, is_detailed: bool = False
) -> list[tuple[str, int, str]]:
    """메서드 데이터를 HTML 문자열과 높이 정보로 포맷팅함."""
    _data = []
    for _m in methods:
        _m_name = Escape_str_for_xml(_m.name)

        if not is_detailed:
            _data.append((f"+ <b>{_m_name}</b>()", default_h, "function"))
            continue

        _valid_args = [a for a in _m.args if a.name != "self"]
        _m_rt_type = F_type_ref(_m.return_type)

        if not _valid_args:
            _val = f"+ <b>{_m_name}</b>() -&gt; {_m_rt_type}"
            _h = default_h
        else:
            _val = f"+ <b>{_m_name}</b>(<br>"
            for _arg in _valid_args:
                _t = F_type_ref(_arg.type_hint)
                _val += f"&nbsp;&nbsp;&nbsp;&nbsp;{_arg.name}: {_t},<br>"
            _val += f") -&gt; {_m_rt_type}"
            _h = default_h + (len(_valid_args) * default_h) + 16

        _data.append((_val, _h, "function"))
    return _data
