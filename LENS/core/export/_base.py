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

from ..constant import UNCLASSIFIED_ID, UNLABELED_CLASS
from ..format.id_map import Id_entry, Id_map
from ..store import Dataset_Meta, Sample_Set

#: serializer 가 **자기 형태로 확정해 따로 내는** params — 정본 값을 그대로 복사하면 두 진실이 된다.
#: ``id_map``: 내부 조회는 `_resolve_classes` 가 확정한 표를 쓰고(COCO ``categories`` 가 거기 묶인다),
#: 파일로는 `Id_map.Document` 가 만든 **호출번호 키 dict** 를 낸다.
_OWNED_PARAMS = frozenset({"id_map"})

__all__ = ["Exporter", "UNCLASSIFIED_ID", "UNLABELED_CLASS"]


@dataclass
class Exporter(ABC):
    """파생 store → 학습셋 레이아웃 (task 별 서브클래스).

    Attributes:
        source: 파생 store — 내보낼 sample 들 (split 범주로 이미 갈려 있다).
        meta:   정본 store — sample 이 순수 역참조라 픽셀이 여기 있을 수 있다(detection 의 프레임 이미지).
        id_map: class 표 ``{class 이름: {class_id, category_id}}``. 주어지면(정본 params 유래) 그대로,
                None 이면 class 정렬로 생성(상위 분류 없음).
    """

    source: Sample_Set
    meta:   Dataset_Meta | None    = None
    id_map: dict[str, dict] | None = None
    task:   str                    = ""    # 공유 serializer 가 데이터 성격을 읽는 자리 (seg→mask 토글)

    #: **기록 최소 수량** — 전 split 에서 이만큼 안 나온 ``class_id`` 의 인스턴스는 안 적는다(0 = 끄기).
    #:
    #: **id_map 에서는 안 뺀다.** 표는 부품 목록이라 "이번 내보내기에 몇 건 있었나" 와 수명이 다르다 —
    #: 빼면 번호가 밀려 이미 학습한 체크포인트와 어긋난다. 빠지는 것은 **주석**뿐이다.
    min_count: int = 0

    @abstractmethod
    def Export(self, dest: str | Path) -> None:
        """``dest`` 아래에 이 task 의 레이아웃으로 실체화한다."""

    # ── 공통 ──────────────────────────────────────────────────────────────────
    def _resolve_classes(self, classes) -> dict[str, dict]:
        """class 표 확정 → ``{이름: {class_id, category_id}}``.

        정본 표(``id_map``)가 있으면 그대로 쓴다. 없으면 데이터에 실제로 나온 ``class_id`` 번호로 표를
        짓고 **이름 자리에 번호를 적는다** — 이름은 정본만 아는 것이라 지어내지 않는다.

        **번호를 다시 매기지 않는다.** class_id 는 ArcFace 프로토타입 행이자 배포 ONNX 출력 인덱스라
        내보낼 때 재배정하면 기존 체크포인트와 어긋난다. 정본이 든 번호가 곧 산출물의 번호다.

        ``category_id``(상위 분류)도 정본만 안다 — 자동 경로는 0(미분류)이다.

        Args:
            classes: 데이터에 나온 ``class_id`` 번호 집합 (정본 표가 있으면 안 쓴다).
        """
        if self.id_map:
            return {str(_c): {"class_id":    int(_e["class_id"]),
                              "category_id": int(_e.get("category_id", 0))}
                    for _c, _e in self.id_map.items()}
        return {str(_i): {"class_id": int(_i), "category_id": 0}
                for _i in sorted(classes) if int(_i) != UNCLASSIFIED_ID}

    @staticmethod
    def _class_names(table: dict[str, dict]) -> dict[int, str]:
        """확정된 표 → ``{class_id: 이름}`` — 번호를 폴더 이름 등 **표시**로 되돌릴 때."""
        return {int(_e["class_id"]): _c for _c, _e in table.items()}

    def _id_map_document(self, table: dict[str, dict]) -> dict[int, dict]:
        """확정된 표(``{이름: {…}}``) → 파일로 낼 문서 — **0번(미분류 예약)을 세워** ``Id_map`` 에 넘긴다.

        형식(호출번호 키·번호 불변)은 [`format.id_map`](../format/id_map.py) 이 소유한다 — 정본 params 의
        id_map 과 **같은 모양**이라야 편집한 정본과 내보낸 산출물이 안 갈린다. 표는 0번을 안 든다
        (``Pipeline.Class_table`` 이 뺀다) — 학습 측 ignore_index 자리라 여기서 채운다.

        ``category_id``(상위 분류)는 **정본 params 의 id_map 이 든 값을 그대로 나른다** — LENS 가 값을
        만들지 않는다. 정본에 없으면(자동 생성 경로) 0 이고, 0 번 슬롯은 미분류라 항상 0 이다.
        여기서 지어내면 정본과 어긋나는 두 번째 진실이 되므로 **편집은 정본 쪽에서** 한다.
        """
        return Id_map(
            [Id_entry(UNCLASSIFIED_ID, UNLABELED_CLASS, {"category_id": 0})]
            + [Id_entry(_e["class_id"], _c,
                        {_k: _v for _k, _v in _e.items() if _k != "class_id"})
               for _c, _e in table.items()]).Document()

    @staticmethod
    def _copy(src: Path | None, dst: Path) -> bool:
        """원본 파일 → dst 로 복사 (없으면 False). 부모 dir 보장.

        **같은 파일이면 안 쓴다** — 내보낼 곳이 원본과 겹치면 ``copy2`` 가 터진다. 여기서 막는 것은
        마지막 그물이고, 겹침 자체는 호출 측이 먼저 거른다(:func:`~core.split.Run_split`).
        """
        if src is None or not src.exists():
            return False
        if dst.exists() and src.resolve() == dst.resolve():
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
        ``id_map.yaml`` 은 ``_resolve_classes`` 가 확정한 표에서 나오고 ``categories`` 도 같은 표를 쓴다.
        정본 params 의 원본 dict 를 옆에 또 두면 **categories 와 어긋날 수 있는 두 번째 진실**이 된다.
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
