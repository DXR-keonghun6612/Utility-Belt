"""Sample source — staged 정본을 unit 단위로 순회한다.

``process`` 의 Stage 입력 계약(``Base_Source``/``Frame``/``Unit``)을 구현한다. Run 의 ``Frame_source`` 가
modified 를 순회하듯, ``Staged_source`` 는 staged 를 순회한다. 두 모드:

- **A+ (``materialize=False``, 기본)** — payload 를 resolve 하지 않고 정본 ref(``unit.frame``/``unit.obj``)
  + inline attr 만 sink 로 넘긴다(sink 가 class_id attr 를 구조로 읽음, 순수 역참조).
- **실체화 (``materialize=True``)** — crop 체인이 먹을 payload 를 resolve 한다: 프레임 leaf(base image·
  ``segment``)를 ``handler.Load`` 로 풀고, object unit 마다 ``segment`` 라벨맵(픽셀=obj_id+1)에서 그 obj
  ``mask`` 를 파생해 ctx 로 올린다 → ``Frame_crop(frame, mask)`` 가 crop 을 낸다. ``Sample_stage`` 가
  ``processes`` 가 있으면 이 모드를 켠다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np

from ..constant import STAGED
from ..data.handler import Data_Ref
from ..process.source import Base_Source, Frame, Unit, resolve


def _inline_ctx(ref: Data_Ref) -> dict:
    """ref 의 **인라인 attr leaf** 값만 ctx dict 로 (파일 payload 는 건너뜀 — A+ 경량 유지).

    gate·select process 가 정본에 기록된 attr(``class_id``·``center_dist`` 등)로 거를 수 있게 한다 —
    payload(image/array/rle)는 로드하지 않으므로 파일 I/O 없음(순수 역참조 유지).
    """
    return {_k: _v.info.get("value")
            for _k, _v in ref.info.items()
            if not _v.Is_stem() and _v.type == "attr"}


def _obj_mask(segment: np.ndarray | None, obj_id: str | None) -> np.ndarray | None:
    """``segment`` 인스턴스 라벨맵(픽셀=obj_id+1)에서 한 obj 의 이진 mask 를 뽑는다 (없으면 None).

    정본은 per-obj mask 를 따로 저장하지 않고 frame-level ``segment`` 한 장에서 파생한다(core 규약 —
    ``mask/separate``·``mask/order`` 가 생산). crop 은 이 mask 의 bbox 로 프레임을 자른다.
    """
    if segment is None or obj_id is None:
        return None
    try:
        _lbl = int(obj_id) + 1
    except (TypeError, ValueError):
        return None
    return (segment == _lbl).astype(np.uint8)


@dataclass
class Staged_frame(Frame):
    """staged 프레임 하나 — A+ 면 inline attr+obj_id 만, 실체화면 leaf resolve + obj mask 파생."""

    stem:  str
    frame: Data_Ref
    unit:  str
    materialize: bool = False

    def context(self, store, params_ctx: dict) -> dict:
        if not self.materialize:
            return {}
        _ctx = {"stem": self.stem}                     # 프레임 leaf(base image·segment) 1회 resolve
        _ctx.update(resolve(store.Category_root(STAGED), self.stem, self.frame.info))
        return _ctx

    def units(self, store, fctx: dict) -> Iterator[Unit]:
        _objs = {_k: _v for _k, _v in self.frame.info.items() if _v.Is_stem()}
        _segment = fctx.get("segment") if self.materialize else None
        if self.unit == "object":
            for _oid, _obj in _objs.items():
                _ctx = {**fctx, "obj_id": _oid, **_inline_ctx(_obj)}
                _mask = _obj_mask(_segment, _oid)
                if _mask is not None:
                    _ctx["mask"] = _mask               # Frame_crop 입력 (segment→obj mask)
                yield Unit(stem=self.stem, ctx=_ctx, frame=self.frame, obj_id=_oid, obj=_obj)
        else:                                          # frame 단위: 프레임 자체가 sample
            _ctx = {**fctx, "obj_id": None, **_inline_ctx(self.frame)}
            yield Unit(stem=self.stem, ctx=_ctx, frame=self.frame, obj_id=None, obj=self.frame)


@dataclass
class Staged_source(Base_Source):
    """Sample source — staged 버킷의 프레임/객체를 순회. ``unit`` 분기 + ``materialize`` (crop resolve)."""

    unit: str = "object"
    materialize: bool = False

    def prelude(self, store) -> dict:
        return {}

    def frames(self, store) -> Iterator[Staged_frame]:
        for _stem, _frame in store.Iter_category(STAGED):
            yield Staged_frame(_stem, _frame, self.unit, self.materialize)

    def count(self, store) -> int:
        return len(store.Bucket(STAGED))
