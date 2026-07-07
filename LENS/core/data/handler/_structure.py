"""구조 사이드카 핸들러 — Node 서브트리(``Serialize`` 결과)를 ``{root}/{SIDECAR_DIR}/{stem}.json`` 로 I/O.

payload 핸들러(image/array/attr…)가 ``ref.type`` 로 디스패치되는 **leaf 파일** I/O 라면, 이건 그 대칭 —
Node 트리 구조를 담는 **고정 json 핸들러**다(디스패치 없음, 언제나 ``.meta/*.json``). ``Data_Ref`` 의 leaf
가 ``name`` 을 키로 경로를 잡듯, 구조는 ``.meta`` + ``stem`` 을 키로 잡을 뿐 구조가 같다. schema 가 fs 경로를
직접 조립하지 않도록(경로 파생 단일 진실원천 = handler) 구조 I/O 를 여기로 모았다. 다른 핸들러와 같은
**stateless classmethod** 스타일 — registry 에는 안 올린다(type 으로 고르는 대상이 아니라 항상 이거다).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from python_toolbox.file import Read_from, Write_to


SIDECAR_DIR: str = ".meta"   # scope 별 구조 사이드카 하위 폴더 (경로 단일 진실원천)


class Structure:
    """Node 구조 사이드카(``{root}/.meta/{stem}.json``)의 read/write/delete/enumerate (상태 없음)."""

    @classmethod
    def _path(cls, root: str, stem: str) -> Path:
        """사이드카 파일 경로 = ``{root}/{SIDECAR_DIR}/{stem}.json``."""
        return Path(root) / SIDECAR_DIR / f"{stem}.json"

    @classmethod
    def Write(cls, root: str, stem: str, payload: dict) -> None:
        """구조 JSON(``payload``)을 사이드카로 쓴다 (부모 dir 보장 + write)."""
        _p = cls._path(root, stem)
        _p.parent.mkdir(parents=True, exist_ok=True)
        Write_to(_p, payload)

    @classmethod
    def Read(cls, root: str, stem: str) -> dict | None:
        """사이드카를 읽어 dict 반환 (없거나 깨졌으면 None — 조용한 기본값 대신 부재를 알림)."""
        _p = cls._path(root, stem)
        if not _p.exists():
            return None
        _ok, _d = Read_from(_p)
        return _d if _ok and isinstance(_d, dict) else None

    @classmethod
    def Delete(cls, root: str, stem: str) -> None:
        """사이드카 파일을 지운다 (없으면 no-op)."""
        cls._path(root, stem).unlink(missing_ok=True)

    @classmethod
    def Move(cls, src_root: str, dst_root: str, stem: str) -> None:
        """사이드카를 ``src_root`` → ``dst_root`` 로 옮긴다 (없으면 no-op; 상태 전이용)."""
        _src = cls._path(src_root, stem)
        if not _src.exists():
            return
        _dst = cls._path(dst_root, stem)
        _dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(_src), str(_dst))

    @classmethod
    def Stems(cls, root: str) -> list[str]:
        """``{root}/.meta`` 의 사이드카 stem 목록 (정렬; dir 없으면 빈 리스트). 부트로드 열거용."""
        _dir = Path(root) / SIDECAR_DIR
        if not _dir.is_dir():
            return []
        return [_p.stem for _p in sorted(_dir.glob("*.json"))]
