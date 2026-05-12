"""Intermediate Representation (IR) Layer.

정적 코드 분석 결과를 담는 범용 데이터 모델 정의.
"""
from typing import Literal
from dataclasses import dataclass, field


@dataclass(slots=True)
class Arg_Info:
    """인자/변수 정보 데이터 모델.

    Attributes:
        name: 식별자명.
        type_hint: 타입 힌트 문자열.
    """
    name: str
    type_hint: str = "Any"


@dataclass(slots=True)
class Method_Info:
    """메서드 및 함수 정보 데이터 모델.

    Attributes:
        name: 메서드명.
        args: 인자 리스트.
        return_type: 반환 타입 문자열.
        docstring: 문서화 문자열.
        stereotype: 스테레오타입 명칭 (예: «function»).
    """
    name: str
    args: list['Arg_Info'] = field(default_factory=list)
    return_type: str = "Any"
    docstring: str | None = None
    stereotype: str = ""

    def To_uml_signature(self) -> str:
        """UML 표준 시그니처 문자열 생성."""
        _args_str = ", ".join(
            f"{a.name}: {a.type_hint}" for a in self.args if a.name != "self"
        )
        return f"+ {self.name}({_args_str}) -> {self.return_type}"


@dataclass(slots=True)
class Class_Info:
    """클래스/구조체 정보 데이터 모델.

    Attributes:
        name: 클래스명.
        bases: 상속받은 부모 클래스 이름 리스트.
        attributes: 클래스 속성 리스트.
        methods: 클래스 메서드 리스트.
        docstring: 문서화 문자열.
        stereotype: 클래스 스테레오타입 (예: «dataclass»).
    """
    name: str
    bases: list[str] = field(default_factory=list)
    attributes: list[Arg_Info] = field(default_factory=list)
    methods: list[Method_Info] = field(default_factory=list)
    docstring: str | None = None
    stereotype: str = ""


@dataclass(slots=True)
class Module_Info:
    """모듈/파일 단위 정보.

    Attributes:
        name: 모듈명.
        imported_symbols: 모듈에서 가져온 심볼 딕셔너리.
        variables: 모듈 레벨 선언 변수 리스트.
        functions: 모듈 내 정의된 전역 함수 리스트.
        classes: 모듈 내 정의된 클래스 리스트.
        stereotype: 스테레오타입 명칭.
        file_path: 소스 코드 파일의 절대 경로.
    """
    name: str
    imported_symbols: dict[str, list[str]] = field(default_factory=dict)
    variables: list[Arg_Info] = field(default_factory=list)
    functions: list[Method_Info] = field(default_factory=list)
    classes: list[Class_Info] = field(default_factory=list)
    stereotype: Literal["«external»", "«local»"] = "«local»"
    file_path: str | None = None
