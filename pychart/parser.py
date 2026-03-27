"""Parser Layer.

AST를 활용하여 파이썬 소스 코드에서 IR 데이터를 추출함.
"""
import ast
from pathlib import Path
from typing import Any

from pychart.definition import (
    Module_Info, Class_Info, Method_Info, Arg_Info, Global_Group_Info)


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

    def visit_Module(self, node: ast.Module) -> None:
        """파일 최상단(모듈 레벨)의 전역 변수 및 레지스트리 객체 동적 수집."""
        for body_item in node.body:
            # 1. 일반 할당 (예: CFGS = Registry(...) 또는 MAX_VAL = 10)
            if isinstance(body_item, ast.Assign):
                for target in body_item.targets:
                    if isinstance(target, ast.Name):
                        _name = target.id
                        _type_hint = "Any"
                        
                        # [핵심 로직] 동적 스테레오타입 분류
                        _group_name = "Globals"
                        _stereotype = "«constants»"

                        if isinstance(body_item.value, ast.Call):
                            # 호출된 함수/클래스 이름 추출 (예: 'Registry')
                            _type_hint = self._Get_type_str(body_item.value.func)
                            
                            # Call 힌트를 기반으로 Registry 여부 판단
                            if "Registry" in _type_hint:
                                _group_name = "Registries"
                                _stereotype = "«registry»"
                        
                        # 그룹 바구니가 없으면 새로 생성
                        if _group_name not in self.ir_data:
                            self.ir_data[_group_name] = Global_Group_Info(
                                name=_group_name, stereotype=_stereotype
                            )
                            
                        self.ir_data[_group_name].variables.append(
                            Arg_Info(name=_name, type_hint=_type_hint)
                        )
                        
            # 2. 타입 힌트가 있는 전역 변수 (예: MAX_VAL: int = 10)
            elif isinstance(body_item, ast.AnnAssign):
                if isinstance(body_item.target, ast.Name):
                    _name = body_item.target.id
                    _type_hint = self._Get_type_str(body_item.annotation)
                    
                    _group_name = "Globals"
                    if _group_name not in self.ir_data:
                        self.ir_data[_group_name] = Global_Group_Info(
                            name=_group_name, stereotype="«constants»"
                        )
                    self.ir_data[_group_name].variables.append(
                        Arg_Info(name=_name, type_hint=_type_hint)
                    )

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """클래스 정의부 방문 및 정보 추출."""
        _bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        _docstring = ast.get_docstring(node)
        
        # 1. 상태 판별 (임시 로컬 변수로만 사용)
        _is_enum_flag = any("Enum" in b for b in _bases)
        _dec_names = [
            ast.unparse(d).split('(')[0].split('.')[-1] for d in node.decorator_list]
        _is_dataclass_flag = "dataclass" in _dec_names
        
        # 2. 스테레오타입 확정
        if _is_enum_flag:
            _stereotype = "«enumeration»<br>"
        elif _is_dataclass_flag:
            _stereotype = "«dataclass»<br>"
        else:
            _stereotype = None

        # 3. 모델 생성 (is_enum, is_dataclass 인자 제거됨)
        _cls_info = Class_Info(
            name=node.name, 
            bases=_bases, 
            docstring=_docstring,
            stereotype=_stereotype
        )

        # 4. 클래스 내부 속성 추출 (기존과 동일)
        for body_item in node.body:
            if isinstance(body_item, ast.AnnAssign) and isinstance(body_item.target, ast.Name):
                _cls_info.attributes.append(
                    Arg_Info(name=body_item.target.id, type_hint=self._Get_type_str(body_item.annotation))
                )
            elif isinstance(body_item, ast.Assign):
                for target in body_item.targets:
                    if isinstance(target, ast.Name):
                        # Enum 멤버 판단 시 로컬 변수(_is_enum_flag) 재활용
                        _type_hint = "EnumMember" if _is_enum_flag else "Any"
                        _cls_info.attributes.append(
                            Arg_Info(name=target.id, type_hint=_type_hint))

        # 3. 데이터 등록
        self.ir_data[node.name] = _cls_info
        
        _prev_class = self._current_class_name
        self._current_class_name = node.name
        self.generic_visit(node)
        self._current_class_name = _prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        """함수 정의부 방문. (전역 함수 & 클래스 메서드 동시 처리)"""
        _func_info = self._Parse_function_info(node)
        
        if self._current_class_name:
            self.ir_data[self._current_class_name].methods.append(_func_info)
        else:
            # [핵심] 전역 함수일 경우 명찰 달아줌
            _func_info.stereotype = "«function»<br>"
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
