"""dataset 핸들러 패키지 — I/O 디스패치 단일 진실원천.

pipeline 의 ``PROCESS_REGISTRY`` 와 동일한 ``python_toolbox.Registry`` 패턴. 순수 트리 코어
(``data_ref``)는 이 패키지를 import 하지 않는다 (단방향) — 로드/저장 디스패치는 여기가 소유한다.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from python_toolbox.registry import Registry

from ._base import Data_Ref, File_Handler, Handler
from ._structure import Structure

HANDLER_REGISTRY = Registry[type]("handler", Handler)

# 핸들러 모듈 자동 등록 — 패키지 내 ``_`` 없는 모듈을 순회 import 해 각 모듈의
# @HANDLER_REGISTRY.Register_module 데코레이터를 트리거한다. 새 핸들러는 파일만 추가하면
# 되고 여기를 손댈 필요가 없다 (``_base`` 등 밑줄 모듈은 등록 대상이 아니라 건너뜀).
for _mod in pkgutil.iter_modules(__path__):
    if not _mod.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_mod.name}")


def _build_ext_map() -> dict[str, str]:
    """등록된 핸들러의 ``Extensions()`` 를 모아 ``ext → type`` 맵을 만든다.

    같은 확장자를 두 핸들러가 주장하면 추론이 모호해지므로 ``KeyError`` 로 막는다
    (Registry 의 중복 키 정책과 동일).
    """
    _map: dict[str, str] = {}
    for _type, _cls in HANDLER_REGISTRY._module_dict.items():
        for _ext in _cls.Extensions():
            _ext = _ext.lower()
            if _ext in _map and _map[_ext] != _type:
                raise KeyError(
                    f"확장자 '{_ext}' 가 '{_map[_ext]}' / '{_type}' 핸들러에 중복 등록")
            _map[_ext] = _type
    return _map


_EXT_TO_TYPE = _build_ext_map()


def Types() -> list[str]:
    """등록된 type 목록 (GUI 데이터-추가 combobox 등)."""
    return sorted(HANDLER_REGISTRY._module_dict)  # registry 내부 맵


def Infer_type(ext: str) -> str | None:
    """파일 확장자로 핸들러 type 을 추론한다.

    인식하는 핸들러가 없으면 ``None`` — 호출 측이 type 을 명시하게 한다(조용한
    기본값 없음). 인라인 type(attr·rle)은 확장자가 없어 여기서 추론되지 않는다.
    """
    return _EXT_TO_TYPE.get(ext.lstrip(".").lower())


def Load(root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
    """ref.format[0](handler key) 로 payload 로드 (``path`` = leaf 조상 key 시퀀스)."""
    return HANDLER_REGISTRY.Get(ref.format[0], Handler).Load(root, path, name, ref)


def Save(root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
    """ref.format[0](handler key) 로 저장. 갱신된 ``Data_Ref`` 반환."""
    return HANDLER_REGISTRY.Get(ref.format[0], Handler).Save(root, path, name, ref, src)


def Move(src_root: str, src_path: tuple[str, ...],
         dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """파일을 ``src`` 경로 → ``dst`` 경로로 옮긴다 (인라인=no-op)."""
    HANDLER_REGISTRY.Get(ref.format[0], Handler).Move(src_root, src_path, dst_root, dst_path, name, ref)


def Copy(src_root: str, src_path: tuple[str, ...],
         dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """파일을 ``src`` → ``dst`` 로 복사한다 (src 보존; 인라인=no-op)."""
    HANDLER_REGISTRY.Get(ref.format[0], Handler).Copy(src_root, src_path, dst_root, dst_path, name, ref)


def Delete(root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """이 ref 의 파일을 지운다 (인라인=no-op)."""
    HANDLER_REGISTRY.Get(ref.format[0], Handler).Delete(root, path, name, ref)


def Path_of(root: str, path: tuple[str, ...], name: str, ref: Data_Ref):
    """이 ref 를 받치는 파일 경로 (인라인이면 None) — store 밖 레이아웃으로 내보낼 때."""
    return HANDLER_REGISTRY.Get(ref.format[0], Handler).Path_of(root, path, name, ref)


def _claim_type(value: Any, *, storage: bool, params: bool) -> str | None:
    """spec 이 type/format 을 안 줄 때, value+맥락을 담당하는 핸들러 type (최고 ``Claims``; 없으면 None).

    각 핸들러가 선언한 ``Claims`` 를 registry 전체에서 모아 우선순위로 고른다 — value→type 추론을
    중앙 테이블이 아니라 핸들러들의 선언으로 병합해 결정한다(새 type=파일 하나로 확장).
    """
    _best, _type = 0, None
    for _t, _cls in HANDLER_REGISTRY._module_dict.items():
        _p = _cls.Claims(value, storage=storage, params=params)
        if _p > _best:
            _best, _type = _p, _t
    return _type


def Template(spec: dict, value: Any, *, params: bool = False) -> Data_Ref:
    """routing spec(+값·맥락) → ``Data_Ref`` 템플릿 — 값을 어떤 서술자로 담을지 한곳에서 정한다.

    handler 확정 순서: ``spec.type`` → ``spec.format`` 확장자 추론 → value+맥락 ``Claims``(핸들러 선언).
    정해진 핸들러의 ``INLINE``(인라인 vs 파일)·``Default_format`` 으로 조립하고, ``spec`` 의 ``format``
    이 있으면 그게 이긴다.

    **위치는 spec 이 안 정한다** — 파일 경로는 트리 위치(``path``)와 leaf 이름에서 ``File_Handler._path``
    가 파생한다. 그래서 template 은 ``format`` 만 정하고 ``info`` 는 비운 채 낸다(payload 는 ``Save`` 가 채움).
    """
    _storage = spec.get("to", "meta") == "storage"
    _type = (spec.get("type")
             or Infer_type(spec.get("format", ""))
             or _claim_type(value, storage=_storage, params=params))
    if _type is None:
        raise ValueError(
            f"routing: value({type(value).__name__})·맥락(storage={_storage}, params={params})"
            f" 으로 type 을 정할 수 없음 — spec 에 type 을 명시하세요")
    _cls = HANDLER_REGISTRY.Get(_type, Handler)
    return Data_Ref(format=(_type, spec.get("format") or _cls.Default_format()), info={})


def Route(root: str, path: tuple[str, ...], name: str, spec: dict, value: Any,
          *, params: bool = False) -> Data_Ref:
    """값을 spec 대로 저장한다 — ``Template`` 로 ref 를 짓고 ``Save`` 로 write."""
    return Save(root, path, name, Template(spec, value, params=params), value)


__all__ = [
    "Data_Ref",
    "Handler", "File_Handler", "Structure", "HANDLER_REGISTRY",
    "Types", "Infer_type", "Load", "Save", "Move", "Copy", "Delete", "Path_of",
    "Template", "Route",
]
