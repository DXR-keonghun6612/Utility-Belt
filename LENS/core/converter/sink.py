"""Convert sink — 발견된 raw 그룹을 handler 로 저장하고 stem 컨테이너를 modified 버킷에 등록한다.

``process`` 의 Stage 출력 계약(``Base_Sink``)을 구현한다. 체인이 비므로 per-step ``route`` 는 안 쓰고,
unit 당 1회 ``emit`` 에서 구조를 만든다 — ``target="frame"`` 이면 stem ``Data_Ref`` 를 modified 에,
``target="params"`` 면 root leaf 를 ``store.params`` 에 (둘 다 payload 는 ``handler.Save`` 위임).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..constant import MODIFIED
from ..data import handler
from ..data.handler import Data_Ref
from ..process.sink import Base_Sink
from ..process.source import Unit


@dataclass
class Register_sink(Base_Sink):
    """raw unit → 저장 + 등록. source 가 정한 ref 템플릿(``unit.extra["specs"]``)으로 handler.Save."""

    def emit(self, store, unit: Unit, ctx: dict) -> None:
        _specs = unit.extra["specs"]
        if unit.extra.get("target") == "params":           # dataset-wide root leaf
            for _name, _ref in _specs.items():
                if _name in ctx:
                    store.params[_name] = handler.Save(store.root, None, _name, _ref, ctx[_name])
            return
        _root = store.Category_root(MODIFIED)               # frame: modified 버킷 stem
        _info = {_name: handler.Save(_root, unit.stem, _name, _ref, ctx[_name])
                 for _name, _ref in _specs.items() if _name in ctx}
        store.Bucket(MODIFIED)[unit.stem] = Data_Ref(type="stem", info=_info)
