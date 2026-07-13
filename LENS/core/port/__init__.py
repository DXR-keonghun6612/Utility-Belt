"""port — 외부 세계와 닿는 유일한 지점 (실체화·발견).

데이터 **하나**의 읽기/쓰기(포맷 코덱·경로 파생·구조 사이드카)와, 외부 레이아웃의 **발견**(glob).
아는 것은 **디스크와 포맷뿐** — ``Bucket_Store`` 를 모른다.

의존은 한 방향 — ``schema ← port ← store``. **store 가 port 에 요청하지, port 는 store 를 모른다.**
"어느 범주에 어떻게 넣나"는 store 의 일이라 여기 없다: ``Scan`` 은 *어떤 파일이 있나*만 답하고, 등록은
``store.Import`` 가 한다. 이 방향은 [`../test_layering.py`](../test_layering.py) 가 강제한다.

**``Data_Ref`` 를 재노출하지 않는다.** 소비처는 [`core.schema`](../schema.py) 에서 직접 가져간다 — 편의
재노출이 있던 동안 거의 모든 소비처가 여길 경유해 ``Data_Ref`` 를 당겼고, 그 바람에 데이터모델만 필요한
쪽까지 cv2·numpy 를 끌고 왔다(cv2-free 가 이론으로만 존재했다).

핸들러 모듈을 떨구기만 하면 아래 순회가 ``@HANDLER_REGISTRY.Register_module`` 을 트리거한다 — 새
처리방법 추가에 이 파일을 손댈 필요가 없다. (등록 대상이 아닌 모듈(`scan`)이 섞여 있어도 무해하다 —
데코레이터가 없으면 아무 일도 안 일어난다. 단 그런 모듈은 **port 내부를 import 하면 안 된다** — 이
순회가 도는 중이라 순환이 난다.)
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any

from python_toolbox.registry import Registry

from ..constant import ROUTE_TARGETS, TO_META, TO_STORAGE
from ..schema import Data_Ref
from ._base import File_Handler, Handler
from ._structure import Structure

HANDLER_REGISTRY = Registry[type]("handler", Handler)

# 핸들러 모듈 자동 등록 (``_`` 모듈은 건너뜀).
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


def _handler(ref: Data_Ref) -> type[Handler]:
    """이 ref 를 맡을 핸들러 — **등록된 첫 칸이 아니면 인라인(attr)이다.**

    첫 칸은 handler 이름이거나 **도메인 개념**(``bbox``)이다. 개념은 파일 I/O 가 없어 핸들러를 안 갖고,
    그래서 등록되지도 않는다 — 개념이 갈리는 곳은 표현(gui viewer)이지 저장이 아니다. 여기서 그 전부를
    인라인으로 흘려보내므로, **개념을 더해도 port 는 안 고친다**.
    """
    _key = ref.format[0] if ref.format else ""
    return HANDLER_REGISTRY.Get(_key if _key in HANDLER_REGISTRY._module_dict else "attr", Handler)


def Load(root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
    """payload 로드 (``path`` = leaf 조상 key 시퀀스)."""
    return _handler(ref).Load(root, path, name, ref)


def Save(root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
    """저장. 갱신된 ``Data_Ref`` 반환."""
    return _handler(ref).Save(root, path, name, ref, src)


def Move(src_root: str, src_path: tuple[str, ...],
         dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """파일을 ``src`` 경로 → ``dst`` 경로로 옮긴다 (인라인=no-op)."""
    _handler(ref).Move(src_root, src_path, dst_root, dst_path, name, ref)


def Copy(src_root: str, src_path: tuple[str, ...],
         dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """파일을 ``src`` → ``dst`` 로 복사한다 (src 보존; 인라인=no-op)."""
    _handler(ref).Copy(src_root, src_path, dst_root, dst_path, name, ref)


def Delete(root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """이 ref 의 파일을 지운다 (인라인=no-op)."""
    _handler(ref).Delete(root, path, name, ref)


def Path_of(root: str, path: tuple[str, ...], name: str, ref: Data_Ref):
    """이 ref 를 받치는 파일 경로 (인라인이면 None) — store 밖 레이아웃으로 내보낼 때."""
    return _handler(ref).Path_of(root, path, name, ref)


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
    정해진 핸들러의 ``Default_format`` 으로 조립하고, ``spec`` 의 ``format`` 이 있으면 그게 이긴다.

    **``to`` 는 요청이지 힌트가 아니다** — 그릇(``meta``=인라인 / ``storage``·``trace``=파일)과 확정된
    핸들러의 ``INLINE`` 이 어긋나면 실패한다. ``trace`` 가 여기서 ``storage`` 와 같은 이유는 둘의 차이가
    **호출 측이 넘기는 root** 뿐이기 때문이다 — port 는 그 root 가 정본인지 진단인지 모른다.

    **위치는 spec 이 안 정한다** — 파일 경로는 트리 위치(``path``)와 leaf 이름에서 ``File_Handler._path``
    가 파생한다. 그래서 template 은 ``format`` 만 정하고 ``info`` 는 비운 채 낸다(payload 는 ``Save`` 가 채움).

    Raises:
        ValueError: ``to`` 가 ``ROUTE_TARGETS`` 밖 · type 을 정할 수 없음 · ``to`` ↔ ``INLINE`` 불일치.
    """
    _to = spec.get("to", TO_META)
    if _to not in ROUTE_TARGETS:
        raise ValueError(f"routing: 알 수 없는 to={_to!r} (가능: {', '.join(ROUTE_TARGETS)})")
    _file = _to != TO_META                               # storage·trace = 파일 / meta = 인라인
    _type = (spec.get("type")
             or Infer_type(spec.get("format", ""))
             or _claim_type(value, storage=_file, params=params))
    if _type is None:
        raise ValueError(
            f"routing: value({type(value).__name__})·맥락(to={_to}, params={params})"
            f" 으로 type 을 정할 수 없음 — spec 에 type 을 명시하세요")
    _cls = HANDLER_REGISTRY._module_dict.get(_type)      # 개념(bbox 등)이면 None — 핸들러가 없다
    if (_cls.INLINE if _cls is not None else True) == _file:
        raise ValueError(
            f"routing: to={_to!r}({'파일' if _file else '인라인'}) 인데 type={_type!r} 은 "
            f"{'인라인' if _file else '파일'} 이다 — "
            + (f"to: {TO_STORAGE} 로 바꾸거나 type 을 빼세요" if not _file else
               f"to: {TO_META} 로 바꾸거나 파일 type(image·segmap·array·docs)을 쓰세요"))
    if _cls is None:                                     # 개념(bbox 등) — 파일 핸들러가 아니다
        return Inline(value, _type)
    if _type == "attr":                                  # 등록 이름 = 개념 없음 (그냥 파이썬 값)
        return Inline(value)
    return Data_Ref(format=(_type, spec.get("format") or _cls.Default_format()), info={})


