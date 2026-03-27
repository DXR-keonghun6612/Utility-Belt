"""formatter.py: 텍스트 및 HTML 포맷팅 유틸리티."""
import re

from pychart.definition import Arg_Info, Method_Info

from .utils import R_brackets


BUILTIN_TYPES = {
    "int", "str", "float", "bool", "list", "dict", "tuple", "set", 
    "Any", "None", "Callable", "Optional", "Union", "Type", "type"
}

def F_type_ref(type_hint: str) -> str:
    """타입 힌트에서 사용자 정의 객체를 찾아 #태그 형식(가짜 링크)으로 강조함."""
    if not type_hint or type_hint == "Any":
        return "Any"
        
    # 1. 제네릭 기호(<, >)를 HTML 엔티티로 안전하게 변환
    _clean_type = R_brackets(type_hint)
    
    # 2. 정규식 치환 함수: 단어 단위로 검사
    def _replacer(match: re.Match) -> str:
        word = match.group(0)
        if word in BUILTIN_TYPES:
            return word # 내장 타입은 그대로 반환
        # 사용자 정의 타입은 파란색 텍스트와 # 기호를 붙여 하이퍼링크처럼 연출
        return f"<b><font color='#0066CC'>#{word}</font></b>"
        
    # 영문자, 숫자, 언더바가 조합된 단어(\b)를 모두 찾아서 _replacer로 넘김
    # 예: "list[Custom_Model]" -> "list[&lt;b&gt;&lt;font color='#0066CC'&gt;#Custom_Model&lt;/font&gt;&lt;/b&gt;]"
    return re.sub(r'\b[A-Za-z_][A-Za-z0-9_]*\b', _replacer, _clean_type)


def F_attributes(
    attributes: list[Arg_Info], default_h: int = 20
) -> list[tuple[str, int, str]]:
    """속성(Variables) 데이터를 HTML 문자열과 높이 정보로 포맷팅함."""
    _data = []
    for _a in attributes:
        _a_name = R_brackets(_a.name)
        _a_type = F_type_ref(_a.type_hint)
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
            
        _data.append((R_brackets(_val), _h, "function"))
    return _data