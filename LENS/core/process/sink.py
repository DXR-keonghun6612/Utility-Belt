"""Stage sink — **출력을 어디로 보내나**.

``Stage`` 엔진(``_base.py``)의 출력 축. sink 는 step 이 낸 ctx 값 중 선언된 키를 **저장/배치**한다 — Run 은
``Meta_sink``(frame/object/params 를 handler 로 meta 에 route), Convert 는 ``Register_sink``, Sample 은
``Sample_sink``. route 는 여기(출력) / resolve 는 [`source.py`](source.py)(입력)로 갈린 대칭.

라우팅 규칙·outputs 스키마는 [`README.md`](README.md).
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..constant import MODIFIED
from ..data import handler
from ..data.handler import Data_Ref
from .source import Unit


def _params_ref(spec: dict, val: Any) -> Data_Ref:
    """블록(dataset-wide) 출력 → ``params`` 용 ``Data_Ref`` 템플릿."""
    if spec.get("to", "meta") == "storage":
        _fmt = spec.get("format", "npy")
        return Data_Ref(type=spec.get("type") or handler.Infer_type(_fmt) or "array",
                        format=_fmt, info={"dir": spec.get("dir", "params")})
    if isinstance(val, np.ndarray) and val.ndim:           # 배열 → npy
        return Data_Ref(type="array", format="npy", info={"dir": "params"})
    return Data_Ref(type="attr", info={})                  # 스칼라/list/dict 인라인


def _data_ref(spec: dict, val: Any) -> Data_Ref:
    """frame/object 출력 → ``Data_Ref`` 템플릿 (meta 인라인=rle/attr / storage=image/array)."""
    if spec.get("to", "meta") == "storage":
        _fmt = spec.get("format", "png")
        return Data_Ref(type=spec.get("type") or handler.Infer_type(_fmt) or "image",
                        format=_fmt, info={"dir": spec.get("dir", "")})
    if isinstance(val, np.ndarray) and val.ndim >= 2:      # 마스크 → RLE 인라인
        return Data_Ref(type="rle", info={})
    return Data_Ref(type="attr", format=spec.get("format", ""), info={})  # bbox 등


class Base_Sink(ABC):
    """Stage 출력 축 — route(단위 출력 저장) + close(순회 후) + cache/finalize 훅."""

    def route(self, store, unit: Unit, spec_map: dict, out: dict) -> None:
        """step 출력 ``out`` 의 선언 키(``spec_map``)를 ``unit`` 주소에 저장한다 (per-step; 기본 no-op)."""

    def emit(self, store, unit: Unit, ctx: dict) -> None:
        """체인 후 unit 당 1회 — 구조 생성(Convert=stem 등록 / Sample=트리 배치). 기본 no-op.

        Run(``Meta_sink``)은 per-step ``route`` 로 다 끝나 여기선 no-op. 체인이 비는 stage(Convert/
        Sample)가 source ctx 를 받아 자기 구조를 만드는 자리.
        """

    def close(self, store) -> None:
        """순회 종료 후 1회 (집계 export 등). 기본 no-op."""

    def cached(self, store, param_keys: list[str]) -> bool:
        """재실행 캐시 적중 여부 (기본 False — sink 가 판정)."""
        return False

    def params_unit(self) -> Unit:
        """finalize(순회 후 1회) 체인 출력이 향할 단위 (위치 없음 → params)."""
        return Unit(stem="", ctx={})

    def finalize_ctx(self, store) -> dict:
        """finalize 체인 시작 ctx (carry 와 병합됨). 기본 ``{}``."""
        return {}


# ── Run: meta 로 route (frame/object/params) ──────────────────────────────────

@dataclass
class Meta_sink(Base_Sink):
    """Run sink — step 출력을 handler 로 ``Dataset_Meta`` 에 저장.

    ``to`` 는 보관 방식(meta 인라인 / storage 파일), ``level`` 은 위치(frame/object)를 가른다. 저장은 전부
    ``handler.Save`` 가 하고, sink 는 ``Data_Ref`` 템플릿(타입·dir·format)과 ``obj_id`` 만 구성한다. 미선언
    키는 ctx 로만 흐른다. ``object`` 리스트만은 구조 교체(frame ``info`` 의 컨테이너 entry; leaf 보존).
    frame/obj 가 없는 단위(finalize)는 위치가 없어 params(root leaf, dataset-wide)로 나간다.
    """

    def route(self, store, unit: Unit, spec_map: dict, out: dict) -> None:
        _root = store.Category_root(MODIFIED)         # 프레임/객체 파일은 modified 버킷에
        _frame, _obj, _stem, _obj_id = unit.frame, unit.obj, unit.stem, unit.obj_id
        for _key, _spec in spec_map.items():
            _val = out.get(_key)
            if _val is None:
                continue
            if _frame is None and _obj is None:            # 블록 레벨(finalize 등) — params
                store.params[_key] = handler.Save(
                    store.root, None, _key, _params_ref(_spec, _val), _val)
                continue
            _is_obj = _spec.get("level", "object") == "object"
            if _is_obj and _obj is None:                   # 객체 위치 없음
                continue
            _target = _obj.info if _is_obj else _frame.info
            _oid    = _obj_id if _is_obj else None
            _target[_key] = handler.Save(
                _root, _stem, _key, _data_ref(_spec, _val), _val, obj_id=_oid)

        _objs = out.get("object")
        if isinstance(_objs, list) and _frame is not None:  # 구조 교체 — 순번=obj_id; leaf 보존
            _leaves = {_k: _v for _k, _v in _frame.info.items() if not _v.Is_stem()}
            _frame.info = {**_leaves, **{str(_i): _n for _i, _n in enumerate(_objs)}}

    def cached(self, store, param_keys: list[str]) -> bool:
        return all(_k in store.params for _k in param_keys)

    def finalize_ctx(self, store) -> dict:
        return {"meta": store}
