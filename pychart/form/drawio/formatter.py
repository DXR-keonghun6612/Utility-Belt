"""formatter.py: 텍스트 및 HTML 포맷팅 유틸리티."""
from pychart.definition import Arg_Info, Method_Info

from .utils import R_brackets


def F_attributes(
    attributes: list[Arg_Info], default_h: int = 20
) -> list[tuple[str, int, str]]:
    """속성(Variables) 데이터를 HTML 문자열과 높이 정보로 포맷팅함."""
    _data = []
    for _a in attributes:
        _a_name = R_brackets(_a.name)
        _a_type = R_brackets(_a.type_hint)
        _data.append((f"+ {_a_name}: {_a_type}", default_h, "variable"))
    return _data

def F_methods(
    methods: list[Method_Info], default_h: int = 20, is_detailed: bool = False
) -> list[tuple[str, int, str]]:
    """메서드(Functions) 데이터를 줄바꿈이 적용된 HTML 문자열과 높이 정보로 포맷팅함."""
    _data = []
    for _m in methods:
        _m_name = R_brackets(_m.name)

        if not is_detailed:
            _data.append((
                R_brackets(f"+ <b>{_m_name}</b>()"), default_h, "function"))
            continue

        _valid_args = [a for a in _m.args if a.name != "self"]
        _m_rt_type = R_brackets(_m.return_type)
        
        if not _valid_args:
            _val = f"+ <b>{_m_name}</b>() -&gt; {_m_rt_type}"
            _h = default_h
        else:
            _val = f"+ <b>{_m_name}</b>(<br>"
            for _arg in _valid_args:
                _t = R_brackets(_arg.type_hint)
                _val += f"&nbsp;&nbsp;&nbsp;&nbsp;{_arg.name}: {_t},<br>"
            _val += f") -&gt; {_m_rt_type}"
            _h = default_h + (len(_valid_args) * default_h) + 16
            
        _data.append((R_brackets(_val), _h, "function"))
    return _data