"""핸들러 추상 베이스 + 디스크 파일 공통 베이스.

각 처리방법 핸들러(``image``/``array``/``attr``/``rle`` …)는 ``Handler`` 를 상속하고
``@HANDLER_REGISTRY.Register_module("key")`` 로 등록한다 (registry 는 패키지 ``__init__``).
등록 이름이 ``Data_Ref.format[0]`` 와 매칭되어 Load/Save 디스패치의 키가 된다.

핸들러는 **상태가 없다**(설정은 ``Data_Ref.info`` 에 있음). 그래서 메서드를 ``classmethod``
로 두고 registry 가 저장한 클래스에서 바로 호출한다(인스턴스화 없음). ``cls`` 로 호출하므로
``File_Handler`` 의 공통 로직이 구체 서브클래스의 ``_Read``/``_Write`` 로 정상 디스패치된다.

경로 파생에 필요한 건 ``root`` + ``path``(store 가 넘기는 key 시퀀스)뿐이다 (attr/rle 는 파일이 없어
둘 다 안 쓴다). 서술자 ``Data_Ref`` 는 [`../data_ref.py`](../data_ref.py) 소유 — 데이터모델이 I/O 계층을
모르도록 단방향(handler → data_ref). 여기서는 편의로 재노출한다.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from ..data_ref import Data_Ref

__all__ = ["Data_Ref", "Handler", "File_Handler"]


class Handler(ABC):
    """데이터 처리방법 한 가지의 읽기/쓰기를 담당하는 핸들러 (상태 없음).

    경로 파생·인코딩·인라인 규칙을 전부 핸들러가 소유한다. 외부(converter·pipeline·GUI)는
    handler key(=등록 이름 = ``format[0]``)만 알면 된다.

    **기본 구성 선언** — 쓰기 경로(``handler.Template``)가 값을 어떤 서술자로 담을지 정할 때
    참조하는 type 별 규약을 핸들러가 소유한다(중앙 테이블 대신 각 핸들러가 자기 규칙을 든다 →
    새 type=파일 하나로 확장). ``INLINE``(값을 info 인라인 vs 파일)·``Default_format``(ext 짝)·
    ``Claims``(spec 이 type 을 안 줄 때 value+맥락으로 자기가 담당하는지)가 그것.
    """

    # 값을 ``Data_Ref.info`` 에 인라인 보관(attr/rle)하면 True, 디스크 파일(image/array/segmap)이면 False.
    INLINE: ClassVar[bool] = False

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """spec 이 ``type``/``format`` 을 안 줄 때, 이 value+맥락을 담당하는 우선순위 (0=미매칭).

        ``handler.Template`` 의 value→type 추론을 각 핸들러로 이전한 자리. registry 를 순회해 최고
        우선순위 핸들러가 선택된다. ``storage`` = spec.to=="storage"(파일 요청), ``params`` = 위치
        없는 dataset-wide(finalize) 출력. 같은 ndarray 라도 맥락으로 rle/array/image 를 가른다.
        """
        return 0

    @classmethod
    @abstractmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        """dataset → payload. 대상이 없으면 ``None``. ``path`` = 이 leaf 조상 key 시퀀스."""

    @classmethod
    @abstractmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        """src → dataset. 갱신된 ``Data_Ref`` 반환. ``src`` = raw ``Path`` 또는 in-memory payload."""

    @classmethod
    def Move(cls, src_root: str, src_path: tuple[str, ...],
             dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        """파일을 ``src`` 경로 → ``dst`` 경로로 옮긴다 (인라인 핸들러는 **no-op**)."""
        return None

    @classmethod
    def Copy(cls, src_root: str, src_path: tuple[str, ...],
             dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        """파일을 ``src`` → ``dst`` 로 복사한다 (src 보존; 인라인 핸들러는 **no-op**)."""
        return None

    @classmethod
    def Delete(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        """이 leaf 파일을 지운다 (인라인은 **no-op**)."""
        return None

    @classmethod
    def Default_format(cls) -> str:
        """포맷 미지정 시 기본 format."""
        return ""

    @classmethod
    def Extensions(cls) -> tuple[str, ...]:
        """이 핸들러가 인식하는 파일 확장자 (ext→type 추론용).

        인라인 핸들러(attr·rle)는 파일 확장자가 없어 빈 튜플. ``handler.__init__`` 이
        등록된 핸들러를 순회해 ``ext → type`` 맵을 만들고, converter 가 type 추론에 쓴다.
        """
        return ()

    @classmethod
    def Can_visualize(cls) -> bool:
        """이미지로 시각화 가능한지 (GUI 데이터 트리·오버레이용)."""
        return False


class File_Handler(Handler):
    """디스크 파일 기반 핸들러 공통 베이스 (등록하지 않는 추상 베이스).

    경로 파생(``{root}/<*path>/{name}.{ext}`` — ``path`` = store 가 넘기는 key 시퀀스) 과
    복사(raw Path → 그대로 copy) 를 소유한다. 서브클래스는 인식 확장자 ``Extensions`` 와
    in-memory io 인 ``_Read``/``_Write`` 만 구현한다.
    """

    @classmethod
    def Default_format(cls) -> str:
        """기본 format = 인식 확장자의 첫 항목 (``Extensions()[0]``).

        서브클래스는 ``Extensions`` 만 선언하면 기본 format 까지 따라온다.
        """
        return cls.Extensions()[0]

    @classmethod
    def _path(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Path:
        """파일 경로 = ``{root}/{*path}/{name}.{ext}`` — 재귀 key 뭉치기 (format = (handler, ext))."""
        return Path(root, *path, f"{name}.{ref.format[1]}")

    @classmethod
    def Move(cls, src_root: str, src_path: tuple[str, ...],
             dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        """파일을 ``src`` → ``dst`` 경로로 ``shutil.move`` (없으면 no-op)."""
        _src = cls._path(src_root, src_path, name, ref)
        if not _src.exists():
            return
        _dst = cls._path(dst_root, dst_path, name, ref)
        _dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(_src), str(_dst))

    @classmethod
    def Copy(cls, src_root: str, src_path: tuple[str, ...],
             dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        """파일을 ``src`` → ``dst`` 경로로 ``shutil.copy2`` (없으면 no-op)."""
        _src = cls._path(src_root, src_path, name, ref)
        if not _src.exists():
            return
        _dst = cls._path(dst_root, dst_path, name, ref)
        _dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(_src), str(_dst))

    @classmethod
    def Delete(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
        """이 leaf 파일을 지운다 (없으면 no-op)."""
        cls._path(root, path, name, ref).unlink(missing_ok=True)

    @classmethod
    def Load(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
        _p = cls._path(root, path, name, ref)
        return cls._Read(_p) if _p.exists() else None

    @classmethod
    def Save(cls, root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
        _from_file = isinstance(src, (str, Path))
        _handler = ref.format[0]                        # format = (handler, ext) — handler key 보존
        _ext = (ref.format[1] if len(ref.format) > 1 and ref.format[1] else
                (Path(src).suffix.lstrip(".").lower() if _from_file
                 else cls.Default_format()))
        _out = Data_Ref(format=(_handler, _ext), info=dict(ref.info))
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
        """경로에서 payload 를 읽는다."""

    @classmethod
    @abstractmethod
    def _Write(cls, data: Any, path: Path) -> None:
        """payload 를 경로에 쓴다."""
