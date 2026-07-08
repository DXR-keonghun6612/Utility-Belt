"""핸들러 추상 베이스 + 디스크 파일 공통 베이스.

각 처리방법 핸들러(``image``/``array``/``attr``/``rle`` …)는 ``Handler`` 를 상속하고
``@HANDLER_REGISTRY.Register_module("type")`` 로 등록한다 (registry 는 패키지 ``__init__``).
등록 이름이 ``Data_Ref.type`` 와 매칭되어 Load/Save 디스패치의 키가 된다.

핸들러는 **상태가 없다**(설정은 ``Data_Ref.info`` 에 있음). 그래서 메서드를 ``classmethod``
로 두고 registry 가 저장한 클래스에서 바로 호출한다(인스턴스화 없음). ``cls`` 로 호출하므로
``File_Handler`` 의 공통 로직이 구체 서브클래스의 ``_Read``/``_Write`` 로 정상 디스패치된다.

핸들러가 dataset 에서 실제로 필요한 건 **``root``(경로 파생)뿐**이라 ``meta`` 전체가 아니라
``root: str`` 을 받는다 (attr/rle 는 root 도 쓰지 않는다).
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from python_toolbox.data_schema import Data_Schema


@dataclass
class Data_Ref(Data_Schema):
    """트리의 **유일** 노드 — leaf payload 서술자 겸 재귀 컨테이너. ``type`` 이 둘을 가른다.

    - **leaf** (``type`` = image/array/attr/rle/segmap …): ``info`` = parameter + payload(인라인 값 or 파일 위치).
    - **컨테이너** (``type`` = ``"stem"``): ``info`` = ``dict[str, Data_Ref]`` (자식들; leaf 든 중첩 stem 이든).
      obj_id/이름은 부모 ``info`` 의 **key**, class 라벨은 ``info["class_id"]``(attr) 로 산다.

    handler 가 소비/생산하는 최하위 primitive 라 handler 패키지가 소유한다. 트리 재귀(순회·전이·병합)는
    ``schema.Bucket_Store`` 가 ``type`` 으로 leaf/stem 을 갈라 소유한다. 값 덤프는 ``Extract``, 구조 직렬화는
    ``Serialize`` (``Data_Schema`` 가 중첩 ``Data_Ref`` 를 재귀 직렬화; 역은 ``__post_init__`` 이 재구성).

    Attributes:
        type:   핸들러 키 (leaf) 또는 ``"stem"``(컨테이너). 로드/저장·재귀 동작을 결정.
        format: 그 핸들러 안의 방향/직렬화 (ext·dtype·encoding). 컨테이너는 무의미(``""``).
        info:   leaf = parameter + payload(``value``/``dir``) / 컨테이너 = 자식 ``dict[str, Data_Ref]``.
    """

    type:   str
    format: str            = ""
    info:   dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type == "stem":                        # 컨테이너 → 자식(info 값)을 Data_Ref 로 재구성(재귀)
            self.info = {_k: _v if isinstance(_v, Data_Ref) else Data_Ref(**_v)
                         for _k, _v in self.info.items()}

    def Is_stem(self) -> bool:
        """컨테이너(``type=="stem"``)인지 — ``info`` 로 자식을 재귀로 든 노드."""
        return self.type == "stem"

    def Is_inline(self) -> bool:
        """leaf payload 를 ``info`` 에 인라인 보관(attr/rle/bbox 등)이면 True, 파일 참조면 False.

        내보낼 때 leaf 처리를 가른다(inline → 값 그대로 / file → handler). 판별은 파일 위치(``dir``)
        유무 — 인라인 서술자는 위치 키를 갖지 않는다. (컨테이너엔 호출하지 않음.)
        """
        return "dir" not in self.info


class Handler(ABC):
    """데이터 처리방법 한 가지의 읽기/쓰기를 담당하는 핸들러 (상태 없음).

    경로 파생·인코딩·인라인 규칙을 전부 핸들러가 소유한다. 외부(converter·pipeline·GUI)는
    type(=등록 이름)만 알면 된다.

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
    def Load(
        cls, root: str, stem: str | None, name: str,
        ref: Data_Ref, *, obj_id: str | None = None
    ) -> Any:
        """dataset → payload. 대상이 없으면 ``None``."""

    @classmethod
    @abstractmethod
    def Save(
        cls, root: str, stem: str | None, name: str, ref: Data_Ref, src: Any,
        *, obj_id: str | None = None
    ) -> Data_Ref:
        """src → dataset. 갱신된 ``Data_Ref`` 를 반환한다.

        ``src`` 는 핸들러가 이해하는 입력 — converter 의 raw 파일 ``Path`` 또는
        pipeline 의 in-memory payload(ndarray·값).
        """

    @classmethod
    def Move(
        cls, src_root: str, dst_root: str, stem: str | None, name: str,
        ref: Data_Ref, *, obj_id: str | None = None
    ) -> None:
        """이 ref 의 파일을 ``src_root`` 에서 ``dst_root`` 로 옮긴다 (staging 상태 전이용).

        인라인 핸들러(attr·rle)는 디스크 파일이 없어 **no-op** — 값이 meta 안에 있어 버킷만
        옮기면 된다. 파일 핸들러만 실제 ``shutil`` 이동한다. 경로 파생 단일 진실원천이 핸들러라,
        전이(Pipeline)는 위치 계산 없이 이 메서드만 부른다.
        """
        return None

    @classmethod
    def Copy(
        cls, src_root: str, dst_root: str, stem: str | None, name: str,
        ref: Data_Ref, *, obj_id: str | None = None
    ) -> None:
        """이 ref 의 파일을 ``src_root`` 에서 ``dst_root`` 로 복사한다 (meta 병합용; src 보존).

        ``Move`` 와 같은 디스패치지만 원본을 남긴다 — 외부 meta 를 들일 때 그 데이터셋을 깨지
        않으려 옮기지 않고 복사한다. 인라인 핸들러(attr·rle)는 값이 meta 안이라 **no-op**.
        """
        return None

    @classmethod
    def Delete(
        cls, root: str, stem: str | None, name: str, ref: Data_Ref,
        *, obj_id: str | None = None
    ) -> None:
        """이 ref 의 파일을 지운다 (인라인은 값이 meta/사이드카 안이라 **no-op**)."""
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

    경로 파생(``{root}/{info.dir 또는 name}/{stem or name}[_{obj_id}].{format}``) 과
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
    def _path(cls, root: str, name: str, ref: Data_Ref,
              stem: str | None, obj_id: str | None) -> Path:
        _dir = ref.info.get("dir") or name
        if stem is None:
            _base = name
        elif obj_id is None:
            _base = stem
        else:
            _base = f"{stem}_{obj_id}"
        return Path(root) / _dir / f"{_base}.{ref.format}"

    @classmethod
    def Move(
        cls, src_root: str, dst_root: str, stem: str | None, name: str,
        ref: Data_Ref, *, obj_id: str | None = None
    ) -> None:
        """파생 경로의 파일을 ``src_root`` → ``dst_root`` 로 ``shutil.move`` (없으면 no-op)."""
        _src = cls._path(src_root, name, ref, stem, obj_id)
        if not _src.exists():
            return
        _dst = cls._path(dst_root, name, ref, stem, obj_id)
        _dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(_src), str(_dst))

    @classmethod
    def Copy(
        cls, src_root: str, dst_root: str, stem: str | None, name: str,
        ref: Data_Ref, *, obj_id: str | None = None
    ) -> None:
        """파생 경로의 파일을 ``src_root`` → ``dst_root`` 로 ``shutil.copy2`` (없으면 no-op)."""
        _src = cls._path(src_root, name, ref, stem, obj_id)
        if not _src.exists():
            return
        _dst = cls._path(dst_root, name, ref, stem, obj_id)
        _dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(_src), str(_dst))

    @classmethod
    def Delete(
        cls, root: str, stem: str | None, name: str, ref: Data_Ref,
        *, obj_id: str | None = None
    ) -> None:
        """파생 경로의 파일을 지운다 (없으면 no-op)."""
        cls._path(root, name, ref, stem, obj_id).unlink(missing_ok=True)

    @classmethod
    def Load(cls, root: str, stem: str | None, name: str,
             ref: Data_Ref, *, obj_id: str | None = None) -> Any:
        _path = cls._path(root, name, ref, stem, obj_id)
        return cls._Read(_path) if _path.exists() else None

    @classmethod
    def Save(
        cls, root: str, stem: str | None, name: str, ref: Data_Ref, src: Any,
        *, obj_id: str | None = None
    ) -> Data_Ref:
        _from_file = isinstance(src, (str, Path))
        _fmt = ref.format or (
            Path(src).suffix.lstrip(".").lower() if _from_file
            else cls.Default_format())
        _out = Data_Ref(type=ref.type, format=_fmt, info=dict(ref.info))
        _path = cls._path(root, name, _out, stem, obj_id)
        _path.parent.mkdir(parents=True, exist_ok=True)
        if _from_file:
            shutil.copy2(src, _path)
        else:
            cls._Write(src, _path)
        return _out

    @classmethod
    @abstractmethod
    def _Read(cls, path: Path) -> Any:
        """경로에서 payload 를 읽는다."""

    @classmethod
    @abstractmethod
    def _Write(cls, data: Any, path: Path) -> None:
        """payload 를 경로에 쓴다."""
