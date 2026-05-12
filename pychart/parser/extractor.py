"""Parser Layer.

AST를 활용하여 단일 파이썬 소스 코드에서 IR 데이터를 추출함.
"""
import ast
from pathlib import Path

from pychart.definition import Arg_Info, Class_Info, Module_Info
from pychart.registry import NODE, SYMBOL_TABLE
from pychart.parser.constants import (
    IGNORED_FILES,
    IGNORED_MODULES,
    TYPE_ANY,
    STEREOTYPE_ENUM,
    STEREOTYPE_DATACLASS,
    STEREOTYPE_FUNC,
)
from pychart.parser.utils import (
    Get_type_str, 
    Parse_function_info, 
    Infer_assign_type, 
    Extract_instance_attributes,
)


class Project_Analyzer(ast.NodeVisitor):
    """AST 기반 파이썬 코드 정적 분석기."""

    def __init__(self, project_root: str | None = None) -> None:
        self.ir_data: dict[str, NODE] = {}
        # 컨텍스트 상태 추적기
        self._this_module: Module_Info | None = None
        self._current_class_name: str | None = None
        self._current_package_name: str = ""
        
        self.project_root = Path(project_root or ".").resolve()

    def Parse_file(self, file_path: Path) -> bool:
        """단일 파일 분석 및 심볼 테이블 등록 수행."""
        # 기본 예외 처리
        if file_path.suffix != ".py" or file_path.name in IGNORED_FILES:
            return False

        _rel_path = file_path.relative_to(self.project_root)
        _file_key = str(_rel_path)

        # 중복 파싱 방지
        if _file_key in self.ir_data:
            return False

        _this_module = Module_Info(name=_file_key)

        # 상태 및 패키지 컨텍스트 초기화
        self.ir_data[_file_key] = _this_module
        self._this_module = _this_module
        
        _parent_parts = _rel_path.parent.parts
        if _parent_parts:
            self._current_package_name = ".".join(_parent_parts)
        else:
            self._current_package_name = ""
        
        try:
            # 트랜잭션 시작
            with open(file_path, "r", encoding="utf-8") as f:
                self.visit(ast.parse(f.read()))

            SYMBOL_TABLE.Register_instance(_file_key, _this_module)
        except (SyntaxError, OSError, KeyError):
            # 트랜잭션 롤백
            if _file_key in self.ir_data:
                del self.ir_data[_file_key]
            self._this_module = None
            return False

        return True

    # =====================================================================
    # [Sector 1] Scope & Structural Nodes
    # =====================================================================

    def visit_Module(self, node: ast.Module) -> None:
        """모듈 진입점 및 전역 변수 추출."""
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and self._this_module:
                        _type = Infer_assign_type(item.value)
                        _arg = Arg_Info(name=target.id, type_hint=_type)
                        self._this_module.variables.append(_arg)
                        
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name) and self._this_module:
                    _hint = Get_type_str(item.annotation)
                    _type = Infer_assign_type(item.value, _hint)
                    _arg = Arg_Info(name=item.target.id, type_hint=_type)
                    self._this_module.variables.append(_arg)
                    
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """클래스 정의 및 클래스 변수 추출."""
        _bases = []
        for b in node.bases:
            if isinstance(b, (ast.Name, ast.Attribute)):
                _bases.append(ast.unparse(b))

        _dec_names = []
        for d in node.decorator_list:
            _name = ast.unparse(d).split('(')[0].split('.')[-1]
            _dec_names.append(_name)

        # 스테레오타입 결정
        _stereotype = ""
        if any("Enum" in b for b in _bases):
            _stereotype = STEREOTYPE_ENUM
        elif "dataclass" in _dec_names:
            _stereotype = STEREOTYPE_DATACLASS

        _cls_info = Class_Info(
            name=node.name, 
            bases=_bases, 
            docstring=ast.get_docstring(node), 
            stereotype=_stereotype
        )

        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    _hint = Get_type_str(item.annotation)
                    _arg = Arg_Info(name=item.target.id, type_hint=_hint)
                    _cls_info.attributes.append(_arg)
                    
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        _type = "EnumMember" if _stereotype else TYPE_ANY
                        _arg = Arg_Info(name=target.id, type_hint=_type)
                        _cls_info.attributes.append(_arg)

        if self._this_module:
            self._this_module.classes.append(_cls_info)
        
        # 스코프 관리
        _prev_class = self._current_class_name
        self._current_class_name = node.name
        self.generic_visit(node)
        self._current_class_name = _prev_class

    def visit_FunctionDef(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """함수/메서드 추출 및 인스턴스 속성 분석."""
        _func_info = Parse_function_info(node)
        
        if self._current_class_name and self._this_module:
            _target_cls = None
            for cls_info in self._this_module.classes:
                if cls_info.name == self._current_class_name:
                    _target_cls = cls_info
                    break
                    
            if _target_cls:
                _target_cls.methods.append(_func_info)
                _existing_names = {a.name for a in _target_cls.attributes}
                _new_attrs = Extract_instance_attributes(node, _existing_names)
                _target_cls.attributes.extend(_new_attrs)
                
        elif self._this_module:
            _func_info.stereotype = STEREOTYPE_FUNC
            self._this_module.functions.append(_func_info)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """비동기 함수 처리."""
        self.visit_FunctionDef(node)

    # =====================================================================
    # [Sector 2] Data Binding & Variables
    # =====================================================================

    def visit_Import(self, node: ast.Import) -> None:
        """절대 임포트 식별자 수집."""
        for alias in node.names:
            if alias.name in IGNORED_MODULES: 
                continue
            if self._this_module:
                self._this_module.imported_symbols.setdefault(alias.name, [])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """상대/절대 from-import 식별자 수집."""
        _mod_name = node.module or ""
        
        # 상대 경로 계산
        if node.level > 0 and self._current_package_name:
            _parts = self._current_package_name.split('.')
            _base = ".".join(_parts[:len(_parts) - node.level + 1])
            _mod_name = f"{_base}.{_mod_name}" if _mod_name else _base
            
        if not _mod_name or _mod_name in IGNORED_MODULES:
            return
            
        if self._this_module:
            _imports = self._this_module.imported_symbols.setdefault(
                _mod_name, []
            )
            for alias in node.names:
                if alias.name not in _imports:
                    _imports.append(alias.name)