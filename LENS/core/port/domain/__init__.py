"""domain — **무엇을 담는 데이터인가**. 유효 포맷 검증 + 정준형 + 정책 (I/O 는 안 한다).

읽기/쓰기는 [`../codec`](../codec)(포맷 단위)이 든다 — 도메인은 *"그 포맷이 이 도메인에 유효한가"* 를
보고, 실어 온 값을 자기 **정준형**으로 맞춘다. 이 분리 덕에 codec 이 도메인을 넘어 재사용된다(``raster``
하나를 image·mask·segmap 이 공유) 하고, 새 도메인은 **파일 하나**로 붙는다(쓰는 포맷 codec 이 이미 있으면
I/O 는 공짜다 — 3D points 가 npy 를 재사용하듯).

``format = (domain, format)`` — 첫 칸이 여기, 둘째 칸이 codec. 도메인 모듈을 떨구면 아래 순회가 등록을
트리거한다(``_`` 모듈은 건너뜀).
"""

from __future__ import annotations

import importlib
import pkgutil

from python_toolbox.registry import Registry

from ._base import Domain

DOMAIN_REGISTRY = Registry[type]("domain", Domain)

# 도메인 모듈 자동 등록 (``_`` 모듈은 건너뜀).
for _mod in pkgutil.iter_modules(__path__):
    if not _mod.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_mod.name}")

ATTR = "attr"     # fallback 도메인 — 등록된 도메인이 아닌 첫 칸(개념 `bbox` 등)은 전부 여기로


def Domains() -> list[str]:
    """등록된 도메인 이름 목록 (GUI 데이터-추가 combobox 등)."""
    return sorted(DOMAIN_REGISTRY._module_dict)


def Domain_for(name: str) -> type[Domain] | None:
    """도메인 이름 → 도메인 (없으면 None — 개념이면 호출 측이 ``ATTR`` 로 보낸다)."""
    return DOMAIN_REGISTRY._module_dict.get(name)


def Infer_domain(ext: str) -> str | None:
    """파일 확장자 → 도메인 (추론 가능한 도메인만; 없으면 None → 호출 측이 ``type`` 명시를 요구).

    같은 확장자를 여러 도메인이 쓰면(png = 사진·마스크·라벨맵) 추론은 곧 **조용히 하나를 고르는 일**이라,
    애매한 도메인은 ``INFERABLE=False`` 로 빠져 있다(png → image 로만 추론된다).
    """
    _e = ext.lstrip(".").lower()
    for _name, _cls in sorted(DOMAIN_REGISTRY._module_dict.items()):
        if _cls.INFERABLE and _e in _cls.FORMATS:
            return _name
    return None


__all__ = ["Domain", "DOMAIN_REGISTRY", "Domains", "Domain_for", "Infer_domain", "ATTR"]
