"""Exporter 계약 — 파생 store → 학습 프레임워크 레이아웃.

**task·format 이 사는 곳은 여기다** — 그래서 파생(sample) 안쪽이다. 빌드는 무엇을 뽑을지(``unit``·crop)만
정하고 레이아웃은 모른다. 축이 둘이다(레지스트리·조합 설명은 [`__init__.py`](__init__.py)):

- **task** = 데이터 성격 (classification / detection / segmentation) — 빌드 ``unit`` 과 mask 필요 여부를 건다.
- **format** = 직렬화 레이아웃 (imagefolder / coco / yolo / mask) — 같은 task 를 여러 모양으로 낸다.

한 serializer 가 여러 task 를 겸한다 — ``Coco``·``Yolo`` 는 detection·segmentation 을 함께 섬기고 task 가
mask 를 토글한다([`_instance.py`](_instance.py) 의 ``Frame_exporter`` 공통 base). 원본(작업 store)은
비파괴 — payload 는 ``port.Path_of`` 로 원본 파일을 찾아 **복사**한다(디코드·재인코딩 없음).

split 은 **재배정하지 않는다** — store 가 이미 split 범주로 갈려 있다(빌드가 배정). 여기선 순회할 뿐이다.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from ..constant import UNCLASSIFIED as UNLABELED

#: id_map 0번 항목의 이름 — 미분류 예약 슬롯. 학습 측의 ignore_index 가 이 class_id 를 쓴다.
UNLABELED_CLASS = "no_label"
from ..store import Dataset_Meta, Sample_Set

#: serializer 가 **자기 형태로 확정해 따로 내는** params — 정본 값을 그대로 복사하면 두 진실이 된다.
#: ``id_map``: 내부 조회는 `_resolve_id_map` 의 flat ``{class:int}`` 를 쓰고(COCO ``categories`` 가
#: 거기 묶인다), 파일로는 `_id_map_document` 가 만든 **호출번호 키 dict** 를 낸다.
_OWNED_PARAMS = frozenset({"id_map"})

__all__ = ["Exporter", "UNLABELED", "UNLABELED_CLASS"]


@dataclass
class Exporter(ABC):
    """파생 store → 학습셋 레이아웃 (task 별 서브클래스).

    Attributes:
        source: 파생 store — 내보낼 sample 들 (split 범주로 이미 갈려 있다).
        meta:   정본 store — sample 이 순수 역참조라 픽셀이 여기 있을 수 있다(detection 의 프레임 이미지).
        id_map: class→정수 매핑. 주어지면(정본 params 유래) 그대로, None 이면 class 정렬로 생성.
    """

    source: Sample_Set
    meta:   Dataset_Meta | None    = None
    id_map: dict[str, int] | None  = None
    task:   str                    = ""    # 공유 serializer 가 데이터 성격을 읽는 자리 (seg→mask 토글)

    @abstractmethod
    def Export(self, dest: str | Path) -> None:
        """``dest`` 아래에 이 task 의 레이아웃으로 실체화한다."""

    # ── 공통 ──────────────────────────────────────────────────────────────────
    def _resolve_id_map(self, classes) -> dict[str, int]:
        """class→정수 확정 — 주어지면 그대로, 없으면 class 정렬로 1부터.

        **0 은 비워 둔다** — 미분류(class-agnostic 인스턴스)의 자리다
        (:meth:`_id_map_document` 가 ``no_label`` 항목으로 채운다).
        """
        return (dict(self.id_map) if self.id_map else
                {_c: _i for _i, _c in enumerate(sorted(classes), start=1)})

    def _id_map_document(self, ids: dict[str, int]) -> dict[int, dict]:
        """flat ``{class:int}`` → 파일로 낼 **호출번호 키 dict**.

        학습 측이 읽는 형식이다::

            0: {class_id: 0, name: no_label,      category_id: 0}
            1: {class_id: 1, name: 10D132000NT9,  category_id: 0}

        바깥 키(호출번호)와 ``class_id`` 를 **분리해서 둔다**. class_id 는 ArcFace 프로토타입의
        행 인덱스이자 배포 ONNX 출력 인덱스라, 항목을 재정렬할 때 번호가 따라 움직이면 기존
        체크포인트와 어긋난다. 분리해 두면 이름이 바뀌어도(부품코드 개정 등) 번호가 그대로임이
        diff 에 드러나고, 소비 측은 마지막 호출번호와 항목 수를 대조해 누락을 잡는다.

        ``category_id``(상위 분류)는 **아직 0 고정**이다 — LENS 에 상위 분류 개념이 없다.
        LENS 산출물을 정본으로 삼으려면 여기에 값을 넣을 편집 기능이 필요하다(미구현).
        그때까지 상위 분류를 쓰는 소비자는 이 값을 별도로 채워야 한다.
        """
        _entries = [{"class_id": 0, "name": UNLABELED_CLASS, "category_id": 0}]
        _entries += [
            {"class_id": int(_i), "name": str(_c), "category_id": 0}
            for _c, _i in sorted(ids.items(), key=lambda _kv: _kv[1])
        ]
        return {_n: _e for _n, _e in enumerate(_entries)}

    @staticmethod
    def _copy(src: Path | None, dst: Path) -> bool:
        """원본 파일 → dst 로 복사 (없으면 False). 부모 dir 보장."""
        if src is None or not src.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True

    def _export_params(self, dest: Path) -> int:
        """정본 ``params`` 를 ``{dest}/params/`` 로 낸다 — **split 폴더와 같은 레벨** (내보낸 개수 반환).

        params 는 stem 축이 없는 dataset-wide 값(roi·id_map·통계)이라 어느 split 에도 속하지 않는다 —
        그래서 store 에서와 같이(``{root}/params/``) split 의 **형제**로 앉힌다. 레이아웃은 store 를 따라
        ``{dest}/params/{이름}.{확장자}``.

        파일 payload 는 **복사**하고(디코드·재인코딩 없음), 인라인 값은 한 파일(``params.json``)에 모은다 —
        값 하나가 파일 하나가 되면 스칼라마다 파일이 생겨 폴더가 어지러워진다.

        **serializer 가 이미 내는 것(:data:`_OWNED_PARAMS`)은 뺀다** — ``id_map`` 이 그렇다. 내보낸
        ``id_map.json`` 은 ``_resolve_id_map`` 이 확정한 flat ``{class:int}`` 이고 ``categories`` 가 그걸
        쓴다. 정본 params 의 원본 dict 를 옆에 또 두면 **categories 와 어긋날 수 있는 두 번째 진실**이 된다.
        """
        if self.meta is None:
            return 0
        _dir = Path(dest) / self.meta.PARAMS
        _inline: dict = {}
        _n = 0
        for _name, _ref in self.meta.Params().items():
            if _name in _OWNED_PARAMS:                  # serializer 가 확정해 따로 낸다
                continue
            _src = self.meta.Path_of((self.meta.PARAMS,), _name, _ref)
            if _src is not None:                        # 파일 payload — 그대로 복사
                if self._copy(_src, _dir / f"{_name}{_src.suffix}"):
                    _n += 1
            else:                                       # 인라인 값 — 모아서 한 파일로
                _val = self.meta.Param(_name)
                if _val is not None:
                    _inline[_name] = _val
        if _inline:
            Write_to(_dir / "params.json", _inline)
            _n += 1
        return _n
