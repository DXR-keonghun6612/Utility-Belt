"""C/C++ 확장 IR Layer.

core.definition의 공통 IR을 상속하여 C/C++ 전용 개념을 추가로 정의합니다.
"""
from typing import Literal
from dataclasses import dataclass, field
from core.definition import Arg_Info, Method_Info, Class_Info, Module_Info

Access = Literal["public", "protected", "private"]


@dataclass(slots=True)
class CXX_Method_Info(Method_Info):
    """C++ 메서드/함수 확장 IR.

    Attributes:
        access: 접근 지정자.
        is_virtual: virtual 메서드 여부.
        is_override: override 여부.
        is_const: const 메서드 여부.
        is_static: static 메서드 여부.
        is_pure_virtual: 순수 가상 함수 여부.
    """
    access: Access = "public"
    is_virtual: bool = False
    is_override: bool = False
    is_const: bool = False
    is_static: bool = False
    is_pure_virtual: bool = False

    def To_uml_signature(self) -> str:
        """UML 시그니처 생성 (접근 지정자 + 한정자 포함)."""
        _access_map = {"public": "+", "protected": "#", "private": "-"}
        _prefix = _access_map.get(self.access, "+")

        _args_str = ", ".join(
            f"{a.name}: {a.type_hint}" for a in self.args
        )
        _sig = f"{_prefix} {self.name}({_args_str}) -> {self.return_type}"

        _qualifiers = []
        if self.is_virtual:
            _qualifiers.append("virtual")
        if self.is_pure_virtual:
            _qualifiers.append("= 0")
        if self.is_const:
            _qualifiers.append("const")
        if self.is_override:
            _qualifiers.append("override")

        return f"{_sig} [{', '.join(_qualifiers)}]" if _qualifiers else _sig


@dataclass(slots=True)
class CXX_Class_Info(Class_Info):
    """C++ 클래스/구조체/유니온 확장 IR.

    Attributes:
        kind: 선언 종류 (class / struct / union).
        template_params: 템플릿 파라미터 리스트.
        namespace_path: 소속 namespace 경로 (예: "ns::inner").
    """
    kind: Literal["class", "struct", "union"] = "class"
    template_params: list[str] = field(default_factory=list)
    namespace_path: str = ""


@dataclass(slots=True)
class Translation_Unit_Info(Module_Info):
    """C++ 번역 단위(소스/헤더 파일) 정보.

    Attributes:
        includes: 직접 #include하는 파일 경로 리스트.
        compile_flags: 이 파일에 적용된 컴파일 플래그 리스트.
    """
    includes: list[str] = field(default_factory=list)
    compile_flags: list[str] = field(default_factory=list)
