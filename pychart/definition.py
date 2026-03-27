"""Intermediate Representation (IR) Layer.

정적 코드 분석 결과를 담는 범용 데이터 모델을 정의함.
"""
from dataclasses import dataclass, field

@dataclass
class Arg_Info:
    """인자 정보 데이터 모델.
    
    Attributes:
        name: 인자명.
        type_hint: 타입 힌트 문자열.
    """
    name: str
    type_hint: str = "Any"

@dataclass
class Method_Info:
    """메서드 및 함수 정보 데이터 모델.
    
    Attributes:
        name: 메서드명.
        args: 인자 리스트.
        return_type: 반환 타입 문자열.
        docstring: 문서화 문자열.
    """
    name: str
    args: list[Arg_Info] = field(default_factory=list)
    return_type: str = "Any"
    docstring: str |  None = None

    def to_uml_signature(self) -> str:
        """UML 표준 시그니처 문자열 생성.

        Returns:
            str: 포맷팅된 UML 시그니처 문자열.
        """
        # self 인자 제외 및 포맷팅
        _args_str = ", ".join(
            f"{a.name}: {a.type_hint}" for a in self.args if a.name != "self")
        return f"+ {self.name}({_args_str}) -> {self.return_type}"

@dataclass
class Class_Info:
    """클래스 정보 데이터 모델.
    
    Attributes:
        name: 클래스명.
        bases: 상속받은 부모 클래스 이름 리스트.
        attributes: 클래스 속성 리스트.
        methods: 클래스 메서드 리스트.
        docstring: 문서화 문자열.
    """
    name: str
    bases: list[str] = field(default_factory=list)
    attributes: list[Arg_Info] = field(default_factory=list)
    methods: list[Method_Info] = field(default_factory=list)
    docstring: str | None = None