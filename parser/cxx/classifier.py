"""C/C++ Classifier — 02_classifier 단계의 C/C++ 구현.

01_parser가 만든 IR의 Type 카테고리(class/struct/union)에 한해
``abstraction``(추상화 수준)과 ``traits``(구조적 특성)를 부여한다.

- abstraction: 자기 메서드만 본 **잠정값** — 상속 체인을 따른 최종 보정은 03_linker 책임.
- Callable(함수)·Data(변수) 카테고리는 손대지 않고 통과시킨다.

분류 규칙은 plan/classifier.md 참조.
"""
from __future__ import annotations
from typing import ClassVar, Iterable

from core.definition import Abstraction, Trait
from cchart.definition import CXX_Class_Info, CXX_Method_Info, Translation_Unit_Info

from .constants import LANGUAGE


class CXX_Classifier:
    """C/C++ IR 분류기 — 02_classifier 단계.

    Args:
        macro_classes: ``--macro-classes`` 옵션으로 지정된 매크로 정의 클래스명 집합.
            클래스 이름(단순명 또는 ``namespace::name``)이 일치하면 ``traits ∋ macro``.
    """

    language: ClassVar[str] = LANGUAGE

    def __init__(self, macro_classes: Iterable[str] | None = None) -> None:
        self.macro_classes: set[str] = set(macro_classes or [])

    # =========================================================================
    # 진입점
    # =========================================================================
    def Classify(self, module: Translation_Unit_Info) -> Translation_Unit_Info:
        """모듈 내 모든 Type 노드에 ``abstraction`` + ``traits``를 부여한다.

        ``module``을 제자리(in-place) 갱신하고 동일 객체를 반환한다.
        함수·변수(Callable / Data)는 변경하지 않는다.
        """
        for _cls in module.classes:
            self._classify_class(_cls)
        return module

    # =========================================================================
    # 클래스 분류
    # =========================================================================
    def _classify_class(self, cls: CXX_Class_Info) -> None:
        _regular = self._regular_methods(cls)
        cls.abstraction = self._infer_abstraction(_regular)
        cls.traits = self._infer_traits(cls, _regular)

    def _infer_abstraction(
        self, regular_methods: list[CXX_Method_Info]
    ) -> Abstraction:
        """자기 메서드만 보고 추상화 수준을 잠정 판정한다.

        - 메서드 ≥ 1개 AND 전부 pure virtual → ``interface``
        - 일부만 pure virtual (1 ≤ pure < 전체) → ``abstract``
        - 그 외 (pure 0개 또는 메서드 0개) → ``concrete``
        """
        if not regular_methods:
            return "concrete"
        _pure = sum(1 for _m in regular_methods if _m.is_pure_virtual)
        if _pure == 0:
            return "concrete"
        if _pure == len(regular_methods):
            return "interface"
        return "abstract"

    def _infer_traits(
        self, cls: CXX_Class_Info, regular_methods: list[CXX_Method_Info]
    ) -> set[Trait]:
        """구조적 특성(0개 이상)을 부여한다."""
        _traits: set[Trait] = set()
        if cls.template_params:
            _traits.add("template")
        if self._is_macro_class(cls):
            _traits.add("macro")
        if not regular_methods:
            _traits.add("data")
        return _traits

    # =========================================================================
    # 헬퍼
    # =========================================================================
    def _regular_methods(self, cls: CXX_Class_Info) -> list[CXX_Method_Info]:
        """ctor/dtor를 제외한 사용자 정의 메서드 목록.

        Notes:
            abstraction 판정과 ``data`` trait 모두 이 집합을 기준으로 한다.
            생성자는 pure virtual이 될 수 없어, 포함하면 idiomatic interface가
            결코 ``interface``로 분류되지 않으므로 제외한다.
        """
        return [
            _m for _m in cls.methods
            if not self._is_ctor_or_dtor(_m, cls.name)
        ]

    @staticmethod
    def _is_ctor_or_dtor(method: CXX_Method_Info, class_name: str) -> bool:
        # 생성자: 메서드명 == 클래스명 / 소멸자: '~' 접두
        return method.name == class_name or method.name.startswith("~")

    def _is_macro_class(self, cls: CXX_Class_Info) -> bool:
        if not self.macro_classes:
            return False
        _qualified = (
            f"{cls.namespace_path}::{cls.name}"
            if cls.namespace_path else cls.name
        )
        return cls.name in self.macro_classes or _qualified in self.macro_classes
