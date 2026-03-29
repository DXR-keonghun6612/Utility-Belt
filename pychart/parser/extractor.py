"""Parser Layer.

AST를 활용하여 파이썬 소스 코드에서 IR 데이터를 추출함.
"""
import ast
import sys
from pathlib import Path

from ..definition import Arg_Info, Class_Info, Method_Info, Module_Info
from .registry import NODE, SYMBOL_TABLE
from .constants import IGNORED_MODULES


class Project_Analyzer(ast.NodeVisitor):
    """AST 기반 파이썬 코드 정적 분석기."""

    def __init__(self, project_root: str | None = None) -> None:
        self.ir_data: dict[str, NODE] = {}
        self._current_class_name: str | None = None
        self._current_module_info: Module_Info | None = None
        self._current_package_name: str = ""
        
        self.project_root = Path(project_root or ".").resolve()
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))

    def Analyze_from_roots(self, roots: list[str]) -> dict[str, NODE]:
        """1-Pass 분석: 모든 파일을 독립적으로 파싱하여 전역 심볼 테이블 구축."""
        all_files: list[Path] = []
        # 분석에서 제외할 파일명 정의
        _ignore_files = {"__init__.py", "setup.py", "conftest.py"}

        for r in roots:
            p = Path(r).resolve()
            if p.is_file() and p.suffix == '.py':
                if p.name not in _ignore_files:
                    all_files.append(p)
            elif p.is_dir():
                for f in p.rglob("*.py"):
                    # 가상환경, 숨김 폴더 및 무시 대상 파일 제외
                    if not any((part.startswith('.') or part == 'venv') for part in f.parts):
                        if f.name not in _ignore_files:
                            all_files.append(f)

        for target_file in all_files:
            try:
                rel_path = target_file.relative_to(self.project_root)
            except ValueError:
                continue

            parts = list(rel_path.with_suffix('').parts)
            if parts and parts[-1] == '__init__':
                parts.pop()
            
            mod_name = ".".join(parts)
            self._current_package_name = ".".join(parts[:-1]) if parts else ""
            
            if mod_name in self.ir_data:
                continue

            self._current_module_info = Module_Info(name=mod_name)
            self.ir_data[mod_name] = self._current_module_info

            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    self.visit(tree)
                
                # 전역 레지스트리에 등록
                SYMBOL_TABLE.Register_instance(mod_name, self._current_module_info)
            except (SyntaxError, OSError, KeyError):
                continue

        return self.ir_data

    def _Get_type_str(self, node: ast.AST | None) -> str:
        if node is None:
            return "Any"
        try:
            return ast.unparse(node)
        except Exception:
            return "Unknown"

    def _Parse_function_info(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Method_Info:
        return Method_Info(
            name=node.name,
            args=[Arg_Info(name=arg.arg, type_hint=self._Get_type_str(arg.annotation)) for arg in node.args.args],
            return_type=self._Get_type_str(node.returns),
            docstring=ast.get_docstring(node)
        )

    def visit_Module(self, node: ast.Module) -> None:
        for body_item in node.body:
            if isinstance(body_item, ast.Assign):
                for target in body_item.targets:
                    if isinstance(target, ast.Name):
                        self._Process_module_variable(target.id, body_item.value)
            elif isinstance(body_item, ast.AnnAssign):
                if isinstance(body_item.target, ast.Name):
                    self._Process_module_variable(
                        body_item.target.id, body_item.value, self._Get_type_str(body_item.annotation))
        self.generic_visit(node)

    def _Process_module_variable(self, name: str, value: ast.AST | None, type_hint: str = "Any") -> None:
        _final_type = type_hint
        if _final_type == "Any" and isinstance(value, ast.Call):
            _final_type = self._Get_type_str(value.func)
        if self._current_module_info:
            self._current_module_info.variables.append(Arg_Info(name=name, type_hint=_final_type))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        _bases = [ast.unparse(b) for b in node.bases if isinstance(b, (ast.Name, ast.Attribute))]
        _dec_names = [ast.unparse(d).split('(')[0].split('.')[-1] for d in node.decorator_list]
        _stereotype = ""
        if any("Enum" in b for b in _bases):
            _stereotype = "«enumeration»<br>"
        elif "dataclass" in _dec_names:
            _stereotype = "«dataclass»<br>"

        _cls_info = Class_Info(
            name=node.name, bases=_bases, docstring=ast.get_docstring(node), stereotype=_stereotype)

        for body_item in node.body:
            if isinstance(body_item, ast.AnnAssign):
                if isinstance(body_item.target, ast.Name):
                    _cls_info.attributes.append(Arg_Info(name=body_item.target.id, type_hint=self._Get_type_str(body_item.annotation)))
            elif isinstance(body_item, ast.Assign):
                for target in body_item.targets:
                    if isinstance(target, ast.Name):
                        _type = "EnumMember" if "enumeration" in _stereotype else "Any"
                        _cls_info.attributes.append(Arg_Info(name=target.id, type_hint=_type))

        if self._current_module_info:
            self._current_module_info.classes.append(_cls_info)
        
        _prev_class = self._current_class_name
        self._current_class_name = node.name
        self.generic_visit(node)
        self._current_class_name = _prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        _func_info = self._Parse_function_info(node)
        if self._current_class_name:
            if self._current_module_info:
                _cls = next((c for c in self._current_module_info.classes if c.name == self._current_class_name), None)
                if _cls:
                    _cls.methods.append(_func_info)
                    self._Analyze_class_instance_attributes(_cls, node)
        else:
            if self._current_module_info:
                _func_info.stereotype = "«function»<br>"
                self._current_module_info.functions.append(_func_info)

    def _Analyze_class_instance_attributes(
        self, cls_info: Class_Info, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        class _Instance_Attr_Visitor(ast.NodeVisitor):
            def __init__(self) -> None: self.found_attrs = []
            def visit_Assign(self, node: ast.Assign) -> None:
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                        _type = self._Infer_type(node.value)
                        self.found_attrs.append((target.attr, _type))
                self.generic_visit(node)
            def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
                if isinstance(node.target, ast.Attribute) and isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
                    self.found_attrs.append((node.target.attr, ast.unparse(node.annotation)))
                self.generic_visit(node)
            def _Infer_type(self, value):
                if isinstance(value, ast.Call):
                    return ast.unparse(value.func)
                return "Any"

        visitor = _Instance_Attr_Visitor()
        visitor.visit(node)
        existing_names = {a.name for a in cls_info.attributes}
        for name, _type in visitor.found_attrs:
            if name not in existing_names:
                cls_info.attributes.append(Arg_Info(name=name, type_hint=_type))
                existing_names.add(name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in IGNORED_MODULES: continue
            if self._current_module_info and alias.name not in self._current_module_info.imported_symbols:
                self._current_module_info.imported_symbols.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod_name = node.module or ""
        if node.level > 0 and self._current_package_name:
            parts = self._current_package_name.split('.')
            base = ".".join(parts[:len(parts)-node.level+1])
            mod_name = f"{base}.{mod_name}" if mod_name else base
        if not mod_name or mod_name in IGNORED_MODULES:
            return
        if self._current_module_info and mod_name not in self._current_module_info.imported_symbols:
            self._current_module_info.imported_symbols.append(mod_name)
