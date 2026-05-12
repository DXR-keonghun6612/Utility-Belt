"""Parser Utility Logic.

상태 독립적(Stateless) 순수 함수 모음.
"""
import ast
from pychart.definition import Arg_Info, Method_Info
from pychart.parser.constants import TYPE_ANY, TYPE_UNKNOWN


def Get_type_str(node: ast.AST | None) -> str:
    """AST 노드를 문자열 타입 힌트로 언파싱함."""
    if node is None:
        return TYPE_ANY
    try:
        return ast.unparse(node)
    except Exception:
        return TYPE_UNKNOWN


def Parse_function_info(
    node: ast.FunctionDef | ast.AsyncFunctionDef
) -> Method_Info:
    """함수 노드에서 시그니처 및 문서화 정보를 추출함."""
    _args = []
    for arg in node.args.args:
        _type_hint = Get_type_str(arg.annotation)
        _args.append(Arg_Info(name=arg.arg, type_hint=_type_hint))

    return Method_Info(
        name=node.name,
        args=_args,
        return_type=Get_type_str(node.returns),
        docstring=ast.get_docstring(node)
    )


def Infer_assign_type(
    value: ast.AST | None, default_type: str = TYPE_ANY
) -> str:
    """할당된 값(노드)을 기반으로 변수의 타입을 추론함."""
    if default_type == TYPE_ANY and isinstance(value, ast.Call):
        return Get_type_str(value.func)
    return default_type

def Extract_instance_attributes(
    node: ast.FunctionDef | ast.AsyncFunctionDef, existing_names: set[str]
) -> list[Arg_Info]:
    """__init__ 등의 메서드 내부에서 인스턴스 속성을 추출함."""
    _new_attrs = []

    for child in ast.walk(node):
        if isinstance(child, (ast.Assign, ast.AnnAssign)):
            # 단일 및 다중 할당 타겟을 리스트로 정규화
            _targets = (
                child.targets if isinstance(child, ast.Assign) 
                else [child.target]
            )

            for target in _targets:
                # self.* 형태의 식별자 검증 (조기 계속 패턴)
                if not isinstance(target, ast.Attribute):
                    continue
                if not isinstance(target.value, ast.Name):
                    continue
                if target.value.id != "self":
                    continue

                _attr_name = target.attr
                if _attr_name in existing_names:
                    continue

                # 타입 힌트 결정
                if isinstance(child, ast.AnnAssign):
                    _type = Get_type_str(child.annotation)
                else:
                    _type = Infer_assign_type(child.value)

                # 추출 결과 저장
                _new_attrs.append(Arg_Info(name=_attr_name, type_hint=_type))
                existing_names.add(_attr_name)

    return _new_attrs
