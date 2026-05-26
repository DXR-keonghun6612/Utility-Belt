"""Intermediate Representation (IR) Layer.

정적 코드 분석 결과를 담는 범용 데이터 모델 정의.

본 IR은 모든 언어 백엔드가 수렴하는 공통 계약이며,
``Data_Schema`` 상속으로 yaml/json 자동 직렬화를 지원한다.
"""
from __future__ import annotations
from typing import Literal
from dataclasses import dataclass, field

from python_toolbox import Data_Schema


# 분류 어휘 — plan/classifier.md / plan/data-model.md
Abstraction = Literal["interface", "abstract", "concrete"]
Trait = Literal["template", "macro", "data"]
Origin = Literal["internal", "external"]
Access = Literal["public", "protected", "private"]


@dataclass
class Arg_Info(Data_Schema):
    """인자/변수/속성 정보 데이터 모델.

    Attributes:
        name: 식별자명.
        type_hint: 타입 힌트 문자열.
        access: 접근 지정자 (속성에 의미 있음; 인자는 무시).
        is_static: 정적 멤버 여부 (속성에 의미 있음).
        default_value: 기본값 문자열 표현 (없으면 None).
        source_line: 선언 라인 (디버깅용).
    """
    name: str
    type_hint: str = "Any"
    access: Access = "public"
    is_static: bool = False
    default_value: str | None = None
    source_line: int | None = None


@dataclass
class Method_Info(Data_Schema):
    """메서드 및 함수 정보 데이터 모델.

    Notes:
        Callable 카테고리에는 stereotype 어휘를 적용하지 않는다.
        분류는 메타 필드(access, is_static, ...)만으로 충분.

    Attributes:
        id: 노드 ID — ``{module_key}::{namespace}::{name}``.
        name: 메서드/함수명.
        args: 인자 리스트.
        return_type: 반환 타입.
        docstring: 문서화 문자열.
        source_line: 선언 라인 (디버깅용).
    """
    name: str
    args: list[Arg_Info] = field(default_factory=list)
    return_type: str = "Any"
    docstring: str | None = None
    id: str = ""
    source_line: int | None = None

    def To_uml_signature(self) -> str:
        """UML 표준 시그니처 문자열 생성."""
        _args_str = ", ".join(
            f"{a.name}: {a.type_hint}" for a in self.args if a.name != "self"
        )
        return f"+ {self.name}({_args_str}) -> {self.return_type}"


@dataclass
class Class_Info(Data_Schema):
    """클래스/구조체/유니온 정보 데이터 모델.

    Attributes:
        id: 노드 ID — ``{module_key}::{namespace}::{name}``.
        name: 클래스명.
        bases: 상속받은 부모 클래스 이름 리스트
            (가능하면 fully qualified name).
        attributes: 속성 리스트.
        methods: 메서드 리스트.
        docstring: 문서화 문자열.
        abstraction: 추상화 수준 (정확히 1개). 기본값 ``"concrete"``.
            02_classifier가 자기 메서드만 보고 잠정 부여,
            03_linker가 상속 체인 따라 최종 보정.
        traits: 구조적 특성 (0개 이상).
            ``template`` / ``macro`` / ``data``.
        origin: ``internal`` (분석 대상) / ``external`` (관측 범위 밖).
        source_line: 선언 라인 (디버깅용).
    """
    name: str
    bases: list[str] = field(default_factory=list)
    attributes: list[Arg_Info] = field(default_factory=list)
    methods: list[Method_Info] = field(default_factory=list)
    docstring: str | None = None
    id: str = ""
    abstraction: Abstraction = "concrete"
    traits: set[Trait] = field(default_factory=set)
    origin: Origin = "internal"
    source_line: int | None = None


@dataclass
class Module_Info(Data_Schema):
    """모듈/파일 단위 정보.

    Attributes:
        id: 모듈 키 (보통 ``file_key`` 그대로).
        name: 모듈명.
        imported_symbols: 가져온 심볼 딕셔너리 (C++의 includes 포함).
        variables: 모듈 레벨 선언 변수 리스트.
        functions: 모듈 내 정의된 전역 함수 리스트.
        classes: 모듈 내 정의된 클래스 리스트.
        origin: ``internal`` / ``external``.
        file_path: 소스 코드 파일의 절대 경로.
    """
    name: str
    imported_symbols: dict[str, list[str]] = field(default_factory=dict)
    variables: list[Arg_Info] = field(default_factory=list)
    functions: list[Method_Info] = field(default_factory=list)
    classes: list[Class_Info] = field(default_factory=list)
    id: str = ""
    origin: Origin = "internal"
    file_path: str | None = None
