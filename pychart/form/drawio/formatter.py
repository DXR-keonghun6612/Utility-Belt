"""formatter.py: 텍스트 및 HTML 포맷팅 유틸리티."""
import re
from typing import Final

from pychart.definition import Arg_Info, Method_Info

from .utils import R_brackets

# 내장 파이썬 타입 리스트
BUILTIN_TYPES: Final[set[str]] = {
    "int", "str", "float", "bool", "list", "dict", "tuple", "set", 
    "Any", "None", "Callable", "Optional", "Union", "Type", "type"
}


def F_type_ref(type_hint: str) -> str:
    """타입 힌트에서 사용자 정의 객체를 강조함.
    
    내장 타입을 제외한 단어는 파란색 강조 및 # 접두사를 붙여 시각화함.

    Args:
        type_hint: 원본 타입 힌트 문자열.

    Returns:
        str: HTML 태그가 포함된 포맷팅된 문자열.
    """
    if not type_hint or type_hint == "Any":
        return "Any"
        
    # 꺾쇠(<, >)를 HTML 엔티티로 안전하게 변환
    _clean_type = R_brackets(type_hint)
    
    def _replacer(match: re.Match) -> str:
        word = match.group(0)
        if word in BUILTIN_TYPES:
            return word
        # 사용자 정의 타입은 파란색 강조
        return f"<b><font color='#0066CC'>#{word}</font></b>"
        
    return re.sub(r'\b[A-Za-z_][A-Za-z0-9_]*\b', _replacer, _clean_type)


def F_attributes(
    attributes: list[Arg_Info], default_h: int = 20
) -> list[tuple[str, int, str]]:
    """속성 데이터를 HTML 문자열과 높이 정보로 포맷팅함.

    Args:
        attributes: 속성 정보 리스트.
        default_h: 한 줄당 기본 높이.

    Returns:
        list[tuple[str, int, str]]: (HTML텍스트, 높이, 타입태그) 튜플 리스트.
    """
    _data = []
    for _a in attributes:
        _a_name = R_brackets(_a.name)
        _a_type = F_type_ref(_a.type_hint)
        _data.append((f"+ {_a_name}: {_a_type}", default_h, "variable"))
    return _data


def F_methods(
    methods: list[Method_Info], default_h: int = 20, is_detailed: bool = False
) -> list[tuple[str, int, str]]:
    """메서드 데이터를 HTML 문자열과 높이 정보로 포맷팅함.

    Args:
        methods: 메서드 정보 리스트.
        default_h: 한 줄당 기본 높이.
        is_detailed: 인자 정보를 상세히 표시할지 여부.

    Returns:
        list[tuple[str, int, str]]: (HTML텍스트, 높이, 타입태그) 튜플 리스트.
    """
    _data = []
    for _m in methods:
        _m_name = R_brackets(_m.name)

        if not is_detailed:
            _data.append((
                R_brackets(f"+ <b>{_m_name}</b>()"), default_h, "function"))
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
            # 인자 수에 비례하여 박스 높이 계산
            _h = default_h + (len(_valid_args) * default_h) + 16
            
        _data.append((R_brackets(_val), _h, "function"))
    return _data
