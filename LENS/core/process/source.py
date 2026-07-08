"""Stage source 계약 + Run source — **무엇을 순회하며 무엇을 ctx 로 resolve 하나**.

``Stage`` 엔진(``_base.py``)의 입력 축. source 는 처리 단위(``Unit``)를 내주고, 각 Unit 은 process
체인이 먹을 **resolve 된 ctx**(handler.Load 로 푼 payload) + sink 가 쓸 **주소**(stem/obj_id/frame ref)를
든다. 여기엔 **계약**(``Base_Source``·``Stem_Block``·``Unit``·``resolve``)과 Run 구현(``Meta_block`` =
modified 프레임/객체)만 둔다 — Convert 의 ``Raw_block`` 은 [`../converter`](../converter), Sample 의
``Staged_block`` 은 [`../sampler`](../sampler) 가 이 계약을 같은 모양으로 구현한다.

순회 배치는 **하나의 stem**(정본 프레임 / raw 그룹)이라 ``Stem_Block`` 이다. Meta·Staged 는 stem 의
자식 stem(객체)을 unit 으로 분해하는 **골격(``units``)을 공유**하고, unit ctx 채우기(``_unit``)와 frame-
단위 정책(``_frame_unit``)만 다르다. Raw 는 obj 분해가 없어 ``units`` 를 직접 낸다.

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


class Stem_Block(ABC):
    """한 순회 배치 = 한 stem(정본 프레임 / raw 그룹) — 배치 ctx + 그 안의 처리 단위(``Unit``)를 낸다.

    carry 는 배치 경계에서 이월된다. object 단위면 stem 의 자식 stem(=객체)마다 한 unit, frame 단위면
    ``_frame_unit`` — 이 **분해 골격은 여기(``units``)가 소유**하고, 서브클래스는 "unit ctx 를 어떻게
    채우나"(``_unit``)와 frame-단위 정책(``_frame_unit``)만 구현한다. obj 분해가 없는 배치(Raw)는
    ``units`` 를 override 한다.
    """

    # Meta/Staged 가 쓰는 필드 (골격이 참조). Raw 는 units override 라 이 필드가 없어도 된다.
    stem:  str
    frame: Data_Ref
    unit:  str

    @abstractmethod
    def context(self, store, params_ctx: dict) -> dict:
        """배치 단위 ctx (params + 배치 leaf resolve; unit 루프와 무관하게 1회)."""

    def units(self, store, fctx: dict) -> Iterator[Unit]:
        """이 배치의 처리 단위들 — object=자식 obj 마다, frame=``_frame_unit`` (공통 분해 골격)."""
        if self.unit == "object":
            for _oid, _obj in self._objects().items():
                yield self._unit(store, fctx, _oid, _obj)
        else:
            yield from self._frame_unit(store, fctx)

    def _objects(self) -> dict[str, Data_Ref]:
        """이 stem 의 자식 stem(=객체) 들 (leaf 는 제외)."""
        return {_k: _v for _k, _v in self.frame.info.items() if _v.Is_stem()}

    def _unit(self, store, fctx: dict, obj_id: str | None, obj: Data_Ref | None) -> Unit:
        """한 객체(또는 frame-단위의 프레임 자신)를 처리 unit 으로 — 서브클래스가 ctx 채우기 구현."""
        raise NotImplementedError

    def _frame_unit(self, store, fctx: dict) -> Iterator[Unit]:
        """frame-단위 기본 — 프레임 자신을 한 unit 으로(obj=frame). Meta 는 '첫 객체'로 override."""
        yield self._unit(store, fctx, None, self.frame)


class Base_Source(ABC):
    """Stage 입력 축 — prelude(순회 전 1회 ctx) + blocks(순회 배치)."""

    @abstractmethod
    def prelude(self, store) -> dict:
        """순회 전 1회 resolve 하는 공통 ctx (예: params). 없으면 ``{}``."""

    @abstractmethod
    def blocks(self, store) -> Iterator[Stem_Block]:
        """순회할 배치(``Stem_Block``)들을 낸다."""

    def count(self, store) -> int:
        """총 배치 수 (cache-hit 시 진행 표시용). 기본은 blocks 열거."""
        return sum(1 for _ in self.blocks(store))


# ── Run: modified 프레임/객체 ──────────────────────────────────────────────────

@dataclass
class Meta_block(Stem_Block):
    """정본 프레임 하나 — leaf resolve + unit(frame/object) 분기. frame-단위는 '첫 객체 1회'."""

    stem:  str
    frame: Data_Ref
    unit:  str

    def context(self, store, params_ctx: dict) -> dict:
        _ctx: dict = {"meta": store, "stem": self.stem, **params_ctx}
        _ctx.update(resolve(store.Category_root(MODIFIED), self.stem, self.frame.info))
        return _ctx

    def _unit(self, store, fctx: dict, obj_id: str | None, obj: Data_Ref | None) -> Unit:
        _octx = dict(fctx)
        _octx["obj_id"] = obj_id                        # gate·select 가 obj_id 로 거를 수 있게
        if obj is not None:
            _octx.update(resolve(store.Category_root(MODIFIED), self.stem, obj.info, obj_id=obj_id))
        return Unit(stem=self.stem, ctx=_octx, frame=self.frame, obj_id=obj_id, obj=obj)

    def _frame_unit(self, store, fctx: dict) -> Iterator[Unit]:
        _objs = self._objects()
        if _objs:                                       # unit=frame: 첫 객체 1회(obj_id 바인딩)
            _k = next(iter(_objs))
            yield self._unit(store, fctx, _k, _objs[_k])
        else:                                           # 객체 없는 프레임
            yield self._unit(store, fctx, None, None)


@dataclass
class Frame_source(Base_Source):
    """Run source — working(modified) 버킷의 프레임을 순회. ``unit`` 으로 frame/object 분기.

    staged(검수 끝)는 안 건드린다 — 재가공하려면 먼저 modified 로 되돌린다.
    """

    unit: str = "frame"

    def prelude(self, store) -> dict:
        return resolve(store.root, None, store.params)      # params(root leaf) 1회

    def blocks(self, store) -> Iterator[Meta_block]:
        for _stem, _frame in store.Iter_category(MODIFIED):
            yield Meta_block(_stem, _frame, self.unit)

    def count(self, store) -> int:
        return len(store.Bucket(MODIFIED))
