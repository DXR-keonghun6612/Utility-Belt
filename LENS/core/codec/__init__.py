"""codec — **포맷 단위** payload I/O. 도메인을 모른다.

I/O 의 실제 범위는 도메인보다 훨씬 작다 — png 를 읽는 법은 사진이든 마스크든 라벨맵이든 같다. 그래서
읽기/쓰기는 여기(포맷)가 소유하고, *"그 포맷이 이 도메인에 유효한가"* 와 의미 보정만 도메인이 든다
([`../domain`](../domain)). codec 은 도메인을 넘어 재사용된다 — ``raster`` 하나를 image·mask·segmap 이
함께 쓴다.

``format[1]`` (= ``Formats()`` 의 이름)로 고른다. 파일 codec 은 그게 곧 확장자(``png``·``npy``·``yaml``),
인라인 codec 은 표현 이름(``rle``·``polygon``) 또는 파이썬 타입(``str``·``int``…)이다.

**새 처리 구조는 파일 하나** — codec 모듈을 떨구면 아래 순회가 등록을 트리거하고, 도메인의 ``FORMATS``
에 그 이름을 한 줄 더하면 붙는다(예: SAM polygon → [`polygon.py`](polygon.py)).
"""

from __future__ import annotations

import importlib
import pkgutil

from python_toolbox.registry import Registry

from ._base import Codec, File_Codec, Inline_Codec

CODEC_REGISTRY = Registry[type]("codec", Codec)

# codec 모듈 자동 등록 (``_`` 모듈은 건너뜀).
for _mod in pkgutil.iter_modules(__path__):
    if not _mod.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_mod.name}")


def Codec_for(fmt: str) -> type[Codec] | None:
    """format 이름(``format[1]``) → codec (없으면 None). 이름은 각 codec 의 ``Formats()`` 가 선언한다."""
    return _FORMAT_TO_CODEC.get(fmt)


def _build_format_map() -> dict[str, type[Codec]]:
    """등록된 codec 의 ``Formats()`` 를 모아 ``format 이름 → codec`` 맵. 중복 선언은 ``KeyError``."""
    _map: dict[str, type[Codec]] = {}
    for _name, _cls in CODEC_REGISTRY._module_dict.items():
        for _f in _cls.Formats():
            if _f in _map and _map[_f] is not _cls:
                raise KeyError(f"format '{_f}' 가 두 codec 에 중복 등록 ({_map[_f].__name__} / {_cls.__name__})")
            _map[_f] = _cls
    return _map


_FORMAT_TO_CODEC = _build_format_map()

__all__ = ["Codec", "File_Codec", "Inline_Codec", "CODEC_REGISTRY", "Codec_for"]
