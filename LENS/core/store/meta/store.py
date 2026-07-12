"""정본 스테이지 — thin ``Dataset_Meta``(``Bucket_Store`` 서브클래스, 범주 = staging 상태).

조회·쓰기 게이트도 영속·전이도 [`../bucket_store.py`](../bucket_store.py)의 ``Bucket_Store`` 메서드가
소유한다(순수 트리 코어는 [`../../schema.py`](../../schema.py)). 여기 남는 건 **설정**(범주 목록·진입 범주)
+ 그 범주를 이름으로 노출하는 **named accessor**뿐 — 타입이 곧 트리 모양 보장이라 병합이 같은 타입끼리만.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Mapping

from ...constant import META_STATES, MODIFIED, SKIPPED, STAGED
from ..bucket_store import Bucket_Store
from ...schema import Data_Ref



@dataclass
class Dataset_Meta(Bucket_Store):
    """정본 store — 범주 = staging 상태 (modified/staged/skipped).

    ``modified`` = 작업(flow 출력·가져오기), ``staged`` = 검수 완료(annotation 대상), ``skipped`` = 보류.
    새 항목과 **내용이 바뀐 항목**은 ``modified`` 로 진입한다(``DEFAULT_CATEGORY``) — 검수는 내용에 대한
    것이라 내용이 달라지면 다시 받아야 한다. class→id 매핑은 파생(sample) 소유고, meta 는 class **이름**만
    ``class_id`` LEAF 로 든다.

    설정 + named accessor 뿐 — 조회·쓰기·영속·전이는 ``Bucket_Store`` 메서드.
    """

    CATEGORIES:       ClassVar[tuple[str, ...]] = META_STATES
    DEFAULT_CATEGORY: ClassVar[str] = MODIFIED

    # ── 객체 삭제 — 컨테이너 + segment 라벨을 함께 (obj_id↔라벨 정합) ─────────────────
    def Remove_object(self, key: str, obj_id: str) -> None:
        """객체를 지운다 — 컨테이너 pop + **그 객체의 segment 라벨을 0 으로** (원자적).

        정본은 per-obj mask 를 안 들고 frame-level ``segment`` 한 장(픽셀 = obj_id+1)에 담는다. 그래서
        객체만 지우면 그 라벨이 **유령 mask** 로 남는다 — 여기서 segment 를 함께 비워 obj_id↔라벨 정합을
        지킨다. 빈 자리는 **구멍으로 둔다**(재부여·압축은 ``Order_objects`` 의 몫) — 편집은 정합만 지키고
        순번을 다시 매기지 않는다. ``Delete_node`` 와 달리 segment 를 아는 정본 전용 연산이다.
        """
        _p = self.Item_path(key)
        _item = self.Find(key)
        if _p is None or _item is None or not _item.Has(obj_id):
            return
        self._clear_label(key, _p, _item, obj_id)      # segment 라벨 0 (segmap·정수 obj_id 일 때만)
        self.Delete_node(_p, obj_id)                    # 컨테이너 pop (객체는 payload 없어 파일 no-op)
        self.Save(key)

    def _clear_label(self, key: str, path: tuple[str, ...], item: Data_Ref, obj_id: str) -> None:
        """이 객체의 라벨(obj_id+1)을 segmap leaf 에서 0 으로 칠하고 다시 저장한다 (없으면 no-op)."""
        _name, _ref = next(((_n, _r) for _n, _r in item.Leaves().items()
                            if _r.format and _r.format[0] == "segmap"), (None, None))
        if _ref is None:
            return
        try:
            _label = int(obj_id) + 1                    # 규약: 라벨 = obj_id + 1 (없으면 라벨 자리 없음)
        except (TypeError, ValueError):
            return
        _seg = self.Load(key, _name)
        if _seg is None:
            return
        _seg[_seg == _label] = 0
        _spec = {"to": "storage", "type": _ref.format[0]}
        if len(_ref.format) > 1 and _ref.format[1]:
            _spec["format"] = _ref.format[1]
        item.Push(_name, self.Route(path, _name, _spec, _seg))

    # ── named accessor — ``Bucket(상태)`` 읽기 뷰에 이름을 얹은 sugar ─────────────────
    @property
    def modified(self) -> Mapping[str, Data_Ref]:
        """작업 대상(flow 출력·가져오기) 항목 — 읽기 전용 뷰."""
        return self.Bucket(MODIFIED)

    @property
    def staged(self) -> Mapping[str, Data_Ref]:
        """검수 완료(annotation 대상) 항목 — 읽기 전용 뷰."""
        return self.Bucket(STAGED)

    @property
    def skipped(self) -> Mapping[str, Data_Ref]:
        """보류(파이프라인 제외) 항목 — 읽기 전용 뷰."""
        return self.Bucket(SKIPPED)
