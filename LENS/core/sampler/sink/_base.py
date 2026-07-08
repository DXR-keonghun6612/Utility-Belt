"""Sample sink 베이스 — staged unit 을 ``Sample_Set`` 트리에 배치한다 (task = sink).

``process`` 의 Stage 출력 계약(``Base_Sink``)을 구현한다. 체인이 비므로 unit 당 1회 ``emit`` 에서
split 을 결정적 배정하고 ``Place``(task별 트리 모양)로 꽂는다. ``close`` 는 ``Finalize``(집계 export)로.
sample 은 A+(순수 재생성) — leaf 는 payload 실체화가 아니라 정본 ``(source_stem, source_obj)`` **역참조**
+ ``class_id`` attr 만 든다. split 배정은 **frame stem 해시**로 결정적(재실행 안정, leakage 방지).

Run 의 ``Meta_sink`` 가 자기 store(meta)에 route 하듯, sample sink 는 자기 ``target``(``Sample_Set``)에
쓴다 — Stage 가 넘기는 ``store``(=source 의 staged meta)와 별개다(source-store ≠ sink-store).
"""

from __future__ import annotations

import hashlib
from abc import abstractmethod
from dataclasses import dataclass, field

from ...data import handler
from ...data.handler import Data_Ref
from ...data.sample import SPLITS, Sample_Set
from ...data.schema import Set_attr
from ...process.sink import Base_Sink
from ...process.source import Unit

DEFAULT_RATIOS: dict[str, float] = {"train": 0.8, "val": 0.1, "test": 0.1}


@dataclass
class Sample_sink(Base_Sink):
    """staged unit → ``Sample_Set`` 배치 (task별 서브클래스).

    ``target`` 은 채울 store, ``ratios`` 는 split 비율(정규화됨), ``salt`` 는 해시 배정 소금(재현성 유지한
    채 다른 분할). ``Place``(트리 배치)만 서브클래스가 구현하고, ``Finalize``(집계 export)는 선택적.
    """

    target: Sample_Set
    ratios: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_RATIOS))
    salt:   str              = ""

    # ── Base_Sink 계약 ─────────────────────────────────────────────────────────
    def emit(self, store, unit: Unit, ctx: dict) -> None:
        self.Place(self._assign(unit.stem), unit, ctx)

    def close(self, store) -> None:
        self.Finalize()

    # ── 공통 (배정·역참조) ─────────────────────────────────────────────────────
    def _assign(self, stem: str) -> str:
        """frame stem → split (해시 기반 결정적 배정; ``ratios`` 누적 구간에 떨군다)."""
        _h = hashlib.md5(f"{self.salt}{stem}".encode()).hexdigest()
        _f = int(_h[:16], 16) / float(1 << 64)              # [0, 1)
        _norm = self._norm_ratios()
        _acc = 0.0
        for _split in SPLITS:
            _acc += _norm.get(_split, 0.0)
            if _f < _acc:
                return _split
        return SPLITS[-1]

    def _norm_ratios(self) -> dict[str, float]:
        """``ratios`` 를 합=1 로 정규화 (합이 0이면 균등)."""
        _total = sum(self.ratios.get(_s, 0.0) for _s in SPLITS)
        if _total <= 0:
            return {_s: 1.0 / len(SPLITS) for _s in SPLITS}
        return {_s: self.ratios.get(_s, 0.0) / _total for _s in SPLITS}

    @staticmethod
    def _sample_ref(stem: str, obj_id: str | None, class_id: str) -> Data_Ref:
        """sample leaf(=컨테이너 stem) — 정본 ``(stem, obj_id)`` 역참조 + class 이름 attr.

        payload 실체화(crop)는 안 한다(A+ 역참조) — 소비 측이 ``source_stem``/``source_obj`` 로 정본
        payload 를 ``handler.Load`` 한다. class 이름은 meta 처럼 ``class_id`` attr 로 든다.
        """
        _ref = Data_Ref(type="stem", info={})
        Set_attr(_ref, "source_stem", stem)
        if obj_id is not None:
            Set_attr(_ref, "source_obj", obj_id)
        if class_id:
            Set_attr(_ref, "class_id", class_id)
        return _ref

    def _set_param(self, name: str, value) -> None:
        """target params(범주 무관 root leaf)에 값을 저장한다 (id_map 등; handler.Route 경유).

        dataset-wide(``params=True``) meta 출력이라 스칼라·dict 는 attr 인라인으로 담긴다.
        """
        self.target.Set(name, handler.Route(
            self.target.root, None, name, {"to": "meta"}, value, params=True), is_param=True)

    def _attach_crop(self, ref: Data_Ref, ctx: dict, split: str, dir_: str, sample_id: str) -> None:
        """``ctx["crop"]`` 가 있으면 payload 로 저장하고 ``ref.info["crop"]`` 에 leaf 를 단다 (없으면 no-op).

        경로는 ``{split}/{dir_}/{sample_id}.png`` (handler 가 파생) — classification 은 ``dir_=class``,
        detection 은 ``dir_=image``. crop 은 파생 산출(정본으로 write-back 안 함)이라 여기 sink 가 떨군다.
        """
        _crop = ctx.get("crop")
        if _crop is None:
            return
        ref.info["crop"] = handler.Route(
            self.target.Category_root(split), sample_id, "crop",
            {"to": "storage", "dir": dir_}, _crop)

    # ── task 훅 ────────────────────────────────────────────────────────────────
    @abstractmethod
    def Place(self, split: str, unit: Unit, ctx: dict) -> None:
        """한 unit 을 ``target`` 트리에 꽂는다 — task 별 layout(class 폴더 / image→object).

        ``ctx`` 는 체인 최종 컨텍스트 — crop 실체화 시 ``ctx["crop"]`` (없으면 A+ 역참조만). payload 저장은
        ``_attach_crop`` 헬퍼로.
        """

    def Finalize(self) -> None:
        """순회 후 1회 — 집계 export(id_map·COCO manifest 등). 기본 no-op."""
