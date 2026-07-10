"""**flat 트리 스키마** — 유일 노드 ``Data_Ref`` + forest 파사드 ``Bucket_Store`` (데이터모델).

노드 클래스(``Node``/``Stem``/``Obj``)가 없다. 트리는 ``Data_Ref`` 하나로 재귀한다:

- **leaf** — ``type`` = image/attr/rle… , ``info`` = payload(값/파일 위치).
- **컨테이너** — ``type="stem"`` , ``info: dict[str, Data_Ref]`` = 자식(leaf 든 중첩 stem 이든).
  obj_id/이름은 부모 ``info`` 의 **key**(별도 저장 없음 — 항상 부모 통해 접근), class 라벨은 ``info["class_id"]``.

``Bucket_Store`` 는 트리 노드가 아니라 **forest 컨테이너**(``params`` + ``buckets``)로, 필드·범주 편의·
순회(``Iter_*``)만 든다 — **디스크 I/O(영속·전이·병합)는 데이터모델이 모르고** [`store_io.py`](store_io.py)
자유함수가 store 를 받아 수행한다. 트리 순회 헬퍼 ``_iter_leaves`` (``type`` 으로 leaf/stem 을 가름).

이 모듈은 **저장·I/O 계층을 모른다** — ``handler`` 를 import 하지 않는다(반대 방향이다). 그래서 데이터
모델만 필요한 소비자는 cv2·핸들러 registry 없이 이 파일 하나만 들일 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Iterator, Mapping

from python_toolbox.data_schema import Data_Schema


@dataclass
class Data_Ref(Data_Schema):
    """트리의 **유일** 노드 — leaf payload 서술자 겸 재귀 컨테이너. ``type`` 이 둘을 가른다.

    - **leaf** (``type`` = image/array/attr/rle/segmap …): ``info`` = parameter + payload(인라인 값 or 파일 위치).
    - **컨테이너** (``type`` = ``"stem"``): ``info`` = ``dict[str, Data_Ref]`` (자식들; leaf 든 중첩 stem 이든).
      obj_id/이름은 부모 ``info`` 의 **key**, class 라벨은 ``info["class_id"]``(attr) 로 산다.

    **서술자일 뿐 payload 가 아니다** — 실체화(파일 read/write, 인코딩, 경로 파생)는 ``handler`` 가
    ``type`` 으로 디스패치해 수행한다. 그래서 이 클래스는 handler 를 모른다(데이터모델 → I/O 단방향).
    값 덤프는 ``Extract``, 구조 직렬화는 ``Serialize``(``Data_Schema`` 가 중첩 ``Data_Ref`` 를 재귀
    직렬화; 역은 ``__post_init__`` 이 재구성).

    Attributes:
        type:   핸들러 키 (leaf) 또는 ``"stem"``(컨테이너). 로드/저장·재귀 동작을 결정.
        format: 그 핸들러 안의 방향/직렬화 (ext·dtype·encoding). 컨테이너는 무의미(``""``).
        info:   leaf = parameter + payload(``value``/``dir``) / 컨테이너 = 자식 ``dict[str, Data_Ref]``.
    """

    type:   str
    format: str            = ""
    info:   dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type == "stem":                        # 컨테이너 → 자식(info 값)을 Data_Ref 로 재구성(재귀)
            self.info = {_k: _v if isinstance(_v, Data_Ref) else Data_Ref(**_v)
                         for _k, _v in self.info.items()}

    def Is_stem(self) -> bool:
        """컨테이너(``type=="stem"``)인지 — ``info`` 로 자식을 재귀로 든 노드."""
        return self.type == "stem"

    def Is_inline(self) -> bool:
        """leaf payload 를 ``info`` 에 인라인 보관(attr/rle/bbox 등)이면 True, 파일 참조면 False.

        내보낼 때 leaf 처리를 가른다(inline → 값 그대로 / file → handler). 판별은 파일 위치(``dir``)
        유무 — 인라인 서술자는 위치 키를 갖지 않는다. (컨테이너엔 호출하지 않음.)
        """
        return "dir" not in self.info

    def Clone(self) -> "Data_Ref":
        """이 서브트리의 깊은 사본 (``Serialize`` 왕복).

        다른 트리의 노드를 그대로 꽂으면 두 트리가 같은 객체를 공유해, 한쪽 수정이 다른 쪽으로 샌다.
        트리 경계를 넘겨 들이는 ref 는 이 메서드를 통과한다.
        """
        return Data_Ref(**self.Serialize())


# ── 트리 순회 — leaf 주소 지정의 유일한 출처 ──────────────────────────────────────
def Iter_leaves(ref: Data_Ref, path: tuple[str, ...] = ()
                ) -> Iterator[tuple[tuple[str, ...], str, Data_Ref]]:
    """컨테이너 ``ref`` 아래 모든 leaf 를 ``(path, name, ref)`` 로 재귀 순회 (stem 은 파고듦).

    ``path`` 는 조상 stem 의 key 들이다. payload 파일 주소는 ``(stem, obj_id=path[-1])`` 로 잡히므로
    (``handler`` 의 ``{root}/{dir}/{stem}[_{obj_id}].{fmt}``), **이 함수가 주소 지정의 유일한 출처**다 —
    같은 순회를 두 곳에서 따로 구현하면 두 규약이 갈라져 payload 가 조용히 엇나간다.
    """
    for _name, _entry in ref.info.items():
        if _entry.Is_stem():
            yield from Iter_leaves(_entry, path + (_name,))
        else:
            yield path, _name, _entry


def Merge_into(dst: Data_Ref, src: Data_Ref
               ) -> list[tuple[tuple[str, ...], str, Data_Ref]]:
    """``src`` 서브트리에서 **``dst`` 에 없는 것만** 들인다 (host 가 이긴다). 순수 — 디스크를 모른다.

    겹치는 컨테이너는 파고들고, 없는 노드는 ``Clone`` 해서 꽂는다. 들어온 leaf 들을 ``Iter_leaves`` 와
    **같은 모양**(``(path, name, ref)``)으로 돌려주므로, 호출 측(``store_io``)이 그 leaf 의 payload 만
    골라 복사할 수 있다 — "무엇을 들일까"(데이터모델)와 "그 파일을 어디로"(I/O)가 갈린다.
    """
    _inserted: list[tuple[tuple[str, ...], str, Data_Ref]] = []
    for _name, _entry in src.info.items():
        _cur = dst.info.get(_name)
        if _entry.Is_stem():
            if isinstance(_cur, Data_Ref) and _cur.Is_stem():
                for _p, _n, _r in Merge_into(_cur, _entry):          # 양쪽에 있음 → 파고듦
                    _inserted.append(((_name,) + _p, _n, _r))
            else:
                _clone = _entry.Clone()                              # 통째 삽입
                dst.info[_name] = _clone
                _inserted += [((_name,) + _p, _n, _r)
                              for _p, _n, _r in Iter_leaves(_clone)]
        elif _cur is None:                                           # leaf — host 에 없을 때만
            _clone = _entry.Clone()
            dst.info[_name] = _clone
            _inserted.append(((), _name, _clone))
    return _inserted


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
    persistence root)를 든다. **버킷 하나가 곧 디스크 디렉터리**(``Category_root``)라 벌크 연산(다 된
    것만 빼내기·병합)이 버킷 단위로 자연히 떨어진다 — 이 동형성이 ``buckets`` 의 존재 이유다.

    **불변식 — 한 key 는 정확히 한 버킷에 산다.** ``Find``/``Category_of``/``store_io.Delete`` 가 전부
    이걸 전제한다. 강제하는 곳은 **쓰기 문**(``Set``/``Get_or_add``)이고, 디스크에서 들어오는 중복은
    ``store_io.Restore`` 가 막는다. 내부 dict 를 직접 만지는 건 친구 모듈 ``store_io`` 뿐이라
    ``Bucket()`` 은 **읽기 전용 뷰**를 준다.

    디스크 I/O(영속·전이·병합)는 안 든다 — ``store_io`` 자유함수가 store 를 받아 수행한다.

    서브클래스는 **설정만** 고정한다: ``CATEGORIES``(범주 이름) · ``DEFAULT_CATEGORY``(새 항목이 들어오고,
    내용이 바뀐 항목이 되돌아가는 진입 범주) · ``TOP_STEM``. 타입이 곧 **트리 모양 보장**이라
    ``store_io.Merge`` 는 같은 타입끼리만 허용한다.

    Attributes:
        root:    fs 루트 (직렬화 제외 — 로드 위치 주입).
        params:  범주 무관 root leaf (이름 → ``Data_Ref``; top 사이드카로 나감).
        buckets: 범주 → 항목 dict (``{key: 컨테이너 Data_Ref}``). CATEGORIES 로 고정.
    """

    root:       str = ""
    params:     dict[str, Data_Ref] = field(default_factory=dict)
    buckets:    dict[str, dict[str, Data_Ref]] = field(default_factory=dict)

    CATEGORIES:       ClassVar[tuple[str, ...]] = ()
    DEFAULT_CATEGORY: ClassVar[str] = ""  # 새 항목의 진입 범주 (내용이 바뀌면 여기로 되돌린다)
    TOP_STEM:         ClassVar[str] = "store"   # root params 사이드카 stem → {root}/.meta/{TOP_STEM}.json

    def __post_init__(self) -> None:
        self.params = _As_refs(self.params)
        self.buckets = {_c: _As_refs(_items) for _c, _items in self.buckets.items()}
        for _c in self.CATEGORIES:                       # 유효 범주 보장 + 결정적 순서
            self.buckets.setdefault(_c, {})

    # ── 범주 레벨 편의 (CATEGORIES 의존) ────────────────────────────────────────
    def Category_root(self, category: str) -> str:
        """그 범주의 파일 루트 = ``{root}/{category}`` (handler 가 payload·구조 위치 잡는 용)."""
        return str(Path(self.root) / category)

    def Bucket(self, category: str) -> Mapping[str, Data_Ref]:
        """그 범주의 항목 (``{key: 컨테이너 Data_Ref}``) — **읽기 전용 뷰**.

        쓰기는 ``Set``/``Get_or_add`` 를 통과해야 불변식(한 key = 한 버킷)이 지켜진다. 항목 **내부**
        (``ref.info``)는 자유롭게 고쳐도 된다 — 불변식은 최상위 배치에만 걸린다.
        """
        return MappingProxyType(self.buckets[category])

    def Set(self, key: str, ref: Data_Ref, *,
            category: str | None = None, is_param: bool = False) -> None:
        """forest 최상위에 ``Data_Ref`` 를 배치하는 **쓰기 게이트**.

        ``is_param`` 이면 범주 무관 root leaf(``params``)에, 아니면 버킷(범주 직속 항목)에 넣는다.
        ``category`` 를 생략하면 ``DEFAULT_CATEGORY``.

        Raises:
            KeyError: 같은 key 가 **다른 범주**에 이미 있을 때. 조용히 중복을 만들지 않는다 — 호출 측이
                ``store_io.Move``(옮기기) / ``Get_or_add``(있으면 그대로) / ``store_io.Delete`` 중 하나를
                고른다.
        """
        if is_param:
            self.params[key] = ref
            return
        _cat = category or self.DEFAULT_CATEGORY
        _cur = self.Category_of(key)
        if _cur is not None and _cur != _cat:
            raise KeyError(
                f"{type(self).__name__}: '{key}' 는 이미 '{_cur}' 범주에 있다 "
                f"('{_cat}' 로 중복 등록 불가 — Move/Get_or_add/Delete 중 선택)")
        self.buckets[_cat][key] = ref

    def Get_or_add(self, key: str, ref: Data_Ref, *, category: str | None = None) -> Data_Ref:
        """key 가 **어느 범주에든** 있으면 그 항목을 그대로 돌려주고, 없으면 넣고 돌려준다.

        재-ingest(재-convert·재-sample)의 계약 — 이미 있는 항목은 **현재 범주(=상태)를 유지**한다.
        내보내기가 범주 기반이므로 검수 이력을 재수집이 덮어써서는 안 된다.
        """
        _cur = self.Find(key)
        if _cur is not None:
            return _cur
        self.buckets[category or self.DEFAULT_CATEGORY][key] = ref
        return ref

    def Category_of(self, key: str) -> str | None:
        """key 가 사는 범주 (없으면 None; CATEGORIES 순)."""
        for _c in self.CATEGORIES:
            if key in self.buckets[_c]:
                return _c
        return None

    def Has(self, key: str) -> bool:
        """key 가 어느 범주에든 있는지."""
        return self.Category_of(key) is not None

    def Conflicts(self, other: "Bucket_Store") -> list[str]:
        """``other`` 를 들일 때 겹치는 key 목록 (범주 무관). 디스크를 안 본다 — 병합 전 질의용."""
        return [_k for _, _k, _ in other.Iter_all() if self.Has(_k)]

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
            for _p, _n, _r in Iter_leaves(_item):
                yield (_c, _k) + _p, _n, _r
