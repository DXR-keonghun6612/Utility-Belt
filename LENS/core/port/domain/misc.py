"""나머지 도메인 — ``array`` (수치 배열) · ``docs`` (중첩 구조) · ``attr`` (개념 없는 인라인 값).

포맷이 하나뿐이라 얇다. **``attr`` 은 fallback 도메인**이다 — 등록된 도메인이 아닌 첫 칸은 전부 여기로
온다(빈 칸이든 ``bbox`` 든). 개념(``bbox``)은 파일 I/O 가 없어 도메인을 안 갖고, 갈리는 곳은 **표현**
(gui viewer)이라 port 는 그 전부를 파이썬 값으로 싣는다 — 그래서 **개념을 더해도 port 를 안 고친다**.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from . import DOMAIN_REGISTRY
from ._base import Domain


@DOMAIN_REGISTRY.Register_module("array")
class Array_Domain(Domain):
    """수치 배열 — npy 파일. 차원을 안 따진다(3D 확장도 여기 또는 전용 도메인으로)."""

    FORMATS:   ClassVar[tuple[str, ...]] = ("npy",)
    INFERABLE: ClassVar[bool]            = True

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """dataset-wide(params) 배열 — 통계 등 ndarray 를 npy 로(위치 없는 출력의 배열)."""
        return 3 if (params and isinstance(value, np.ndarray) and value.ndim) else 0


@DOMAIN_REGISTRY.Register_module("arrays")
class Arrays_Domain(Domain):
    """**이름 붙은 배열 묶음** — npz 파일. 함께 갈리고 함께 쓰이는 배열들이 한 파일이어야 할 때.

    배열 하나는 ``array``(npy)가 든다. 여기는 ``{이름: 배열}`` 이라 되읽을 때 key 가 보존된다 —
    쪼개면 파일이 이름 수만큼 늘고, 합치면 한 번에 실려 온다.
    """

    FORMATS:   ClassVar[tuple[str, ...]] = ("npz",)
    INFERABLE: ClassVar[bool]            = True

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """배열 값을 가진 dict — ``docs``(중첩 구조)보다 세게 집는다(그쪽은 JSON 이라 배열이 안 실린다)."""
        return 4 if (isinstance(value, dict) and value
                     and all(isinstance(_v, np.ndarray) for _v in value.values())) else 0


@DOMAIN_REGISTRY.Register_module("docs")
class Docs_Domain(Domain):
    """중첩 구조(dict/list) — yaml/json 파일. ``id_map`` 등."""

    FORMATS:   ClassVar[tuple[str, ...]] = ("yaml", "yml", "json")
    INFERABLE: ClassVar[bool]            = True

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """파일 요청의 **중첩 구조(dict/list)** 담당 — 스칼라 인라인(attr)과 구분."""
        return 3 if (storage and isinstance(value, (dict, list))) else 0


@DOMAIN_REGISTRY.Register_module("attr")
class Attr_Domain(Domain):
    """개념 없는 인라인 파이썬 값 — format 이 곧 타입(``str``·``int``·``float``·``list``).

    등록 도메인이 아닌 첫 칸(``bbox`` 등 개념)도 전부 이 도메인으로 처리된다 (port ``_domain`` 이 라우팅).
    """

    FORMATS:   ClassVar[tuple[str, ...]] = ("str", "int", "float", "list")
    INFERABLE: ClassVar[bool]            = False   # 확장자가 없다

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """인라인 요청의 최저 fallback — 파일이 아닌 파이썬 값(스칼라·list) 담당."""
        from ...codec.inline import Python_type
        return 1 if not storage and Python_type(value) is not None else 0
