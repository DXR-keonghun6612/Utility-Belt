"""Sample sink 베이스 — staged unit 을 ``Sample_Set`` 작업 버킷에 배치 + split 내보내기 (task = sink).

``process`` 의 Stage 출력 계약(``Base_Sink``)을 구현한다. unit 당 1회 ``emit`` 에서 ``Place``(task별 트리
모양)로 **단일 작업 버킷**(``WORKING``)에 꽂는다 — 빌드는 split 을 모른다. sample 은 A+(순수 재생성) —
leaf 는 payload 실체화가 아니라 정본 ``(source_stem, source_obj)`` **역참조** + ``class_id`` attr 만 든다.

train/val/test 는 파생이라 **내보내기(``Export``)가** frame stem 해시로 결정적 배정해 ``{split}/…`` 로
실체화한다(재실행 안정, 같은 image 는 한 split — leakage 방지). ``Place``·``Export`` 는 task 별이라
서브클래스가 구현하고, split 배정(``_assign``)·crop 복사(``_copy_crop``)는 베이스가 공유한다.

Run 의 ``Meta_sink`` 가 자기 store(meta)에 route 하듯, sample sink 는 자기 ``target``(``Sample_Set``)에
쓴다 — Stage 가 넘기는 ``store``(=source 의 staged meta)와 별개다(source-store ≠ sink-store).
"""

from __future__ import annotations

import hashlib
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ...data import handler
from ...data.handler import Data_Ref
from ...data.sample import SPLITS, WORKING, Sample_Set
from ...data.schema import Set_attr
from ...process.sink import Base_Sink
from ...process.source import Unit

DEFAULT_RATIOS: dict[str, float] = {"train": 0.8, "val": 0.1, "test": 0.1}


@dataclass
class Sample_sink(Base_Sink):
    """staged unit → ``Sample_Set`` 배치 + split 내보내기 (task별 서브클래스).

    빌드는 split 을 모른다 — unit 을 **단일 작업 버킷**(``WORKING``)에 task 트리로 꽂을 뿐이다(``Place``).
    split(train/val/test)은 파생이라 **내보내기(``Export``)가** frame stem 해시로 가른다 — task 별 레이아웃·
    집계가 다르므로 ``Place``·``Export`` 를 서브클래스가 구현한다(``Finalize``·crop 복사 등 공통은 베이스).
    """

    target: Sample_Set

    # ── Base_Sink 계약 ─────────────────────────────────────────────────────────
    def emit(self, store, unit: Unit, ctx: dict) -> None:
        self.Place(unit, ctx)

    def close(self, store) -> None:
        self.Finalize()

    # ── 내보내기 공통 (split 배정·crop 복사) ────────────────────────────────────
    @staticmethod
    def _norm_ratios(ratios: dict[str, float]) -> dict[str, float]:
        """``ratios`` 를 합=1 로 정규화 (합이 0이면 균등)."""
        _total = sum(ratios.get(_s, 0.0) for _s in SPLITS)
        if _total <= 0:
            return {_s: 1.0 / len(SPLITS) for _s in SPLITS}
        return {_s: ratios.get(_s, 0.0) / _total for _s in SPLITS}

    @classmethod
    def _assign(cls, stem: str, ratios: dict[str, float], salt: str) -> str:
        """frame stem → split (해시 결정적 배정; ``ratios`` 누적 구간에 떨군다).

        같은 stem 은 항상 같은 split 이라 재실행에 안정하고, object 를 frame stem 으로 배정하므로 같은
        이미지의 객체는 한 split 에 몰린다(train/test leakage 방지). ``salt`` 로 재현성 유지한 채 재분할.
        """
        _h = hashlib.md5(f"{salt}{stem}".encode()).hexdigest()
        _f = int(_h[:16], 16) / float(1 << 64)          # [0, 1)
        _norm = cls._norm_ratios(ratios)
        _acc = 0.0
        for _split in SPLITS:
            _acc += _norm.get(_split, 0.0)
            if _f < _acc:
                return _split
        return SPLITS[-1]

    @staticmethod
    def _resolve_id_map(id_map: dict[str, int] | None, classes) -> dict[str, int]:
        """class→정수 매핑 확정 — 주어지면(정본 params 유래) 그대로, 없으면 class 정렬로 1부터 생성."""
        return dict(id_map) if id_map else {_c: _i for _i, _c in enumerate(sorted(classes), start=1)}

    def _copy_crop(self, ref: Data_Ref, dst_root: str | Path, sample_id: str) -> bool:
        """sample 의 crop payload 를 작업 버킷 → ``dst_root`` 로 복사한다 (없으면 no-op, 복사했으면 True).

        ``ref.info["crop"]`` leaf 의 ``dir``(class/image)가 경로에 따라오므로 dst 에 그대로 재현된다
        (예: ``{dst_root}/{class}/{sample_id}.png``). 원본(작업 store)은 비파괴(``handler.Copy``).
        """
        _crop = ref.info.get("crop")
        if _crop is None:
            return False
        handler.Copy(self.target.Category_root(WORKING), str(dst_root), sample_id, "crop", _crop)
        return True

    # ── 공통 (역참조) ──────────────────────────────────────────────────────────
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

    def _attach_crop(self, ref: Data_Ref, ctx: dict, dir_: str, sample_id: str) -> None:
        """``ctx["crop"]`` 가 있으면 payload 로 저장하고 ``ref.info["crop"]`` 에 leaf 를 단다 (없으면 no-op).

        경로는 작업 버킷(``WORKING``) 아래 ``{dir_}/{sample_id}.png`` (handler 가 파생) — classification 은
        ``dir_=class``, detection 은 ``dir_=image``. split 은 안 붙인다(내보내기가 가른다). crop 은 파생
        산출(정본으로 write-back 안 함)이라 여기 sink 가 떨군다.
        """
        _crop = ctx.get("crop")
        if _crop is None:
            return
        ref.info["crop"] = handler.Route(
            self.target.Category_root(WORKING), sample_id, "crop",
            {"to": "storage", "dir": dir_}, _crop)

    # ── task 훅 ────────────────────────────────────────────────────────────────
    @abstractmethod
    def Place(self, unit: Unit, ctx: dict) -> None:
        """한 unit 을 ``target`` 의 작업 버킷(``WORKING``)에 꽂는다 — task 별 layout(class 폴더 / image→object).

        split 은 안 붙인다(내보내기가 frame 해시로 가른다). ``ctx`` 는 체인 최종 컨텍스트 — crop 실체화 시
        ``ctx["crop"]`` (없으면 A+ 역참조만). payload 저장은 ``_attach_crop`` 헬퍼로.
        """

    def Finalize(self) -> None:
        """순회 후 1회 — 후처리 훅. 집계(id_map·COCO manifest 등)는 ``Export`` 소유. 기본 no-op."""

    @abstractmethod
    def Export(self, dest: str | Path, *,
               ratios: dict[str, float] | None = None, salt: str = "",
               id_map: dict[str, int] | None = None) -> None:
        """작업 버킷을 split 별로 갈라 ``dest`` 아래 실체화한다 — task 별 레이아웃·집계.

        split 은 ``_assign``(frame stem 해시)로 배정하고 crop payload 는 ``_copy_crop`` 으로 옮긴다
        (crop 이 실체화된 sample 만 픽셀이 나온다 — A+ 역참조만이면 복사할 파일 없음). ``ratios`` 는
        None 이면 ``DEFAULT_RATIOS``. ``id_map``(class→정수)은 주어지면(정본 params 유래) 그대로 쓰고,
        없으면 class 정렬로 자동 생성한다 — 산출물의 class↔index 일관성용.
        """
