"""Editor 데이터 모델 — categorized 결과 로드/교정/저장.

결과 폴더는 `<root>/<class>/<stem>.png` 구조(체크포인트·최종 데이터셋 모두 이 형태).
categorization.json 이 있으면 그것을, 없으면 폴더 구조를 스캔한다. 교정 결과는
workspace 기준 상대경로 + class 로 categorization.json 에 저장한다(확정 포맷).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from python_toolbox.file import Read_from, Write_to


CATEGORIZATION_FILE = "categorization.json"
EXCLUDED = "__excluded__"

_IMAGE_GLOBS = ("*.png", "*.jpg", "*.jpeg")


class Editor_model:
    """class 재지정/제외를 관리하는 평면 엔트리 모델."""

    def __init__(self) -> None:
        self.root: Path | None = None
        self.entries: list[dict] = []   # {rel, path, cls, excluded}
        self.moved: int = 0             # 마지막 save 에서 이동한 파일 수

    # ── 로드 ──────────────────────────────────────────────────────────────────

    def load(self, root: Path) -> None:
        self.root = root
        _json = root / CATEGORIZATION_FILE
        if _json.exists():
            self._load_json(_json, root)
        else:
            self._scan_dirs(root)

    def _load_json(self, json_path: Path, root: Path) -> None:
        _ok, _data = Read_from(json_path)
        _entries: list[dict] = []
        if _ok and isinstance(_data, dict):
            for _cls, _rels in _data.items():
                for _rel in _rels:
                    _entries.append({
                        "rel": _rel, "path": root / _rel,
                        "cls": _cls, "excluded": _cls == EXCLUDED,
                    })
        self.entries = _entries

    def _scan_dirs(self, root: Path) -> None:
        _entries: list[dict] = []
        for _cls_dir in sorted(_p for _p in root.iterdir() if _p.is_dir()):
            _excluded = _cls_dir.name == EXCLUDED
            _files: list[Path] = []
            for _g in _IMAGE_GLOBS:
                _files.extend(_cls_dir.glob(_g))
            for _img in sorted(_files):
                _entries.append({
                    "rel": _img.relative_to(root).as_posix(), "path": _img,
                    "cls": _cls_dir.name, "excluded": _excluded,
                })
        self.entries = _entries

    # ── 조회 ──────────────────────────────────────────────────────────────────

    def classes(self) -> list[str]:
        """제외되지 않은 엔트리의 class 목록 (정렬)."""
        return sorted({_e["cls"] for _e in self.entries if not _e["excluded"]})

    def filtered(self, cls: str | None) -> list[dict]:
        """class 필터(None=전체, EXCLUDED=제외됨)에 맞는 엔트리."""
        if cls is None:
            return [_e for _e in self.entries if not _e["excluded"]]
        if cls == EXCLUDED:
            return [_e for _e in self.entries if _e["excluded"]]
        return [_e for _e in self.entries if _e["cls"] == cls and not _e["excluded"]]

    # ── 교정 ──────────────────────────────────────────────────────────────────

    def reassign(self, rels: set[str], new_cls: str) -> None:
        for _e in self.entries:
            if _e["rel"] in rels:
                _e["cls"] = new_cls
                _e["excluded"] = False

    def exclude(self, rels: set[str]) -> None:
        for _e in self.entries:
            if _e["rel"] in rels:
                _e["excluded"] = True

    def restore(self, rels: set[str]) -> None:
        """제외됨 → 원래 class(폴더명 기준)로 되돌린다."""
        for _e in self.entries:
            if _e["rel"] in rels:
                _e["excluded"] = False

    # ── 저장 ──────────────────────────────────────────────────────────────────

    def save(self) -> Path:
        """교정을 적용한다 — 파일을 현재 class 폴더로 이동 + categorization.json 기록.

        각 엔트리를 `<root>/<class>/<name>.png`(제외는 `<root>/__excluded__/…`)로 물리
        이동해 폴더 구조가 항상 결과를 반영하게 한 뒤, 같은 상대경로로 json 을 쓴다.
        빈 class 폴더는 정리한다.

        Returns:
            기록한 categorization.json 경로.
        """
        if self.root is None:
            raise RuntimeError("로드된 결과 폴더가 없습니다.")

        self.moved = 0
        _used: set[str] = set()

        # 1차: 제자리 유지 항목이 자기 이름을 먼저 차지하도록 예약.
        _pending: list[dict] = []
        for _e in self.entries:
            _cls = EXCLUDED if _e["excluded"] else _e["cls"]
            _desired = f"{_cls}/{Path(_e['rel']).name}"
            if self.root / _desired == Path(_e["path"]) and Path(_e["path"]).exists():
                _used.add(_desired)
            else:
                _pending.append(_e)

        # 2차: 이동 항목에 충돌 없는(덮어쓰지 않는) 고유 이름 배정.
        for _e in _pending:
            _cls = EXCLUDED if _e["excluded"] else _e["cls"]
            _dest_rel = self._unique_rel(_cls, Path(_e["rel"]).name, _used)
            _used.add(_dest_rel)
            _dest = self.root / _dest_rel
            _src = Path(_e["path"])
            _dest.parent.mkdir(parents=True, exist_ok=True)
            if _src.exists() and _src != _dest:
                shutil.move(str(_src), str(_dest))
                self.moved += 1
            _e["rel"] = _dest_rel
            _e["path"] = _dest

        self._cleanup_empty()

        _data: dict[str, list[str]] = {}
        for _e in self.entries:
            _cls = EXCLUDED if _e["excluded"] else _e["cls"]
            _data.setdefault(_cls, []).append(_e["rel"])
        _path = self.root / CATEGORIZATION_FILE
        Write_to(_path, _data)
        return _path

    def _unique_rel(self, cls: str, name: str, used: set[str]) -> str:
        """used 와 디스크 양쪽에서 비어 있는 `<cls>/<name>` 상대경로를 만든다."""
        _rel = f"{cls}/{name}"
        if _rel not in used and not (self.root / _rel).exists():  # type: ignore[operator]
            return _rel
        _stem, _suf = Path(name).stem, Path(name).suffix
        _k = 1
        while True:
            _rel = f"{cls}/{_stem}__{_k}{_suf}"
            if _rel not in used and not (self.root / _rel).exists():  # type: ignore[operator]
                return _rel
            _k += 1

    def _cleanup_empty(self) -> None:
        """비어 버린 class 폴더를 제거한다."""
        if self.root is None:
            return
        for _d in self.root.iterdir():
            if _d.is_dir() and not any(_d.iterdir()):
                _d.rmdir()
