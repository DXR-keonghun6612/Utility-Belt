"""C/C++ Extractor — 01_parser 단계의 C/C++ 구현.

libclang AST를 순회하여 IR(``Translation_Unit_Info``)을 생성하고,
무효화 메타(의존 파일 목록, 컨텍스트 해시)를 함께 반환한다.

분류(stereotype)는 부여하지 않음 — 02_classifier 책임.
"""
from __future__ import annotations
from pathlib import Path
from typing import ClassVar

try:
    import clang.cindex as ci
    _CLANG_AVAILABLE = True
except ImportError:
    _CLANG_AVAILABLE = False

from core.definition import Arg_Info
from core.hashing import Hash_context
from cchart.definition import CXX_Method_Info, CXX_Class_Info, Translation_Unit_Info

from .compile_db import Compile_DB
from .constants import LANGUAGE
from .utils import Is_system_header, Make_file_key, Make_node_id


class CXX_Extractor:
    """libclang 기반 C/C++ 소스 추출기 (:class:`parser.protocol.Parser_Protocol` 구현).

    Args:
        compile_db: 파일별 컴파일 컨텍스트.
        project_root: ``file_key`` 산출 기준 루트 경로.
        namespace_filter: 지정 시 해당 namespace에 속하는 심볼만 추출.
    """

    language: ClassVar[str] = LANGUAGE

    def __init__(
        self,
        compile_db: Compile_DB,
        project_root: str | Path | None = None,
        namespace_filter: list[str] | None = None,
    ) -> None:
        if not _CLANG_AVAILABLE:
            raise ImportError(
                "[ERROR] libclang Python 바인딩이 설치되어 있지 않습니다. "
                "'pip install libclang'"
            )
        self._index = ci.Index.create()
        self._compile_db = compile_db
        self.project_root = (
            Path(project_root).resolve() if project_root else Path(".").resolve()
        )
        self.namespace_filter: set[str] = set(namespace_filter or [])

    # =========================================================================
    # Parser_Protocol 진입점
    # =========================================================================
    def Parse_file(
        self, path: Path
    ) -> tuple[Translation_Unit_Info, list[Path], str]:
        """단일 파일 파싱.

        Returns:
            (IR ``Translation_Unit_Info``, 의존 파일 절대 경로 목록, 컨텍스트 해시).
        """
        _file_path = path.resolve()
        _entry = self._compile_db.Get_entry(_file_path)
        _flags = _entry.flags if _entry else []
        _file_key = Make_file_key(_file_path, self.project_root)

        _tu = self._index.parse(
            str(_file_path),
            args=_flags,
            options=ci.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
        )

        _module = Translation_Unit_Info(
            name=_file_path.name,
            file_path=str(_file_path),
            id=_file_key,
            compile_flags=_flags,
            origin="internal",
        )
        self._visit_cursor(_tu.cursor, _module, _file_path, _file_key)

        _deps = self._extract_dependencies(_tu)
        _ctx_hash = Hash_context({"language": LANGUAGE, "flags": _flags})

        return _module, _deps, _ctx_hash

    # =========================================================================
    # [Sector 1] Cursor 순회
    # =========================================================================
    def _visit_cursor(
        self,
        cursor,
        module: Translation_Unit_Info,
        source_file: Path,
        file_key: str,
        namespace_path: str = "",
    ) -> None:
        for _child in cursor.get_children():
            _loc_file = _child.location.file
            if _loc_file and Path(_loc_file.name).resolve() != source_file:
                continue

            if _child.kind == ci.CursorKind.NAMESPACE:
                _ns = (
                    f"{namespace_path}::{_child.spelling}"
                    if namespace_path else _child.spelling
                )
                self._visit_cursor(_child, module, source_file, file_key, _ns)

            elif _child.kind in (
                ci.CursorKind.CLASS_DECL,
                ci.CursorKind.STRUCT_DECL,
                ci.CursorKind.UNION_DECL,
            ):
                if not _child.is_definition():
                    continue
                _cls = self._extract_class(_child, namespace_path, file_key)
                if _cls and self._passes_namespace_filter(_cls.namespace_path):
                    module.classes.append(_cls)

            elif _child.kind == ci.CursorKind.FUNCTION_DECL:
                if not _child.is_definition():
                    continue
                _func = self._extract_function(_child, namespace_path, file_key)
                if _func and self._passes_namespace_filter(namespace_path):
                    module.functions.append(_func)

            elif _child.kind == ci.CursorKind.INCLUSION_DIRECTIVE:
                _inc = _child.get_included_file()
                if _inc and not Is_system_header(_inc.name):
                    module.includes.append(_inc.name)

    # =========================================================================
    # [Sector 2] 심볼 추출
    # =========================================================================
    def _extract_class(
        self, cursor, namespace_path: str, file_key: str
    ) -> CXX_Class_Info | None:
        if not cursor.spelling:
            return None

        _kind_map = {
            ci.CursorKind.STRUCT_DECL: "struct",
            ci.CursorKind.UNION_DECL: "union",
        }
        _kind = _kind_map.get(cursor.kind, "class")

        _bases: list[str] = []
        _methods: list[CXX_Method_Info] = []
        _attrs: list[Arg_Info] = []
        _template_params: list[str] = []

        _inner_ns = (
            f"{namespace_path}::{cursor.spelling}"
            if namespace_path else cursor.spelling
        )

        for _child in cursor.get_children():
            _ck = _child.kind

            if _ck == ci.CursorKind.CXX_BASE_SPECIFIER:
                # libclang이 제공하는 fully qualified name 우선
                _base_t = _child.type.spelling if _child.type else _child.spelling
                _bases.append(
                    _base_t.replace("class ", "").replace("struct ", "").strip()
                )

            elif _ck in (
                ci.CursorKind.CXX_METHOD,
                ci.CursorKind.CONSTRUCTOR,
                ci.CursorKind.DESTRUCTOR,
            ):
                _m = self._extract_method(_child, file_key, _inner_ns)
                if _m:
                    _methods.append(_m)

            elif _ck == ci.CursorKind.FIELD_DECL:
                _attrs.append(Arg_Info(
                    name=_child.spelling,
                    type_hint=_child.type.spelling,
                    access=self._get_access(_child),
                    source_line=_child.location.line if _child.location else None,
                ))

            elif _ck in (
                ci.CursorKind.TEMPLATE_TYPE_PARAMETER,
                ci.CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
                ci.CursorKind.TEMPLATE_TEMPLATE_PARAMETER,
            ):
                _template_params.append(_child.spelling)

        return CXX_Class_Info(
            name=cursor.spelling,
            bases=_bases,
            attributes=_attrs,
            methods=_methods,
            id=Make_node_id(file_key, namespace_path, cursor.spelling),
            kind=_kind,
            namespace_path=namespace_path,
            template_params=_template_params,
            source_line=cursor.location.line if cursor.location else None,
            # abstraction / traits / origin은 dataclass 기본값 (02가 갱신)
        )

    def _extract_method(
        self, cursor, file_key: str, owner_ns: str
    ) -> CXX_Method_Info | None:
        if not cursor.spelling:
            return None

        _args = [
            Arg_Info(
                name=_arg.spelling or f"p{_i}",
                type_hint=_arg.type.spelling,
            )
            for _i, _arg in enumerate(cursor.get_arguments())
        ]
        _return_type = (
            cursor.result_type.spelling
            if cursor.kind not in (
                ci.CursorKind.CONSTRUCTOR, ci.CursorKind.DESTRUCTOR
            )
            else "void"
        )

        return CXX_Method_Info(
            name=cursor.spelling,
            args=_args,
            return_type=_return_type,
            id=Make_node_id(file_key, owner_ns, cursor.spelling),
            access=self._get_access(cursor),
            is_virtual=cursor.is_virtual_method(),
            is_const=cursor.is_const_method(),
            is_static=cursor.is_static_method(),
            is_pure_virtual=cursor.is_pure_virtual_method(),
            is_override=self._has_token(cursor, "override"),
            is_final=self._has_token(cursor, "final"),
            is_noexcept=self._has_token(cursor, "noexcept"),
            source_line=cursor.location.line if cursor.location else None,
        )

    def _extract_function(
        self, cursor, namespace_path: str, file_key: str
    ) -> CXX_Method_Info | None:
        if not cursor.spelling:
            return None

        _args = [
            Arg_Info(
                name=_arg.spelling or f"p{_i}",
                type_hint=_arg.type.spelling,
            )
            for _i, _arg in enumerate(cursor.get_arguments())
        ]

        return CXX_Method_Info(
            name=cursor.spelling,
            args=_args,
            return_type=cursor.result_type.spelling,
            id=Make_node_id(file_key, namespace_path, cursor.spelling),
            is_noexcept=self._has_token(cursor, "noexcept"),
            source_line=cursor.location.line if cursor.location else None,
        )

    # =========================================================================
    # [Sector 3] 메타데이터
    # =========================================================================
    def _extract_dependencies(self, tu) -> list[Path]:
        """transitive include 절대 경로 (시스템 헤더 제외).

        C++의 무효화 정확도를 위해 ``tu.get_includes()``의 전이적 결과를
        사용한다 — 단일 파일 해시만으로는 헤더 변경을 잡지 못함.
        """
        _seen: set[Path] = set()
        _result: list[Path] = []
        for _file_inc in tu.get_includes():
            _path = Path(_file_inc.include.name).resolve()
            if Is_system_header(str(_path)):
                continue
            if _path in _seen:
                continue
            _seen.add(_path)
            _result.append(_path)
        return _result

    # =========================================================================
    # [Sector 4] 헬퍼
    # =========================================================================
    def _get_access(self, cursor) -> str:
        _map = {
            ci.AccessSpecifier.PUBLIC: "public",
            ci.AccessSpecifier.PROTECTED: "protected",
            ci.AccessSpecifier.PRIVATE: "private",
        }
        return _map.get(cursor.access_specifier, "public")

    def _has_token(self, cursor, keyword: str) -> bool:
        """cursor 토큰 중 ``keyword`` 존재 여부 (override/final/noexcept 검사용)."""
        try:
            return any(_t.spelling == keyword for _t in cursor.get_tokens())
        except Exception:
            return False

    def _passes_namespace_filter(self, namespace_path: str) -> bool:
        if not self.namespace_filter:
            return True
        return any(
            namespace_path == _ns or namespace_path.startswith(f"{_ns}::")
            for _ns in self.namespace_filter
        )
