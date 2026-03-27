"""Parser Layer.

AST를 활용하여 파이썬 소스 코드에서 IR 데이터를 추출함.
"""
import ast
from pathlib import Path
from typing import Any

from pychart.definition import Module_Info, Class_Info, Method_Info, Arg_Info


class Project_Analyzer(ast.NodeVisitor):
    """AST 기반 파이썬 코드 정적 분석기."""

    def __init__(self) -> None:
        """초기화."""
        # 클래스(Class_Info)와 독립 함수(Method_Info)가 통합 저장되는 바구니
        self.ir_data: dict[str, Any] = {}
        # 파싱 컨텍스트: 현재 어느 클래스 내부에 있는지 추적
        self._current_class_name: str | None = None

    def Analyze_directory(self, target_dir: str) -> dict[str, Any]:
        """지정된 현재 디렉토리의 파이썬 코드만 얕게(Shallow) 분석함."""
        _target_path = Path(target_dir).resolve()

        if not _target_path.is_dir():
            raise NotADirectoryError(f"유효하지 않은 디렉토리입니다: {_target_path}")

        for _f in _target_path.glob("*.py"):
            if any((_p.startswith('.') or _p == 'venv') for _p in _f.parts):
                continue

            try:
                with open(_f, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    self.visit(tree)
            except SyntaxError:
                continue
                
        return self.ir_data

    def _Get_type_str(self, node: ast.AST | None) -> str:
        """AST 노드에서 타입 문자열 추출."""
        if node is None:
            return "Any"
        try:
            return ast.unparse(node)
        except Exception:
            return "Unknown"

    def _Parse_function_info(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> Method_Info:
        """함수/메서드 노드에서 시그니처 정보를 추출하는 공통 헬퍼."""
        return Method_Info(
            name=node.name,
            args=[
                Arg_Info(
                    name=arg.arg,
                    type_hint=self._Get_type_str(arg.annotation)
                ) for arg in node.args.args
            ],
            return_type=self._Get_type_str(node.returns),
            docstring=ast.get_docstring(node)
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """클래스 정의부 방문 및 정보 추출."""
        # 1. 클래스 메타데이터 추출
        _bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        _docstring = ast.get_docstring(node)
        _is_enum = any("Enum" in b for b in _bases)
        
        # 데코레이터 파싱 (Dataclass 식별)
        _dec_names = [ast.unparse(d).split('(')[0].split('.')[-1] for d in node.decorator_list]
        _is_dataclass = "dataclass" in _dec_names

        _cls_info = Class_Info(
            name=node.name, 
            bases=_bases, 
            docstring=_docstring, 
            is_enum=_is_enum, 
            is_dataclass=_is_dataclass
        )

        # 2. 클래스 내부 속성(Attributes) 추출 (메서드는 여기서 추출 안 함!)
        for body_item in node.body:
            if isinstance(body_item, ast.AnnAssign) and isinstance(body_item.target, ast.Name):
                _cls_info.attributes.append(
                    Arg_Info(name=body_item.target.id, type_hint=self._Get_type_str(body_item.annotation))
                )
            elif isinstance(body_item, ast.Assign):
                for target in body_item.targets:
                    if isinstance(target, ast.Name):
                        _type_hint = "EnumMember" if _is_enum else "Any"
                        _cls_info.attributes.append(Arg_Info(name=target.id, type_hint=_type_hint))

        # 3. 데이터 등록
        self.ir_data[node.name] = _cls_info
        
        # 4. 컨텍스트 스위칭 및 내부 순회 시작
        _prev_class = self._current_class_name
        # "지금부터 이 클래스 안쪽을 탐색한다"고 표시
        self._current_class_name = node.name
        # 이 과정에서 visit_FunctionDef가 호출됨!
        self.generic_visit(node)
        # 탐색이 끝나면 원래 상태로 복구
        self._current_class_name = _prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        """함수 정의부 방문. (전역 함수 & 클래스 메서드 동시 처리)"""
        _func_info = self._Parse_function_info(node)

        if self._current_class_name:
            # 클래스 컨텍스트가 켜져 있으면 -> 클래스의 메서드로 등록
            self.ir_data[self._current_class_name].methods.append(_func_info)
        else:
            # 클래스 밖이면 -> 전역(독립) 함수로 등록
            self.ir_data[node.name] = _func_info
            
        # 의도적인 생략: self.generic_visit(node)를 호출하지 않음으로써
        # 함수 안에 선언된 중첩 함수(Nested functions)는 다이어그램에서 무시함.

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """비동기 함수(async def)도 일반 함수와 동일하게 처리."""
        self.visit_FunctionDef(node)

    def visit_Import(self, node: ast.Import) -> None:
        """'import A, B' 형태의 구문 수집."""
        for alias in node.names:
            _mod_name = alias.name
            
            # 처음 보는 모듈이면 바구니 생성
            if _mod_name not in self.ir_data:
                self.ir_data[_mod_name] = Module_Info(name=_mod_name)
                
            # import A 형태는 모듈 자체를 가져온 것이므로 심볼 이름에 모듈명을 그대로 넣음
            if _mod_name not in self.ir_data[_mod_name].imported_symbols:
                self.ir_data[_mod_name].imported_symbols.append(_mod_name)
                
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """'from module import A, B' 형태의 구문 수집."""
        # 상대 경로 import (예: from . import utils) 처리
        _prefix = "." * node.level if node.level > 0 else ""
        _base_module = node.module if node.module else ""
        _full_mod_name = f"{_prefix}{_base_module}"

        if not _full_mod_name:
            self.generic_visit(node)
            return

        # 처음 보는 모듈이면 바구니 생성
        if _full_mod_name not in self.ir_data:
            self.ir_data[_full_mod_name] = Module_Info(name=_full_mod_name)

        # 가져온 심볼(A, B 등) 추가
        for alias in node.names:
            if alias.name not in self.ir_data[_full_mod_name].imported_symbols:
                self.ir_data[_full_mod_name].imported_symbols.append(alias.name)

        self.generic_visit(node)
