"""Stage source 계약 + Run source — **무엇을 순회하며 무엇을 ctx 로 resolve 하나**.

``Stage`` 엔진(``_base.py``)의 입력 축. source 는 처리 단위(``Unit``)를 내주고, 각 Unit 은 process
체인이 먹을 **resolve 된 ctx**(handler.Load 로 푼 payload) + sink 가 쓸 **주소**(stem/obj_id/frame ref)를
든다. 여기엔 **계약**(``Base_Source``·``Frame``·``Unit``·``resolve``)과 Run 구현(``Frame_source`` = modified
프레임/객체)만 둔다 — Convert 의 ``Raw_source`` 는 [`../converter`](../converter), Sample 의 ``Staged_source``
는 [`../sampler`](../sampler) 가 이 계약을 같은 모양으로 구현한다.

resolve 는 여기(입력) / route 는 [`sink.py`](sink.py)(출력)로 갈린 대칭. 둘 다 payload I/O 는 ``handler``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator

from ..constant import MODIFIED
from ..data import handler
from ..data.handler import Data_Ref


@dataclass
class Unit:
    """한 처리 단위 — process 체인 입력 ctx + sink 가 출력을 꽂을 주소.

    ``frame``/``obj_id``/``obj`` 는 Run 라우팅 주소(finalize·params 단위는 ``frame=None``). ``extra`` 는
    source→sink 패스스루(Convert 의 raw path·ref 템플릿, Sample 의 배정 정보 등 stage-특화 부수 정보).
    """

    stem:   str
    ctx:    dict[str, Any]
    frame:  Data_Ref | None = None
    obj_id: str | None      = None
    obj:    Data_Ref | None = None
    extra:  dict[str, Any]  = field(default_factory=dict)


def resolve(root: str, stem: str | None, data: dict[str, Data_Ref],
            *, obj_id: str | None = None) -> dict:
    """``data``(이름→``Data_Ref``)를 핸들러로 풀어 ctx dict 로 만든다 (leaf 만; stem 은 건너뜀).

    각 값을 ``handler.Load`` 로 payload(이미지·배열·값·디코드 마스크)로 해제한다. 대상이 없으면(None)
    건너뛴다 — process 는 ``Data_Ref`` 가 아니라 ready-to-use 값만 본다.
    """
    _out: dict = {}
    for _name, _ref in data.items():
        if _ref.Is_stem():
            continue
        _val = handler.Load(root, stem, _name, _ref, obj_id=obj_id)
        if _val is not None:
            _out[_name] = _val
    return _out


class Frame(ABC):
    """한 프레임(순회 배치) — carry 는 프레임 경계에서 이월된다. 프레임 ctx + 그 안의 unit 들을 낸다."""

    stem: str

    @abstractmethod
    def context(self, store, params_ctx: dict) -> dict:
        """프레임 단위 ctx (params + 프레임 leaf resolve; 객체 루프와 무관하게 1회)."""

    @abstractmethod
    def units(self, store, fctx: dict) -> Iterator[Unit]:
        """이 프레임의 처리 단위들을 ``Unit`` 으로 낸다 (frame/object)."""


class Base_Source(ABC):
    """Stage 입력 축 — prelude(순회 전 1회 ctx) + frames(순회 배치)."""

    @abstractmethod
    def prelude(self, store) -> dict:
        """순회 전 1회 resolve 하는 공통 ctx (예: params). 없으면 ``{}``."""

    @abstractmethod
    def frames(self, store) -> Iterator[Frame]:
        """순회할 프레임(배치)들을 낸다."""

    def count(self, store) -> int:
        """총 프레임 수 (cache-hit 시 진행 표시용). 기본은 frames 열거."""
        return sum(1 for _ in self.frames(store))


# ── Run: modified 프레임/객체 ──────────────────────────────────────────────────

@dataclass
class Meta_frame(Frame):
    """정본 프레임 하나 — leaf resolve + unit(frame/object) 분기."""

    stem:  str
    frame: Data_Ref
    unit:  str

    def context(self, store, params_ctx: dict) -> dict:
        _ctx: dict = {"meta": store, "stem": self.stem, **params_ctx}
        _ctx.update(resolve(store.Category_root(MODIFIED), self.stem, self.frame.info))
        return _ctx

    def units(self, store, fctx: dict) -> Iterator[Unit]:
        _objs = {_k: _v for _k, _v in self.frame.info.items() if _v.Is_stem()}
        _root = store.Category_root(MODIFIED)
        if self.unit == "object":
            _items = list(_objs.items())
        elif _objs:                                   # unit=frame: 첫 객체 1회
            _k = next(iter(_objs))
            _items = [(_k, _objs[_k])]
        else:
            _items = [(None, None)]                   # 객체 없는 프레임
        for _oid, _obj in _items:
            _octx = dict(fctx)
            _octx["obj_id"] = _oid                     # gate·select 가 obj_id 로 거를 수 있게
            if _obj is not None:
                _octx.update(resolve(_root, self.stem, _obj.info, obj_id=_oid))
            yield Unit(stem=self.stem, ctx=_octx, frame=self.frame, obj_id=_oid, obj=_obj)


@dataclass
class Frame_source(Base_Source):
    """Run source — working(modified) 버킷의 프레임을 순회. ``unit`` 으로 frame/object 분기.

    staged(검수 끝)는 안 건드린다 — 재가공하려면 먼저 modified 로 되돌린다.
    """

    unit: str = "frame"

    def prelude(self, store) -> dict:
        return resolve(store.root, None, store.params)      # params(root leaf) 1회

    def frames(self, store) -> Iterator[Meta_frame]:
        for _stem, _frame in store.Iter_category(MODIFIED):
            yield Meta_frame(_stem, _frame, self.unit)

    def count(self, store) -> int:
        return len(store.Bucket(MODIFIED))
