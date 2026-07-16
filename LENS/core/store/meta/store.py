"""정본 스테이지 — thin ``Dataset_Meta``(``Bucket_Store`` 서브클래스, 범주 = staging 상태).

조회·쓰기 게이트도 영속·전이도 [`../bucket_store.py`](../bucket_store.py)의 ``Bucket_Store`` 메서드가
소유한다(순수 트리 코어는 [`../../schema.py`](../../schema.py)). 여기 남는 건 **설정**(범주 목록·진입 범주)
+ 그 범주를 이름으로 노출하는 **named accessor**뿐 — 타입이 곧 트리 모양 보장이라 병합이 같은 타입끼리만.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Mapping

import numpy as np

from ...constant import META_STATES, MODIFIED, SKIPPED, STAGED
from ..bucket_store import Bucket_Store
from ...format import rle
from ...schema import Data_Ref


def _union_box(boxes: list) -> list[float] | None:
    """bbox 들을 **합집합**으로 (하나도 없으면 None) — 합쳐진 객체가 덮는 영역."""
    _bs = [_b for _b in boxes if isinstance(_b, (list, tuple)) and len(_b) == 4]
    if not _bs:
        return None
    return [min(float(_b[0]) for _b in _bs), min(float(_b[1]) for _b in _bs),
            max(float(_b[2]) for _b in _bs), max(float(_b[3]) for _b in _bs)]


def _union_mask(masks: list) -> dict | None:
    """객체 mask(rle) 들을 픽셀 **OR** 로 합쳐 rle 로 (하나도 없으면 None).

    라벨맵 시절엔 배타적이라 재도색이 곧 합집합이었지만, 객체별 mask 는 겹칠 수 있어 픽셀 OR 로 합친다.
    """
    _arrs = [rle.To_mask(_m.info["value"]) for _m in masks
             if _m is not None and _m.info.get("value")]
    if not _arrs:
        return None
    return rle.From_mask(np.logical_or.reduce(_arrs).astype(np.uint8))


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

    # ── 객체 편집 — 컨테이너·attr 만 (라벨맵 재도색은 호출 측이) ──────────────────────
    # 객체 geometry 는 frame-level ``segment`` 한 장(픽셀 = obj_id + 1)에 산다. 그런데 그 라벨맵 재도색은
    # **여기서 안 한다** — store 는 계층상 ``func``(합성)에 못 닿기 때문이다(store → process 금지). 라벨맵을
    # 든 호출 측(gui 편집기·process)이 ``func.mask`` 로 재도색한 **뒤** 아래를 부른다. store 가 드는 건
    # 라벨맵 **밖** 데이터(컨테이너·bbox attr)뿐이다.
    #
    # **메모리만 고친다 — 디스크엔 안 쓴다.** 객체는 payload-free 라 지워도 지울 파일이 없다. 빈 obj_id
    # 자리는 **구멍으로 둔다** — 재부여·압축은 ``Order_objects``(저장 시)의 몫이고, 편집은 정합만 지킨다.
    # 영속은 호출 측의 명시적 저장이 한다(라스터 write + 사이드카 ``Save``).
    #
    # **anti-ghost 는 이제 호출 측 규율이다** — store 가 재도색을 못 하니 "라벨맵을 안 줬다"고 막을 수도
    # 없다. 컨테이너만 지우고 라벨을 안 지우면 유령이 남는다 — 호출 측이 ``func.mask.Erase``/``Merge_into``
    # 를 먼저 부를 책임을 진다.

    def Remove_object(self, key: str, obj_id: str) -> None:
        """객체 컨테이너를 지운다 (메모리만 — payload-free 라 파일 no-op).

        라벨맵 재도색은 안 한다(위 주석) — 호출 측이 ``func.mask.Erase`` 로 그 라벨을 지운 뒤 부른다.
        """
        _p, _item = self.Item_path(key), self.Find(key)
        if _p is None or _item is None or not _item.Has(obj_id):
            return
        self.Delete_node(_p, obj_id)                    # 컨테이너 pop (객체는 payload 없어 파일 no-op)

    def Merge_objects(self, key: str, into: str, others: list[str]) -> None:
        """객체 여럿을 하나로 — bbox 합집합을 ``into`` 에 + 나머지 컨테이너 pop (메모리만).

        라벨맵 재도색은 안 한다 — 호출 측이 ``func.mask.Merge_into`` 로 흡수 라벨을 ``into`` 로 다시 칠한
        **뒤** 이걸 부른다. store 가 드는 건 라벨맵 밖 데이터다: ``into`` 의 attr 은 그대로 남고(class_id 는
        생존 객체가 이긴다), ``bbox`` 만 합쳐진 영역을 덮게 **그린 박스들의 합집합**으로 갱신한다(bbox 가
        진실 — mask 에서 되짚지 않는다).

        Args:
            key:    item(stem) key.
            into:   살아남을 객체 id — 그 class_id 가 이긴다.
            others: 흡수될 객체 id 들 (``into`` 는 무시된다).

        Raises:
            KeyError: item 이나 객체가 없을 때.
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
        _box = _union_box([_item.Get(_o).Attr("bbox", None) for _o in (into, *_ids)])
        if _box is not None:
            _item.Get(into).Push("bbox",
                                 Data_Ref(format=("region", "bbox", "xyxy"), info={"value": _box}))
        _mask = _union_mask([_item.Get(_o).Get("mask") for _o in (into, *_ids)])
        if _mask is not None:                            # 객체 mask 는 배타적이지 않을 수 있어 픽셀 OR
            _item.Get(into).Push("mask",
                                 Data_Ref(format=("mask", "rle"), info={"value": _mask}))
        for _o in _ids:
            self.Delete_node(_p, _o)                     # 컨테이너 pop — 빈 자리는 구멍으로

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
