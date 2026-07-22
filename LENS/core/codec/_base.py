"""codec 계약 — **포맷 하나**의 읽기/쓰기. 도메인을 모른다.

I/O 의 실제 범위는 도메인보다 훨씬 작다 — png 를 읽는 법은 그게 사진이든 마스크든 같다.
그래서 **I/O 는 포맷 단위**로 소유하고(이 계층), 도메인은 *"그 포맷이 이 도메인에 유효한가"* 만 본다
([`../domain`](../domain)). 그 덕에 codec 은 도메인을 넘어 재사용된다 — ``raster`` 하나를 image·mask 가
함께 쓴다(중복 없음).

두 갈래뿐이다:

- ``File_Codec``  — 값이 디스크 파일. 경로 파생·복사/이동/삭제 공통(``_path``)을 여기가 든다.
- ``Inline_Codec`` — 값이 ``Data_Ref.info["value"]`` 에 산다. 파일 연산이 **no-op** 이다.

codec 은 **상태가 없다**(설정은 ``Data_Ref.info``) — 그래서 classmethod 로, registry 가 든 클래스에서
인스턴스화 없이 부른다.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from ..schema import Data_Ref

__all__ = ["Codec", "File_Codec", "Inline_Codec"]


class Codec(ABC):
    """포맷 하나의 payload I/O (상태 없음). 도메인은 모른다 — 정준형 값을 그대로 싣고 내린다."""

    #: 값이 사이드카 인라인(True)이냐 디스크 파일(False)이냐 — 그릇(``to``)과 맞는지 port 가 검사한다.
    INLINE: ClassVar[bool] = False

    @classmethod
    @abstractmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        """dataset → payload(정준형). 대상이 없으면 ``None``."""

    @classmethod
    @abstractmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        """src → dataset. 갱신된 ``Data_Ref`` 반환. ``src`` = raw ``Path`` 또는 in-memory payload."""

    # ── 파일 연산 — 인라인 codec 은 no-op (값이 사이드카 안이라 옮길 파일이 없다) ────
    @classmethod
    def Move(cls, src_root: str, src_path: tuple[str, ...],
             dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        return None

    @classmethod
    def Copy(cls, src_root: str, src_path: tuple[str, ...],
             dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        return None

    @classmethod
    def Delete(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        return None

    @classmethod
    def Path_of(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Path | None:
        """이 leaf 를 받치는 **파일 경로** (인라인이면 ``None``; 없는 파일이어도 경로는 준다)."""
        return None

    @classmethod
    @abstractmethod
    def Formats(cls) -> tuple[str, ...]:
        """이 codec 이 맡는 **format 이름**들 = ``format[1]`` 로 오는 값 (registry key).

        파일 codec 은 곧 확장자(``png``·``jpg``·``npy``·``yaml``), 인라인 codec 은 표현 이름(``rle``·
        ``polygon``) 또는 파이썬 타입(``str``·``int``)이다. 첫 항목이 그 codec 의 기본 format.
        """


class Inline_Codec(Codec):
    """값이 ``Data_Ref.info["value"]`` 에 사는 codec (rle·polygon·attr) — 파일 연산 전부 no-op."""

    INLINE: ClassVar[bool] = True


class File_Codec(Codec):
    """디스크 파일 codec 공통 베이스 — 경로 파생 + 복사/이동/삭제. 서브클래스는 ``_Read``/``_Write`` 만.

    경로 규칙(kind-major)은 [`../port/README.md`](../port/README.md) 소유 — ``_path`` 가 그 단일 구현이다.
    """

    @classmethod
    def _path(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Path:
        """파일 경로 = ``{root}/{범주}/{종류}/{stem}[_{나머지 key…}].{ext}`` (**kind-major**).

        ``path`` = store 가 넘기는 트리 key 시퀀스 ``(범주, stem, *안쪽 key)``, ``name`` = leaf 이름
        (= 종류), ``ext`` = ``format[1]``. 범주와 stem 만 성분으로 남기고 안쪽 key(객체 id 등)는 stem 에
        ``_`` 로 병합한다. params 는 stem 이 없어 ``{root}/params/{name}.{ext}``.
        """
        _ext = ref.format[1]
        _cat, *_rest = path
        if not _rest:                                   # params — stem 이 없다
            return Path(root, _cat, f"{name}.{_ext}")
        return Path(root, _cat, name, f"{'_'.join(_rest)}.{_ext}")

    @classmethod
    def Move(cls, src_root: str, src_path: tuple[str, ...],
             dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        _src = cls._path(src_root, src_path, name, ref)
        if not _src.exists():
            return
        _dst = cls._path(dst_root, dst_path, name, ref)
        _dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(_src), str(_dst))

    @classmethod
    def Copy(cls, src_root: str, src_path: tuple[str, ...],
             dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        _src = cls._path(src_root, src_path, name, ref)
        if not _src.exists():
            return
        _dst = cls._path(dst_root, dst_path, name, ref)
        _dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(_src), str(_dst))

    @classmethod
    def Delete(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        cls._path(root, path, name, ref).unlink(missing_ok=True)

    @classmethod
    def Path_of(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Path | None:
        return cls._path(root, path, name, ref)

    @classmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        _p = cls._path(root, path, name, ref)
        return cls._Read(_p) if _p.exists() else None

    @classmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        """파일로 쓴다 — raw ``Path`` 면 그대로 복사, in-memory 면 ``_Write``.

        ``format`` 의 detail(확장자)이 비어 있으면 채운다: 소스가 파일이면 그 확장자, 아니면 이 codec 의
        첫 확장자. 서술자가 실제 파일과 다른 확장자를 말하지 못하게 하는 자리다.
        """
        _from_file = isinstance(src, (str, Path))
        _domain = ref.format[0]
        _ext = (ref.format[1] if len(ref.format) > 1 and ref.format[1] else
                (Path(src).suffix.lstrip(".").lower() if _from_file else cls.Formats()[0]))
        _out = Data_Ref(format=(_domain, _ext), info=dict(ref.info))
        _p = cls._path(root, path, name, _out)
        _p.parent.mkdir(parents=True, exist_ok=True)
        if _from_file:
            shutil.copy2(src, _p)
        else:
            cls._Write(src, _p)
        return _out

    @classmethod
    @abstractmethod
    def _Read(cls, path: Path) -> Any:
        """경로에서 payload 를 읽는다 (정준형으로)."""

    @classmethod
    @abstractmethod
    def _Write(cls, data: Any, path: Path) -> None:
        """payload 를 경로에 쓴다."""
