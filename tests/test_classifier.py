"""parser.cxx.classifier (02_classifier) 단위 테스트.

실행: ``make test`` 또는 ``python3 -m unittest discover -s tests -v``.
libclang 없이 IR 객체를 직접 구성해 분류 로직만 검증한다.
"""
from __future__ import annotations
import unittest

from cchart.definition import CXX_Class_Info, CXX_Method_Info, Translation_Unit_Info
from parser.cxx.classifier import CXX_Classifier


def _method(name: str, pure: bool = False) -> CXX_Method_Info:
    return CXX_Method_Info(name=name, is_pure_virtual=pure)


def _classify(cls: CXX_Class_Info, macro_classes=None) -> CXX_Class_Info:
    """단일 클래스를 모듈에 담아 분류한 뒤 그 클래스를 돌려준다."""
    CXX_Classifier(macro_classes=macro_classes).Classify(
        Translation_Unit_Info(name="t.cpp", classes=[cls])
    )
    return cls


class TestAbstraction(unittest.TestCase):
    """abstraction 잠정 판정 규칙."""

    def test_all_pure_virtual_is_interface(self):
        cls = _classify(CXX_Class_Info(
            name="IFoo", methods=[_method("a", True), _method("b", True)]))
        self.assertEqual(cls.abstraction, "interface")

    def test_partial_pure_virtual_is_abstract(self):
        cls = _classify(CXX_Class_Info(
            name="Base", methods=[_method("a", True), _method("b")]))
        self.assertEqual(cls.abstraction, "abstract")

    def test_no_pure_virtual_is_concrete(self):
        cls = _classify(CXX_Class_Info(
            name="Impl", methods=[_method("a"), _method("b")]))
        self.assertEqual(cls.abstraction, "concrete")

    def test_no_methods_is_concrete(self):
        cls = _classify(CXX_Class_Info(name="Point", methods=[]))
        self.assertEqual(cls.abstraction, "concrete")

    def test_ctor_dtor_excluded_from_abstraction(self):
        # 생성자/소멸자는 카운트 제외 — 나머지가 전부 pure virtual이면 interface
        cls = _classify(CXX_Class_Info(name="IBar", methods=[
            _method("IBar"), _method("~IBar"),
            _method("a", True), _method("b", True),
        ]))
        self.assertEqual(cls.abstraction, "interface")


class TestTraits(unittest.TestCase):
    """traits 부여 규칙."""

    def test_template_params_adds_template(self):
        cls = _classify(CXX_Class_Info(
            name="Holder", methods=[_method("get")], template_params=["T"]))
        self.assertIn("template", cls.traits)

    def test_macro_class_by_simple_name(self):
        cls = _classify(
            CXX_Class_Info(name="Widget", methods=[_method("f")]),
            macro_classes={"Widget"})
        self.assertIn("macro", cls.traits)

    def test_macro_class_by_qualified_name(self):
        cls = _classify(
            CXX_Class_Info(name="Mac", namespace_path="ns", methods=[_method("f")]),
            macro_classes={"ns::Mac"})
        self.assertIn("macro", cls.traits)

    def test_non_macro_class_has_no_macro_trait(self):
        cls = _classify(
            CXX_Class_Info(name="Plain", methods=[_method("f")]),
            macro_classes={"Other"})
        self.assertNotIn("macro", cls.traits)

    def test_no_user_methods_adds_data(self):
        cls = _classify(CXX_Class_Info(name="Point", methods=[]))
        self.assertIn("data", cls.traits)

    def test_only_ctor_dtor_adds_data(self):
        cls = _classify(CXX_Class_Info(
            name="Vec", methods=[_method("Vec"), _method("~Vec")]))
        self.assertIn("data", cls.traits)

    def test_class_with_method_has_no_data(self):
        cls = _classify(CXX_Class_Info(name="Impl", methods=[_method("run")]))
        self.assertNotIn("data", cls.traits)

    def test_concrete_class_has_empty_traits(self):
        cls = _classify(CXX_Class_Info(name="Impl", methods=[_method("run")]))
        self.assertEqual(cls.traits, set())


class TestClassifyModule(unittest.TestCase):
    """모듈 단위 동작."""

    def test_classify_is_in_place_and_returns_module(self):
        module = Translation_Unit_Info(name="t.cpp", classes=[
            CXX_Class_Info(name="IFoo", methods=[_method("a", True)])])
        result = CXX_Classifier().Classify(module)
        self.assertIs(result, module)
        self.assertEqual(module.classes[0].abstraction, "interface")

    def test_functions_pass_through_untouched(self):
        func = CXX_Method_Info(name="free_fn")
        module = Translation_Unit_Info(name="t.cpp", functions=[func])
        CXX_Classifier().Classify(module)
        self.assertIs(module.functions[0], func)


if __name__ == "__main__":
    unittest.main()
