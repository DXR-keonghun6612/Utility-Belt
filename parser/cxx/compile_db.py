"""Compile DB Layer (C/C++ 전용).

CMake가 생성하는 ``compile_commands.json``을 파싱하여 파일별 컴파일
컨텍스트를 제공합니다. ``CXX_Extractor``의 입력 진입점.
"""
from __future__ import annotations
import shlex
from pathlib import Path
from dataclasses import dataclass, field

from python_toolbox.file import Read_from


@dataclass
class Compile_Entry:
    """단일 파일의 컴파일 컨텍스트.

    Attributes:
        file: 소스 파일 절대 경로.
        directory: 컴파일 기준 디렉토리.
        flags: 분석에 유효한 컴파일 플래그 (``-I`` / ``-D`` / ``-std=`` 등).
    """
    file: Path
    directory: Path
    flags: list[str] = field(default_factory=list)


class Compile_DB:
    """``compile_commands.json`` 기반 컴파일 데이터베이스.

    Args:
        db_path: ``compile_commands.json`` 파일 경로.
        root_filter: 지정 시 해당 디렉토리 하위 파일만 포함.
        namespace_filter: 지정 시 해당 namespace만 분석 대상으로 제한
            (실 필터링은 extractor 단에서 수행).
    """

    def __init__(
        self,
        db_path: str | Path,
        root_filter: str | Path | None = None,
        namespace_filter: list[str] | None = None,
    ) -> None:
        self._path = Path(db_path).resolve()
        self.root_filter = Path(root_filter).resolve() if root_filter else None
        self.namespace_filter = namespace_filter or []
        self._entries: dict[Path, Compile_Entry] = {}
        self._load()

    def _load(self) -> None:
        _ok, _raw = Read_from(self._path)
        if not _ok or not isinstance(_raw, list):
            raise ValueError(f"[ERROR] compile_commands.json 로드 실패: {self._path}")

        for _entry in _raw:
            _file = Path(_entry["file"])
            if not _file.is_absolute():
                _file = Path(_entry.get("directory", ".")) / _file
            _file = _file.resolve()

            if self.root_filter and not _file.is_relative_to(self.root_filter):
                continue

            _dir = Path(_entry.get("directory", ".")).resolve()
            _flags = self._parse_flags(_entry)
            self._entries[_file] = Compile_Entry(
                file=_file, directory=_dir, flags=_flags
            )

    def _parse_flags(self, entry: dict) -> list[str]:
        """컴파일 엔트리에서 분석에 유효한 플래그만 추출합니다."""
        _tokens = (
            list(entry["arguments"])
            if "arguments" in entry
            else shlex.split(entry.get("command", ""))
        )

        _flags: list[str] = []
        _i = 0
        while _i < len(_tokens):
            _t = _tokens[_i]
            if _t in ("-I", "-isystem", "-include"):
                _flags.append(_t)
                _i += 1
                if _i < len(_tokens):
                    _flags.append(_tokens[_i])
            elif any(_t.startswith(_p) for _p in ("-I", "-D", "-U", "-std=", "-isystem")):
                _flags.append(_t)
            _i += 1
        return _flags

    def Get_entry(self, file: Path) -> Compile_Entry | None:
        """파일 경로에 해당하는 컴파일 엔트리를 반환합니다."""
        return self._entries.get(file.resolve())

    def Get_all_files(self) -> list[Path]:
        """분석 대상 파일 경로 리스트를 반환합니다."""
        return [_e.file for _e in self._entries.values()]

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        _filter = f", root={self.root_filter}" if self.root_filter else ""
        return f"Compile_DB({self._path}{_filter}, {len(self)} files)"
