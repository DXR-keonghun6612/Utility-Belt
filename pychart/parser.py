"""Parser Layer.

AST를 활용하여 파이썬 소스 코드에서 IR 데이터를 추출함.
"""
import ast
from pathlib import Path
from definition import Class_Info, Method_Info, Arg_Info

class Project_Analyzer(ast.NodeVisitor):
    """AST 기반 파이썬 코드 정적 분석기.
    
    Attributes:
        classes: 추출된 클래스 정보 매핑 딕셔너리.
    """

    def __init__(self) -> None:
        """초기화."""
        self.classes: dict[str, Class_Info] = {}

    def Analyze_directory(self, target_dir: str) -> dict[str, Class_Info]:
        """지정된 디렉토리를 순회하며 모든 파이썬 코드를 분석함.
        
        Args:
            target_dir: 분석할 프로젝트 루트 디렉토리.
            
        Returns:
            Dict[str, ClassInfo]: 추출된 IR 데이터 모델.
        """
        _target_path = Path(target_dir).resolve()

        if not _target_path.is_dir():
            raise NotADirectoryError(f"유효하지 않은 디렉토리입니다: {_target_path}")

        for py_file in _target_path.rglob("*.py"):
            # 가상환경 및 숨김 폴더 제외
            if any(part.startswith('.') or part == 'venv' for part in py_file.parts):
                continue
                
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    self.visit(tree)
            except SyntaxError:
                # 문법 오류가 있는 파일은 건너뜀
                continue
                
        return self.classes

    def _Get_type_str(self, node: ast.AST | None) -> str:
        """AST 노드 타입 문자열 변환.

        Args:
            node: AST 노드 객체.

        Returns:
            str: 변환된 타입 문자열.
        """
        if node is None:
            return "Any"
        try:
            return ast.unparse(node)
        except Exception:
            return "Unknown"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """클래스 정의부 방문 및 정보 추출.

        Args:
            node: 클래스 정의 AST 노드.
        """
        # 상속 및 Docstring 추출
        _bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        _docstring = ast.get_docstring(node)

        _cls_info = Class_Info(
            name=node.name, bases=_bases, docstring=_docstring)

        # 클래스 내부 순회
        for body_item in node.body:
            # 메서드 추출
            if isinstance(body_item, ast.FunctionDef):
                _m_doc = ast.get_docstring(body_item)
                _m_ret = self._Get_type_str(body_item.returns)
                _m_args = [
                    Arg_Info(name=arg.arg, type_hint=self._Get_type_str(arg.annotation))
                    for arg in body_item.args.args
                ]
                _cls_info.methods.append(
                    Method_Info(
                        name=body_item.name,
                        args=_m_args,
                        return_type=_m_ret,
                        docstring=_m_doc
                    )
                )

            # 타입 힌트가 포함된 속성 추출
            elif isinstance(body_item, ast.AnnAssign):
                if isinstance(body_item.target, ast.Name):
                    _cls_info.attributes.append(
                        Arg_Info(
                            name=body_item.target.id,
                            type_hint=self._Get_type_str(body_item.annotation)
                        )
                    )

        self.classes[node.name] = _cls_info
        self.generic_visit(node)
