"""Parser Layer (C/C++).

libclang AST를 활용하여 단일 번역 단위에서 IR 데이터를 추출합니다.
"""
from pathlib import Path

try:
    import clang.cindex as ci
    _CLANG_AVAILABLE = True
except ImportError:
    _CLANG_AVAILABLE = False

from core.definition import Arg_Info
from cchart.definition import CXX_Method_Info, CXX_Class_Info, Translation_Unit_Info
from cchart.registry import SYMBOL_TABLE
from cchart.parser.compile_db import Compile_DB
from cchart.parser.utils import Is_system_header, Make_file_key


class CXX_Analyzer:
    """libclang 기반 C/C++ 소스 코드 정적 분석기.

    Args:
        compile_db: 파일별 컴파일 컨텍스트를 담은 Compile_DB 인스턴스.
        project_root: 파일 키 생성 기준 루트 경로.
        namespace_filter: 지정 시 해당 namespace에 속하는 심볼만 추출.
    """

    def __init__(
        self,
        compile_db: Compile_DB,
        project_root: str | Path | None = None,
        namespace_filter: list[str] | None = None,
    ) -> None:
        if not _CLANG_AVAILABLE:
            raise ImportError("[ERROR] libclang Python 바인딩이 설치되어 있지 않습니다. 'pip install libclang'")

        self._index = ci.Index.create()
        self._compile_db = compile_db
        self.project_root = Path(project_root).resolve() if project_root else Path(".").resolve()
        self.namespace_filter = set(namespace_filter) if namespace_filter else set()
        self.ir_data: dict[str, Translation_Unit_Info] = {}

    def Parse_file(self, file_path: Path) -> bool:
        """단일 파일 파싱 및 심볼 테이블 등록 수행."""
        _file_path = file_path.resolve()
        _entry = self._compile_db.Get_entry(_file_path)
        _flags = _entry.flags if _entry else []
        _file_key = Make_file_key(_file_path, self.project_root)

        if _file_key in self.ir_data:
            return False

        try:
            _tu = self._index.parse(
                str(_file_path),
                args=_flags,
                options=ci.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
            )
        except Exception:
            return False

        _tu_info = Translation_Unit_Info(
            name=_file_path.name,
            file_path=str(_file_path),
            compile_flags=_flags,
        )
        self.ir_data[_file_key] = _tu_info
        self._visit_cursor(_tu.cursor, _tu_info, _file_path)

        SYMBOL_TABLE.Register_instance(_file_key, _tu_info)
        return True

    # =========================================================================
    # [Sector 1] Cursor 순회
    # =========================================================================

    def _visit_cursor(
        self, cursor, tu_info: Translation_Unit_Info, source_file: Path,
        namespace_path: str = "",
    ) -> None:
        for child in cursor.get_children():
            _loc_file = child.location.file
            if _loc_file and Path(_loc_file.name).resolve() != source_file:
                continue

            if child.kind == ci.CursorKind.NAMESPACE:
                _ns = f"{namespace_path}::{child.spelling}" if namespace_path else child.spelling
                self._visit_cursor(child, tu_info, source_file, _ns)

            elif child.kind in (ci.CursorKind.CLASS_DECL, ci.CursorKind.STRUCT_DECL,
                                 ci.CursorKind.UNION_DECL):
                if not child.is_definition():
                    continue
                _cls = self._extract_class(child, namespace_path)
                if _cls and self._passes_namespace_filter(_cls.namespace_path):
                    tu_info.classes.append(_cls)

            elif child.kind == ci.CursorKind.FUNCTION_DECL:
                if not child.is_definition():
                    continue
                _func = self._extract_function(child)
                if _func and self._passes_namespace_filter(namespace_path):
                    tu_info.functions.append(_func)

            elif child.kind == ci.CursorKind.INCLUSION_DIRECTIVE:
                _inc = child.get_included_file()
                if _inc and not Is_system_header(_inc.name):
                    tu_info.includes.append(_inc.name)

    # =========================================================================
    # [Sector 2] 심볼 추출
    # =========================================================================

    def _extract_class(self, cursor, namespace_path: str) -> CXX_Class_Info | None:
        if not cursor.spelling:
            return None

        _kind_map = {
            ci.CursorKind.STRUCT_DECL: "struct",
            ci.CursorKind.UNION_DECL: "union",
        }
        _kind = _kind_map.get(cursor.kind, "class")

        _bases, _methods, _attrs = [], [], []

        for child in cursor.get_children():
            if child.kind == ci.CursorKind.CXX_BASE_SPECIFIER:
                _bases.append(child.spelling.replace("class ", "").replace("struct ", "").strip())

            elif child.kind in (ci.CursorKind.CXX_METHOD,
                                 ci.CursorKind.CONSTRUCTOR,
                                 ci.CursorKind.DESTRUCTOR):
                _m = self._extract_method(child)
                if _m:
                    _methods.append(_m)

            elif child.kind == ci.CursorKind.FIELD_DECL:
                _attrs.append(Arg_Info(
                    name=child.spelling,
                    type_hint=child.type.spelling,
                ))

        return CXX_Class_Info(
            name=cursor.spelling,
            bases=_bases,
            attributes=_attrs,
            methods=_methods,
            kind=_kind,
            namespace_path=namespace_path,
            stereotype=self._get_class_stereotype(cursor),
        )

    def _extract_method(self, cursor) -> CXX_Method_Info | None:
        if not cursor.spelling:
            return None

        _args = [
            Arg_Info(
                name=arg.spelling or f"p{i}",
                type_hint=arg.type.spelling,
            )
            for i, arg in enumerate(cursor.get_arguments())
        ]

        _return_type = (
            cursor.result_type.spelling
            if cursor.kind not in (ci.CursorKind.CONSTRUCTOR, ci.CursorKind.DESTRUCTOR)
            else "void"
        )

        _is_override = len(list(cursor.get_overridden_cursors())) > 0

        return CXX_Method_Info(
            name=cursor.spelling,
            args=_args,
            return_type=_return_type,
            access=self._get_access(cursor),
            is_virtual=cursor.is_virtual_method(),
            is_override=_is_override,
            is_const=cursor.is_const_method(),
            is_static=cursor.is_static_method(),
            is_pure_virtual=cursor.is_pure_virtual_method(),
        )

    def _extract_function(self, cursor) -> CXX_Method_Info | None:
        if not cursor.spelling:
            return None

        _args = [
            Arg_Info(
                name=arg.spelling or f"p{i}",
                type_hint=arg.type.spelling,
            )
            for i, arg in enumerate(cursor.get_arguments())
        ]

        return CXX_Method_Info(
            name=cursor.spelling,
            args=_args,
            return_type=cursor.result_type.spelling,
            stereotype="«function»",
        )

    # =========================================================================
    # [Sector 3] 헬퍼
    # =========================================================================

    def _get_access(self, cursor) -> str:
        _map = {
            ci.AccessSpecifier.PUBLIC: "public",
            ci.AccessSpecifier.PROTECTED: "protected",
            ci.AccessSpecifier.PRIVATE: "private",
        }
        return _map.get(cursor.access_specifier, "public")

    def _get_class_stereotype(self, cursor) -> str:
        """순수 가상 함수가 있으면 «interface» 스테레오타입을 부여함."""
        for child in cursor.get_children():
            if child.kind == ci.CursorKind.CXX_METHOD and child.is_pure_virtual_method():
                return "«interface»"
        return ""

    def _passes_namespace_filter(self, namespace_path: str) -> bool:
        """namespace_filter가 비어있으면 전부 통과, 아니면 매칭 여부 반환."""
        if not self.namespace_filter:
            return True
        return any(
            namespace_path == ns or namespace_path.startswith(f"{ns}::")
            for ns in self.namespace_filter
        )
