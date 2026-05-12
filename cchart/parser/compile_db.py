"""Compile DB Layer.

CMake가 생성하는 compile_commands.json을 파싱하여 파일별 컴파일 컨텍스트를 제공합니다.
"""
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
        flags: 파싱된 컴파일 플래그 리스트 (-I, -D, -std 등).
    """
    file: Path
    directory: Path
    flags: list[str] = field(default_factory=list)


class Compile_DB:
    """compile_commands.json 기반 컴파일 데이터베이스.

    Args:
        db_path: compile_commands.json 파일 경로.
        root_filter: 지정 시 해당 디렉토리 하위 파일만 포함.
        namespace_filter: 지정 시 해당 namespace만 분석 대상으로 제한 (extractor 단에서 적용).
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

        for entry in _raw:
            _file = Path(entry["file"])
            if not _file.is_absolute():
                _file = Path(entry.get("directory", ".")) / _file
            _file = _file.resolve()

            # root_filter 적용: 지정된 루트 하위 파일만 포함
            if self.root_filter and not _file.is_relative_to(self.root_filter):
                continue

            _dir = Path(entry.get("directory", ".")).resolve()
            _flags = self._parse_flags(entry)
            self._entries[_file] = Compile_Entry(file=_file, directory=_dir, flags=_flags)

    def _parse_flags(self, entry: dict) -> list[str]:
        """컴파일 엔트리에서 분석에 유효한 플래그만 추출함."""
        if "arguments" in entry:
            tokens = list(entry["arguments"])
        else:
            tokens = shlex.split(entry.get("command", ""))

        _flags = []
        _i = 0
        while _i < len(tokens):
            token = tokens[_i]

            # 분리된 형태: -I /path, -isystem /path, -include /path
            if token in ("-I", "-isystem", "-include"):
                _flags.append(token)
                _i += 1
                if _i < len(tokens):
                    _flags.append(tokens[_i])

            # 붙어있는 형태: -I/path, -DFOO, -std=c++17
            elif any(token.startswith(p) for p in ("-I", "-D", "-U", "-std=", "-isystem")):
                _flags.append(token)

            _i += 1

        return _flags

    def Get_entry(self, file: Path) -> Compile_Entry | None:
        """파일 경로에 해당하는 컴파일 엔트리를 반환함."""
        return self._entries.get(file.resolve())

    def Get_all_files(self) -> list[Path]:
        """분석 대상 파일 경로 리스트를 반환함."""
        return [e.file for e in self._entries.values()]

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        _filter = f", root={self.root_filter}" if self.root_filter else ""
        return f"Compile_DB({self._path}{_filter}, {len(self)} files)"
