"""**flat 트리 스키마** — 유일 노드 ``Data_Ref`` + forest 파사드 ``Bucket_Store`` (데이터모델).

노드 클래스(``Node``/``Stem``/``Obj``)가 없다. 트리는 ``Data_Ref`` 하나로 재귀한다:

- **leaf** — ``type`` = image/attr/rle… , ``info`` = payload(값/파일 위치).
- **컨테이너** — ``type="stem"`` , ``info: dict[str, Data_Ref]`` = 자식(leaf 든 중첩 stem 이든).
  obj_id/이름은 부모 ``info`` 의 **key**(별도 저장 없음 — 항상 부모 통해 접근), class 라벨은 ``info["class_id"]``.

``Bucket_Store`` 는 트리 노드가 아니라 **forest 컨테이너**(``params`` + ``buckets``)로, 필드·범주 편의·
순회(``Iter_*``)만 든다 — **디스크 I/O(영속·전이·병합)는 데이터모델이 모르고** [`store_io.py`](store_io.py)
자유함수가 store 를 받아 수행한다. 트리 순회 헬퍼 ``_iter_leaves`` (``type`` 으로 leaf/stem 을 가름).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Iterator

from .handler import Data_Ref


def _As_refs(data: dict) -> dict[str, Data_Ref]:
    """dict 값을 모두 ``Data_Ref`` 로 변환한다 (leaf·stem 무관; stem 은 __post_init__ 이 자식 재구성)."""
    return {_k: _v if isinstance(_v, Data_Ref) else Data_Ref(**_v)
            for _k, _v in data.items()}


def Attr(ref: Data_Ref, name: str, default: str = "") -> str:
    """컨테이너 ``ref`` 의 인라인 attr 값 (``info[name].info["value"]``; 없으면 default). class_id 등 라벨용."""
    _a = ref.info.get(name)
    return _a.info.get("value", default) if isinstance(_a, Data_Ref) else default


def Set_attr(ref: Data_Ref, name: str, value) -> None:
    """컨테이너 ``ref`` 의 인라인 attr 를 설정한다 (있으면 값 갱신, 없으면 attr ``Data_Ref`` 생성)."""
    _a = ref.info.get(name)
    if isinstance(_a, Data_Ref):
        _a.info["value"] = value
    else:
        ref.info[name] = Data_Ref(type="attr", info={"value": value})


@dataclass
class Bucket_Store:
    """범주별 최상위 컨테이너 = **forest 파사드** (트리 노드 아님, 데이터모델).

    ``params``(범주 무관 root leaf) + ``buckets``(``{범주: {key: 컨테이너 Data_Ref}}``, n개 독립
    persistence root)를 든다. 항목(범주 직속)은 ``type="stem"`` Data_Ref. 여기 사는 건 fs root · 범주
    고정(``CATEGORIES``) · 범주 편의 · 순회(``Iter_*``)뿐 — **디스크 I/O(영속·전이·병합)는 안 든다**
    (``store_io`` 자유함수가 store 를 받아 수행; 데이터모델은 I/O 를 모른다). 트리 순회 헬퍼는
    ``_iter_leaves``(``type`` 으로 leaf/stem 가름). 범주 **이름 목록**은 ``CATEGORIES``(ClassVar), 그
    이름→항목 **데이터**는 ``buckets``(필드) — 구 ``categories`` 가 대소문자만 달라 혼동돼 개명.

    Attributes:
        root:    fs 루트 (직렬화 제외 — 로드 위치 주입).
        params:  범주 무관 root leaf (이름 → ``Data_Ref``; top 사이드카로 나감).
        buckets: 범주 → 항목 dict (``{key: 컨테이너 Data_Ref}``). CATEGORIES 로 고정.
    """

    root:       str = ""
    params:     dict[str, Data_Ref] = field(default_factory=dict)
    buckets:    dict[str, dict[str, Data_Ref]] = field(default_factory=dict)

    CATEGORIES: ClassVar[tuple[str, ...]] = ()
    TOP_STEM:   ClassVar[str] = "store"   # root params 사이드카 stem → {root}/.meta/{TOP_STEM}.json

    def __post_init__(self) -> None:
        self.params = _As_refs(self.params)
        self.buckets = {_c: _As_refs(_items) for _c, _items in self.buckets.items()}
        for _c in self.CATEGORIES:                       # 유효 범주 보장 + 결정적 순서
            self.buckets.setdefault(_c, {})

    @staticmethod
    def _iter_leaves(
        ref: Data_Ref, path: tuple[str, ...]
    ) -> Iterator[tuple[tuple[str, ...], str, Data_Ref]]:
        """컨테이너 ``ref`` 아래 모든 leaf 를 ``(path, name, ref)`` 로 재귀 순회 (stem 은 파고듦)."""
        for _name, _entry in ref.info.items():
            if _entry.type == "stem":
                yield from Bucket_Store._iter_leaves(_entry, path + (_name,))
            else:
                yield path, _name, _entry

    # ── 범주 레벨 편의 (CATEGORIES 의존) ────────────────────────────────────────
    def Category_root(self, category: str) -> str:
        """그 범주의 파일 루트 = ``{root}/{category}`` (handler 가 payload·구조 위치 잡는 용)."""
        return str(Path(self.root) / category)

    def Bucket(self, category: str) -> dict[str, Data_Ref]:
        """그 범주의 항목 dict (``{key: 컨테이너 Data_Ref}``). live 참조."""
        return self.buckets[category]

    def Set(self, key: str, ref: Data_Ref, *,
            category: str | None = None, is_param: bool = False) -> None:
        """forest 최상위에 ``Data_Ref`` 를 배치하는 **단일 쓰기 게이트** — sink 이 내부 dict 를 직접 안 만지게.

        ``is_param`` 이면 범주 무관 root leaf(``params``)에, 아니면 ``category`` 버킷(범주 직속 항목)에
        넣는다. params 쓰기(finalize·raw params)와 stem 등록(Convert)이 같은 "dict 에 ref 삽입"이라 한
        메서드로 합쳤다(값→ref 는 ``handler`` 소유; 여기선 배치만).
        """
        if is_param:
            self.params[key] = ref
        else:
            self.buckets[category][key] = ref

    def Category_of(self, key: str) -> str | None:
        """key 가 사는 범주 (없으면 None; CATEGORIES 순)."""
        for _c in self.CATEGORIES:
            if key in self.buckets[_c]:
                return _c
        return None

    def Find(self, key: str) -> Data_Ref | None:
        """key 의 항목(컨테이너 ``Data_Ref``)을 범주 무관하게 찾는다 (CATEGORIES 순; 메모리에 있는 것만)."""
        for _c in self.CATEGORIES:
            _item = self.buckets[_c].get(key)
            if _item is not None:
                return _item
        return None

    def Iter_category(self, category: str) -> Iterator[tuple[str, Data_Ref]]:
        """한 범주 항목을 ``(key, 컨테이너 Data_Ref)`` 로 순회."""
        yield from self.buckets[category].items()

    def Iter_all(self) -> Iterator[tuple[str, str, Data_Ref]]:
        """전 범주 항목을 ``(category, key, 컨테이너 Data_Ref)`` 로 순회."""
        for _c in self.CATEGORIES:
            for _k, _item in self.buckets[_c].items():
                yield _c, _k, _item

    def Iter_refs(self) -> Iterator[tuple[tuple[str, ...], str, Data_Ref]]:
        """forest 전 leaf 를 ``(path, name, ref)`` 로 순회 — params(``path=()``) + 각 항목 subtree union."""
        for _name, _ref in self.params.items():
            yield (), _name, _ref
        for _c, _k, _item in self.Iter_all():
            yield from self._iter_leaves(_item, (_c, _k))