def Template_for_file(spec: dict | str) -> Data_Ref:
    """ingest 스펙(``{pattern, ext, type}``) → ``Data_Ref`` 템플릿.

    ``Template`` 의 자매 — 담을 그릇을 정하는 일은 같지만, ingest 는 파일이 아직 디스크에만 있어
    **볼 값이 없다**(``Template`` 은 값+맥락으로 고를 수 있다).

    **필드는 둘뿐이고 각각 하나의 일만 한다:**

    - ``pattern`` + ``ext`` → **파일을 찾는다**(glob). ``ext`` 는 소스 파일의 확장자.
    - ``type`` → **핸들러** (image/segmap/attr/array/docs …).

    **``type`` 은 필수다 — 확장자로 추론하지 않는다.** `png` 하나가 `image` 일 수도 `segmap`(라벨맵)일
    수도 있어, 추론은 **둘 중 하나를 말없이 고르는 것**이다. (그래서 ``segmap`` 은 ``Extensions`` 를 비워
    충돌을 피해뒀고, 그 대가로 ``Infer_type('png')`` 은 늘 `image` 라고 단정한다.)

    **저장 확장자는 따로 안 받는다** — 서술자의 detail 은 ``Save`` 가 채운다(파일=소스 확장자 그대로,
    인라인=핸들러 기본값). ingest 는 **복사이지 변환이 아니라서** 소스와 다른 확장자를 정할 이유가 없다.

    Raises:
        ValueError: ``type`` 이 없거나 등록되지 않은 handler 일 때.
    """
    if isinstance(spec, str):
        spec = {"pattern": spec}
    _type = spec.get("type")
    if not _type:
        raise ValueError(
            f"glob '{spec['pattern']}': type 을 명시하세요 (가능: {', '.join(Types())}). "
            f"확장자로 추론하지 않습니다 — png 는 image 일 수도 segmap 일 수도 있습니다.")
    if _type not in HANDLER_REGISTRY._module_dict:
        raise ValueError(
            f"glob '{spec['pattern']}': 알 수 없는 type '{_type}' (가능: {', '.join(Types())}).")
    return Data_Ref(format=(_type, ""))                 # detail 은 Save 가 소스에서 채운다


def Route(root: str, path: tuple[str, ...], name: str, spec: dict, value: Any,
          *, params: bool = False) -> Data_Ref:
    """값을 spec 대로 저장한다 — ``Template`` 로 ref 를 짓고 ``Save`` 로 write."""
    return Save(root, path, name, Template(spec, value, params=params), value)


from .attr import Inline, Python_type       # noqa: E402  (자동등록 순회 뒤 — 값→인라인 서술자)
from .scan import Glob_of, Pattern_of, Scan  # noqa: E402  (자동등록 순회 뒤 — scan 은 handler 가 아니다)

__all__ = [
    "Handler", "File_Handler", "Structure", "HANDLER_REGISTRY",
    "Types", "Infer_type", "Load", "Save", "Move", "Copy", "Delete", "Path_of",
    "Template", "Template_for_file", "Route", "Inline", "Python_type",
    "Scan", "Glob_of", "Pattern_of",
]
