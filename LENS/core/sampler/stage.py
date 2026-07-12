"""Sample stage — staged 정본을 순회해 파생 store(``Sample_Set``)에 sample 을 배치한다.

Run 과 **같은 엔진**(``Stage``)이고 바꾸는 건 양 끝뿐이다 — 입력은 ``staged`` 범주(경량 역참조 or crop
실체화), 출력은 자기 ``target``(``Sample_Set``)이다(순회 store ≠ 배치 store). Convert 와 달리 Sample 은
체인을 **실제로 쓴다**(``attr_gate`` 로 솎고 ``frame_crop`` 으로 실체화) — 그래서 엔진에 남는다.

두 모드:

- **A+ (기본)** — payload 를 resolve 하지 않고 정본 역참조 + inline attr 만 든다(순수 재생성).
- **실체화** — ``processes``(crop 체인)가 있으면 프레임 leaf 를 풀고 obj mask 를 파생해 ctx 로 올린다.

**task 는 여기 없다.** 빌드는 무엇을 뽑을지(``unit``)와 어떻게 나눌지(``ratios``/``salt``)만 정한다 —
classification/detection 은 내보내기의 축이다([`export.py`](export.py)).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import ClassVar, Iterator

import numpy as np

from ..constant import STAGED, UNCLASSIFIED
from ..data.handler import Data_Ref
from ..data.sample import SPLITS, Sample_Set
from ..process import Stage
from ..process._base import Unit, inline_ctx, resolve

DEFAULT_RATIOS: dict[str, float] = {"train": 0.8, "val": 0.1, "test": 0.1}
UNLABELED = UNCLASSIFIED   # class_id 가 없는 unit 의 fallback class (정본 미분류 값과 통일)


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
class Sample_stage(Stage):
    """staged 정본 → 파생(``Sample_Set``) 빌드 stage. ``target`` 은 Pipeline 이 주입한다.

    split 은 **빌드가 배정한다** — split 이 곧 store 범주라 배치 시점에 정해져야 한다(``ratios``/``salt``).

    Attributes:
        target: 채울 파생 store (주입; 직렬화 제외).
        ratios: split 비율 — 빌드가 배정하므로 여기 산다(내보내기가 아니라).
        salt:   split 해시 salt — 같은 정본을 다르게 재분할하되 재현 가능하게.
    """

    unit:     str               = "object"   # object = 객체 하나가 sample / frame = 프레임 하나가 sample
    category: str               = STAGED     # 검수 끝난 정본만 파생한다
    ratios:   dict[str, float]  = field(default_factory=lambda: dict(DEFAULT_RATIOS))
    salt:     str               = ""
    target:   Sample_Set | None = None

    __exclude_serialize__: ClassVar[set[str]] = {"config_type", "target"}

    def _label(self) -> str:
        return self.name or "sample"

    @property
    def _materialize(self) -> bool:
        """crop 체인이 있으면 payload 를 resolve 한다 — 없으면 A+ 순수 역참조(파일 I/O 0)."""
        return bool(self.processes)

    # ── 입력 ──────────────────────────────────────────────────────────────────
    def _block_ctx(self, store, stem: str, frame: Data_Ref) -> dict:
        if not self._materialize:
            return {}
        _ctx: dict = {"stem": stem}                     # 프레임 leaf(base image·segment) 1회 resolve
        _ctx.update(resolve(store.root, (self.category, stem), frame))
        return _ctx

    def _unit_ctx(self, store, stem: str, bctx: dict,
                  obj_id: str | None, obj: Data_Ref | None) -> dict:
        _ctx = {**bctx, "obj_id": obj_id, **(inline_ctx(obj) if obj is not None else {})}
        if self._materialize:
            _mask = _obj_mask(bctx.get("segment"), obj_id)   # segment→obj mask (frame-단위는 obj_id 없음)
            if _mask is not None:
                _ctx["mask"] = _mask                         # Frame_crop 입력
        return _ctx

    # ── 출력: 파생 store 에 sample 하나로 배치 ─────────────────────────────────
    def _emit(self, store, unit: Unit, ctx: dict) -> None:
        """unit 하나 → sample 하나. object 단위면 객체가, frame 단위면 프레임이 sample 이다."""
        _sid = f"{unit.stem}_{unit.obj_id}" if unit.obj_id is not None else unit.stem
        self.target.Place(_sid, self._sample_ref(unit),
                          split=self._split_for(unit.stem),   # 같은 프레임 → 한 split
                          crop=ctx.get("crop"))               # 레시피에 crop 체인이 있을 때만

    # ── split 배정 (빌드 시점 — 범주가 곧 split 이라 배치 전에 정해져야 한다) ───────
    @staticmethod
    def _norm_ratios(ratios: dict[str, float]) -> dict[str, float]:
        """``ratios`` 를 합=1 로 정규화 (합이 0이면 균등)."""
        _total = sum(ratios.get(_s, 0.0) for _s in SPLITS)
        if _total <= 0:
            return {_s: 1.0 / len(SPLITS) for _s in SPLITS}
        return {_s: ratios.get(_s, 0.0) / _total for _s in SPLITS}

    def _split_for(self, stem: str) -> str:
        """정본 frame stem → split (해시 결정적 배정; ``ratios`` 누적 구간에 떨군다).

        같은 stem 은 항상 같은 split 이라 재빌드에 안정하고, 객체를 **frame** stem 으로 배정하므로 같은
        이미지에서 나온 sample 은 한 split 에 몰린다(train/test leakage 방지). video 로 확장하면 배정 키를
        ``sequence_id`` 로 바꾸면 된다 — 구조는 그대로.
        """
        _h = hashlib.md5(f"{self.salt}{stem}".encode()).hexdigest()
        _f = int(_h[:16], 16) / float(1 << 64)          # [0, 1)
        _norm = self._norm_ratios(self.ratios)
        _acc = 0.0
        for _split in SPLITS:
            _acc += _norm.get(_split, 0.0)
            if _f < _acc:
                return _split
        return SPLITS[-1]

    # ── sample 조립 ────────────────────────────────────────────────────────────
    @staticmethod
    def _sample_ref(unit: Unit) -> Data_Ref:
        """sample 컨테이너 — 정본 역참조(``source_stem``/``source_obj``) + ``class_id`` attr.

        payload 실체화는 여기서 안 한다(A+ 역참조) — 소비 측(export·분석)이 정본에서 픽셀을 찾는다.
        class 는 구조 key 가 아니라 attr 이다: 폴더로도 표현하면 같은 사실이 두 곳에 살고, 재분류(라벨링
        도구의 핵심 상호작용)가 attr 갱신이 아니라 파일 이동이 된다.
        """
        _ref = Data_Ref(info={})
        _ref.Set_attr("source_stem", unit.stem)
        if unit.obj_id is not None:                          # object 단위 — 객체 하나가 sample
            _ref.Set_attr("source_obj", unit.obj_id)
            _ref.Set_attr("class_id", (unit.obj.Attr("class_id") if unit.obj else "") or UNLABELED)
            return _ref
        if unit.frame is not None:                           # frame 단위 — 객체들을 통째로 (detection)
            for _oid, _obj in unit.frame.Branches().items():
                _ref.Push(_oid, _obj.Clone())
        return _ref
