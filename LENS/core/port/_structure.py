"""구조 사이드카 핸들러 — item 서브트리(``Serialize`` 결과)를 ``{root}/.meta/<key-path>.json`` 로 I/O.

payload 핸들러(image/array/attr…)가 ``format[0]`` 로 디스패치되는 **leaf 파일** I/O 라면, 이건 그 대칭 —
item 트리 구조를 담는 **고정 json 핸들러**다(디스패치 없음, 언제나 ``.meta/*.json``). leaf 가 ``path``+``name``
으로 경로를 잡듯 구조는 ``.meta``+``keys`` 로 잡을 뿐 규칙이 같다(경로 = 재귀 key 뭉치기). schema 가 fs 경로를
직접 조립하지 않도록 구조 I/O 를 여기로 모았다. 다른 핸들러와 같은 **stateless classmethod** 스타일 —
registry 에는 안 올린다(``format[0]`` 로 고르는 대상이 아니라 구조 사이드카면 항상 이거다).
"""

from __future__ import annotations

from pathlib import Path

from python_toolbox.file import Read_from, Write_to


SIDECAR_DIR: str = ".meta"   # scope 별 구조 사이드카 하위 폴더 (경로 단일 진실원천)


class Structure:
    """Node 구조 사이드카(``{root}/.meta/<key-path>.json``)의 read/write/delete/walk (상태 없음).

    경로 = ``.meta`` 아래 **재귀 key 뭉치기** — ``keys=(cat, stem)`` 이면 ``.meta/{cat}/{stem}.json``.
    """

    @classmethod
    def _path(cls, root: str, keys: tuple[str, ...]) -> Path:
        return Path(root) / SIDECAR_DIR / Path(*keys[:-1]) / f"{keys[-1]}.json"

    @classmethod
    def Write(cls, root: str, keys: tuple[str, ...], payload: dict) -> None:
        """구조 JSON 을 ``keys`` 경로 사이드카로 쓴다 (부모 dir 보장)."""
        _p = cls._path(root, keys)
        _p.parent.mkdir(parents=True, exist_ok=True)
        Write_to(_p, payload)

    @classmethod
    def Read(cls, root: str, keys: tuple[str, ...]) -> dict | None:
        """``keys`` 사이드카를 읽어 dict 반환 (없거나 깨졌으면 None)."""
        _p = cls._path(root, keys)
        if not _p.exists():
            return None
        _ok, _d = Read_from(_p)
        return _d if _ok and isinstance(_d, dict) else None

    @classmethod
    def Delete(cls, root: str, keys: tuple[str, ...]) -> None:
        """``keys`` 사이드카 파일을 지운다 (없으면 no-op)."""
        cls._path(root, keys).unlink(missing_ok=True)

    @classmethod
    def Walk(cls, root: str):
        """``{root}/.meta`` 아래 모든 ``*.json`` 을 ``(keys, dict)`` 로 낸다 — keys = 경로 key 시퀀스."""
        _base = Path(root) / SIDECAR_DIR
        if not _base.is_dir():
            return
        for _p in sorted(_base.rglob("*.json")):
            _ok, _d = Read_from(_p)
            if _ok and isinstance(_d, dict):
                yield _p.relative_to(_base).with_suffix("").parts, _d
