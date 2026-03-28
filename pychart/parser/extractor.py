"""Parser Layer.

AST를 활용하여 파이썬 소스 코드에서 IR 데이터를 추출함.
"""
import ast
from pathlib import Path

from pychart.definition import (
    Module_Info, Class_Info, Method_Info, Arg_Info, Global_Group_Info)

from .parsing_type import NODE


class Project_Analyzer(ast.NodeVisitor):
    """AST 기반 파이썬 코드 정적 분석기.
    
    Attributes:
        ir_data: 분석을 통해 수집된 모델 데이터 바구니 (심볼명: 모델객체).
    """

    def __init__(self) -> None:
        """초기화."""
        self.ir_data: dict[str, NODE] = {}
        # 파싱 컨텍스트: 현재 어느 클래스 내부에 있는지 추적
        self._current_class_name: str | None = None

    def Analyze_directory(self, target_dir: str) -> dict[str, NODE]:
        """지정된 디렉토리의 파이썬 코드를 얕게(Shallow) 분석함.

        Args:
            target_dir: 분석 대상 디렉토리 경로.

        Returns:
            dict[str, NODE]: 수집된 IR 데이터 맵.

        Raises:
            NotADirectoryError: 유효하지 않은 디렉토리 경로인 경우 발생.
        """
        _target_path = Path(target_dir).resolve()

        if not _target_path.is_dir():
            raise NotADirectoryError(f"유효하지 않은 디렉토리: {_target_path}")

        for _f in _target_path.glob("*.py"):
            # 숨김 파일이나 venv 디렉토리는 건너뜀
            if any((_p.startswith('.') or _p == 'venv') for _p in _f.parts):
                continue

            try:
                with open(_f, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    self.visit(tree)
            except (SyntaxError, OSError):
                continue
                
        return self.ir_data

    def _Get_type_str(self, node: ast.AST | None) -> str:
        """AST 노드에서 타입 문자열을 추출함.

        Args:
            node: 타입을 추출할 AST 노드.

        Returns:
            str: 추출된 타입 문자열 (기본값 "Any").
        """
        if node is None:
            return "Any"
        try:
            return ast.unparse(node)
        except Exception:
            return "Unknown"

    def _Parse_function_info(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> Method_Info:
        """함수/메서드 노드에서 시그니처 정보를 추출함.

        Args:
            node: 함수 정의 AST 노드.

        Returns:
            Method_Info: 추출된 메서드 정보 모델.
        """
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
        """모듈 레벨의 전역 변수 및 레지스트리 객체를 수집함.

        Args:
            node: 모듈 AST 노드.
        """
        for body_item in node.body:
            # 1. 일반 할당 (Assign)
            if isinstance(body_item, ast.Assign):
                for target in body_item.targets:
                    if isinstance(target, ast.Name):
                        self._Process_global_variable(
                            target.id, body_item.value)
                        
            # 2. 타입 힌트가 있는 할당 (AnnAssign)
            elif isinstance(body_item, ast.AnnAssign):
                if isinstance(body_item.target, ast.Name):
                    self._Process_global_variable(
                        body_item.target.id, 
                        None, 
                        self._Get_type_str(body_item.annotation)
                    )

        self.generic_visit(node)

    def _Process_global_variable(
        self, name: str, value: ast.AST | None, type_hint: str = "Any"
    ) -> None:
        """전역 변수를 분석하여 적절한 그룹에 추가함.

        Args:
            name: 변수명.
            value: 할당된 값 노드.
            type_hint: 명시된 타입 힌트.
        """
        _group_name = "Globals"
        _stereotype = "«constants»"
        _final_type = type_hint

        # Registry 호출 여부 판단
        if isinstance(value, ast.Call):
            _call_type = self._Get_type_str(value.func)
            if "Registry" in _call_type:
                _group_name = "Registries"
                _stereotype = "«registry»"
                _final_type = _call_type
        
        # 그룹 정보 업데이트 또는 생성
        _group = self.ir_data.get(_group_name)
        if not isinstance(_group, Global_Group_Info):
            _group = Global_Group_Info(name=_group_name, stereotype=_stereotype)
            self.ir_data[_group_name] = _group
            
        _group.variables.append(Arg_Info(name=name, type_hint=_final_type))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """클래스 정의부를 방문하여 상속 및 속성 정보를 추출함.

        Args:
            node: 클래스 정의 AST 노드.
        """
        _bases = [
            ast.unparse(b) for b in node.bases 
            if isinstance(b, (ast.Name, ast.Attribute))
        ]
        
        # 스테레오타입 판별
        _dec_names = [
            ast.unparse(d).split('(')[0].split('.')[-1] 
            for d in node.decorator_list
        ]
        _stereotype = ""
        if any("Enum" in b for b in _bases):
            _stereotype = "«enumeration»<br>"
        elif "dataclass" in _dec_names:
            _stereotype = "«dataclass»<br>"

        _cls_info = Class_Info(
            name=node.name, 
            bases=_bases, 
            docstring=ast.get_docstring(node),
            stereotype=_stereotype
        )

        # 클래스 내부 멤버 추출
        for body_item in node.body:
            if isinstance(body_item, ast.AnnAssign):
                if isinstance(body_item.target, ast.Name):
                    _cls_info.attributes.append(Arg_Info(
                        name=body_item.target.id, 
                        type_hint=self._Get_type_str(body_item.annotation)
                    ))
            elif isinstance(body_item, ast.Assign):
                for target in body_item.targets:
                    if isinstance(target, ast.Name):
                        _type = "EnumMember" if "enumeration" in _stereotype else "Any"
                        _cls_info.attributes.append(
                            Arg_Info(name=target.id, type_hint=_type)
                        )

        self.ir_data[node.name] = _cls_info
        
        # 컨텍스트 유지하며 내부 순회
        _prev_class = self._current_class_name
        self._current_class_name = node.name
        self.generic_visit(node)
        self._current_class_name = _prev_class

    def visit_FunctionDef(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """함수 정의부를 방문하여 정보를 추출함. (전역 함수 & 메서드)

        Args:
            node: 함수 정의 AST 노드.
        """
        _func_info = self._Parse_function_info(node)
        
        if self._current_class_name:
            # 클래스 메서드인 경우 해당 클래스 모델에 추가
            _cls = self.ir_data.get(self._current_class_name)
            if isinstance(_cls, Class_Info):
                _cls.methods.append(_func_info)
        else:
            # 전역 함수인 경우 독립 노드로 등록
            _func_info.stereotype = "«function»<br>"
            self.ir_data[node.name] = _func_info

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """비동기 함수를 일반 함수와 동일하게 처리함.

        Args:
            node: 비동기 함수 정의 AST 노드.
        """
        self.visit_FunctionDef(node)

    def visit_Import(self, node: ast.Import) -> None:
        """'import' 구문을 분석하여 모듈 정보를 수집함.

        Args:
            node: Import AST 노드.
        """
        for alias in node.names:
            _mod_name = alias.name
            
            _mod = self.ir_data.get(_mod_name)
            if not isinstance(_mod, Module_Info):
                _mod = Module_Info(name=_mod_name)
                self.ir_data[_mod_name] = _mod
                
            if _mod_name not in _mod.imported_symbols:
                _mod.imported_symbols.append(_mod_name)
                
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """'from ... import' 구문을 분석하여 모듈 정보를 수집함.

        Args:
            node: ImportFrom AST 노드.
        """
        _prefix = "." * node.level if node.level > 0 else ""
        _base_module = node.module if node.module else ""
        _full_mod_name = f"{_prefix}{_base_module}"

        if not _full_mod_name:
            self.generic_visit(node)
            return

        _mod = self.ir_data.get(_full_mod_name)
        if not isinstance(_mod, Module_Info):
            _mod = Module_Info(name=_full_mod_name)
            self.ir_data[_full_mod_name] = _mod

        for alias in node.names:
            if alias.name not in _mod.imported_symbols:
                _mod.imported_symbols.append(alias.name)

        self.generic_visit(node)

