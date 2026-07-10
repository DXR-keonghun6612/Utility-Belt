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
    """raw unit → 저장 + 등록. source 가 정한 ref 템플릿(``unit.extra["specs"]``)으로 handler.Save.

    **재-convert 는 이미 있는 stem 을 건드리지 않는다** — 상태(버킷)도 내용도 그대로 둔다. convert 는
    raw 를 들이는 ingest 라 이미 들인 것에 할 일이 없고, 내보내기가 범주 기반이므로 재수집이 검수 이력
    (staged/skipped)을 덮어써서는 안 된다. 그래서 존재 검사가 payload write **앞**에 온다(파일도 안 쓴다).
    """

    def emit(self, store, unit: Unit, ctx: dict) -> None:
        _specs = unit.extra["specs"]
        if unit.extra.get("target") == "params":           # dataset-wide root leaf
            for _name, _ref in _specs.items():
                if _name in ctx:
                    store.Set(_name, handler.Save(store.root, None, _name, _ref, ctx[_name]),
                              is_param=True)
            return
        if store.Has(unit.stem):                            # 이미 들인 stem → 상태·내용 보존
            return
        _root = store.Category_root(store.DEFAULT_CATEGORY)  # frame: 진입 버킷(modified) stem
        _info = {_name: handler.Save(_root, unit.stem, _name, _ref, ctx[_name])
                 for _name, _ref in _specs.items() if _name in ctx}
        store.Set(unit.stem, Data_Ref(type="stem", info=_info))
