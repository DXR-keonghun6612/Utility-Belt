"""정본 스테이지 — thin ``Dataset_Meta``(``Bucket_Store`` 서브클래스, 범주 = staging 상태).

조회·쓰기 게이트도 영속·전이도 [`../bucket_store.py`](../bucket_store.py)의 ``Bucket_Store`` 메서드가
소유한다(순수 트리 코어는 [`../../schema.py`](../../schema.py)). 여기 남는 건 **설정**(범주 목록·진입 범주)
+ 그 범주를 이름으로 노출하는 **named accessor**뿐 — 타입이 곧 트리 모양 보장이라 병합이 같은 타입끼리만.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping

from ...constant import META_STATES, MODIFIED, SKIPPED, STAGED
from ..bucket_store import Bucket_Store
from ...schema import Data_Ref


def _union_box(boxes: list) -> list[float] | None:
    """bbox 들을 **합집합**으로 (하나도 없으면 None) — 합쳐진 객체가 덮는 영역."""
    _bs = [_b for _b in boxes if isinstance(_b, (list, tuple)) and len(_b) == 4]
    if not _bs:
        return None
    return [min(float(_b[0]) for _b in _bs), min(float(_b[1]) for _b in _bs),
            max(float(_b[2]) for _b in _bs), max(float(_b[3]) for _b in _bs)]


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

    # ── 객체 편집 — 컨테이너 + segment 라벨을 함께 (obj_id↔라벨 정합) ─────────────────
    # 정본은 per-obj mask 를 안 들고 frame-level ``segment`` 한 장(픽셀 = obj_id + 1)에 담는다. 그래서
    # 컨테이너만 건드리면 라벨이 어긋난다 — 아래 둘은 **컨테이너와 라벨을 함께** 옮긴다
    # (``Delete_node`` 와 달리 segment 를 아는 정본 전용 연산). 빈 obj_id 자리는 **구멍으로 둔다** —
    # 재부여·압축은 ``Order_objects``(저장 시)의 몫이고, 편집은 정합만 지킨다.
    #
    # **둘 다 메모리만 고친다 — 디스크엔 안 쓴다.** 객체는 payload-free 라 지워도 지울 파일이 없고,
    # 라벨맵은 호출 측이 **든 그 배열**(편집 중이라 디스크보다 새롭다)을 제자리에서 고친다. 여기서
    # 저장까지 해버리면 편집 한 번마다 디스크가 바뀌어, 되돌리는 길이 "다시 읽기"가 아니게 된다.
    # 영속은 호출 측의 명시적 저장이 한다 (라스터 write + 사이드카 ``Save``).

    def Remove_object(self, key: str, obj_id: str, segment: Any = None) -> None:
        """객체를 지운다 — 컨테이너 pop + **그 객체의 segment 라벨을 0 으로** (메모리만).

        Args:
            key:     item(stem) key.
            obj_id:  지울 객체 id.
            segment: 이 item 의 라벨맵 — 호출 측이 든 **그 배열을 제자리에서** 고친다. 라벨맵을 가진
                item 이면 반드시 줘야 한다(안 주면 라벨이 유령으로 남는다).

        Raises:
            ValueError: item 이 ``segmap`` 을 가졌는데 ``segment`` 를 안 줬을 때 — 조용히 유령을
                남기느니 터진다.
        """
        _p, _item = self.Item_path(key), self.Find(key)
        if _p is None or _item is None or not _item.Has(obj_id):
            return
        if self._segment_leaf(_item) is not None and segment is None:
            raise ValueError(
                f"{key}: 라벨맵을 함께 넘겨야 한다 — 컨테이너만 지우면 라벨이 유령 mask 로 남는다")
        if segment is not None:
            segment[segment == int(obj_id) + 1] = 0     # 규약: 라벨 = obj_id + 1
        self.Delete_node(_p, obj_id)                    # 컨테이너 pop (객체는 payload 없어 파일 no-op)

    def Merge_objects(self, key: str, into: str, others: list[str], segment: Any = None) -> None:
        """객체 여럿을 하나로 합친다 — 라벨 재도색 + bbox 합집합 + 나머지 pop (메모리만).

        라벨맵은 픽셀당 라벨이 하나라 **배타적**이다. 그래서 "합친다" 는 곧 ``segment`` 에서 흡수될
        라벨들을 ``into`` 의 라벨로 **다시 칠하는** 일이고, 그 결과가 mask 합집합과 같다(겹침이 없다).

        ``into`` 의 attr 은 그대로 남는다 — **class_id 는 생존 객체 것이 이긴다**(어느 객체로 합치는지
        호출 측이 정하므로, 어느 class 가 살아남는지도 거기서 정해진다). ``bbox`` 만은 합쳐진 영역을
        덮어야 하므로 **그린 박스들의 합집합**으로 갱신한다 — mask 에서 되짚지 않는다(bbox 가 진실이다).

        Args:
            key:     item(stem) key.
            into:    살아남을 객체 id — 그 class_id·라벨이 이긴다.
            others:  흡수될 객체 id 들 (``into`` 는 무시된다).
            segment: 이 item 의 라벨맵 — 호출 측이 든 **그 배열을 제자리에서** 재도색한다.

        Raises:
            KeyError:   item 이나 객체가 없을 때.
            ValueError: 이 item 에 ``segmap`` leaf 가 없거나 ``segment`` 를 안 줬을 때 — 객체는
                라벨맵 위에서만 합쳐진다.
        """
        _p, _item = self.Item_path(key), self.Find(key)
        if _p is None or _item is None:
            raise KeyError(f"item 이 없음: {key}")
        _ids = [_o for _o in others if _o != into]
        for _o in (into, *_ids):
            if not _item.Has(_o):
                raise KeyError(f"객체가 없음: {key}/{_o}")
        if not _ids:
            return

        if self._segment_leaf(_item) is None:
            raise ValueError(f"segmap 이 없음: {key} — 객체는 라벨맵 위에서만 합칠 수 있다")
        if segment is None:
            raise ValueError(f"{key}: 라벨맵을 함께 넘겨야 한다 — 합치기는 곧 라벨 재도색이다")
        _label = int(into) + 1                           # 규약: 라벨 = obj_id + 1
        for _o in _ids:
            segment[segment == int(_o) + 1] = _label     # 흡수 — 재도색이 곧 합집합

        _box = _union_box([_item.Get(_o).Attr("bbox", None) for _o in (into, *_ids)])
        if _box is not None:
            _item.Get(into).Push("bbox", Data_Ref(format=("bbox", "list"), info={"value": _box}))
        for _o in _ids:
            self.Delete_node(_p, _o)                     # 컨테이너 pop — 빈 자리는 구멍으로

    # ── segment 접근 — 라벨을 건드리는 두 연산이 공유한다 ──────────────────────────
    def _segment_leaf(self, item: Data_Ref) -> str | None:
        """이 item 의 ``segmap`` leaf 이름 (없으면 None) — 라벨이 사는 곳."""
        return next((_n for _n, _r in item.Leaves().items()
                     if _r.format[:1] == ("segmap",)), None)

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
