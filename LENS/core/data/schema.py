"""**flat 트리 스키마** — 유일 노드 ``Data_Ref`` + forest 파사드 ``Bucket_Store``.

노드 클래스(``Node``/``Stem``/``Obj``)가 없다. 트리는 ``Data_Ref`` 하나로 재귀한다:

- **leaf** — ``type`` = image/attr/rle… , ``info`` = payload(값/파일 위치).
- **컨테이너** — ``type="stem"`` , ``info: dict[str, Data_Ref]`` = 자식(leaf 든 중첩 stem 이든).
  obj_id/이름은 부모 ``info`` 의 **key**(별도 저장 없음 — 항상 부모 통해 접근), class 라벨은 ``info["class_id"]``.

``Bucket_Store`` 는 트리 노드가 아니라 **forest 컨테이너**(``params`` + ``categories``)이고, 트리 재귀(순회·
전이·병합)를 ``type`` 으로 leaf/stem 을 갈라 **stateless 헬퍼**로 소유한다. 디스크는 전부 handler 계층:
leaf → ``handler.<op>``(ref.type 디스패치), 구조 사이드카 → ``Structure``(``.meta/{stem}.json``, 항목 단위).
``op`` 는 언제나 handler 함수명 키워드(Move/Copy/Delete) — 센티널 없음.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Iterator

from python_toolbox.file import Write_to

from . import handler
from .handler import Data_Ref, Structure


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
    """범주별 최상위 컨테이너 = **forest 파사드** (트리 노드 아님).

    ``params``(범주 무관 root leaf) + ``categories``(``{범주: {key: 컨테이너 Data_Ref}}``, n개 독립
    persistence root)를 든다. 항목(범주 직속)은 ``type="stem"`` Data_Ref. 여기 사는 건 fs root · 범주
    고정(``CATEGORIES``) · 범주 편의 · 부트(``Load``) · 흩기(``Scatter``)·번들(``Gather``)·전이·병합뿐 —
    트리 재귀는 ``type`` 으로 갈리는 **stateless 헬퍼**(``_iter_leaves``/``_transit``/``_merge_ref``)로 소유.

    Attributes:
        root:       fs 루트 (직렬화 제외 — 로드 위치 주입).
        params:     범주 무관 root leaf (이름 → ``Data_Ref``; top 사이드카로 나감).
        categories: 범주 → 항목 dict (``{key: 컨테이너 Data_Ref}``). CATEGORIES 로 고정.
    """

    root:       str = ""
    params:     dict[str, Data_Ref] = field(default_factory=dict)
    categories: dict[str, dict[str, Data_Ref]] = field(default_factory=dict)

    CATEGORIES: ClassVar[tuple[str, ...]] = ()
    TOP_STEM:   ClassVar[str] = "store"   # root params 사이드카 stem → {root}/.meta/{TOP_STEM}.json

    def __post_init__(self) -> None:
        self.params = _As_refs(self.params)
        self.categories = {_c: _As_refs(_items) for _c, _items in self.categories.items()}
        for _c in self.CATEGORIES:                       # 유효 범주 보장 + 결정적 순서
            self.categories.setdefault(_c, {})

    # ── 트리 재귀 헬퍼 (stateless — type 으로 leaf/stem 을 가름) ────────────────────
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

    @staticmethod
    def _transit(ref: Data_Ref, *roots: str,
                 op: str, stem: str, obj_id: str | None = None) -> None:
        """컨테이너 ``ref`` 아래 leaf payload 파일을 재귀 전이한다 — ``op`` = handler 함수명(Move/Copy/Delete).

        leaf entry 는 현재 ``obj_id`` 로 ``getattr(handler, op)`` 디스패치, stem entry 는 ``obj_id`` = 그
        stem 의 key 로 파고든다(중첩 stem 자체는 파일이 없어 사이드카는 항목 단위로 Store 가 따로 씀).
        """
        for _name, _entry in ref.info.items():
            if _entry.type == "stem":
                Bucket_Store._transit(_entry, *roots, op=op, stem=stem, obj_id=_name)
            else:
                getattr(handler, op)(*roots, stem, _name, _entry, obj_id=obj_id)

    @staticmethod
    def _merge_ref(dst: Data_Ref, src: Data_Ref, *roots: str,
                   op: str | None = None, override: bool = False) -> None:
        """컨테이너 ``src`` 를 ``dst`` 에 재귀 병합 — 겹치는 stem 은 파고들고, 없으면 통째 삽입.

        stem entry 는 ``Node`` 병합처럼 재귀/삽입, leaf entry 는 직접 dispatch. ``op=None`` 이면 in-memory
        만(파일 전이 없음). 항목 내부 깊은 병합의 payload 경로 정밀도는 ``_transit`` 의 stem 인자 수준.
        """
        for _name, _entry in src.info.items():
            _cur = dst.info.get(_name)
            if _entry.type == "stem":                                 # 하위 컨테이너
                if isinstance(_cur, Data_Ref) and _cur.type == "stem" and not override:
                    Bucket_Store._merge_ref(_cur, _entry,
                                            *(str(Path(_r) / _name) for _r in roots),
                                            op=op, override=override)
                    continue
                if isinstance(_cur, Data_Ref) and op is not None:     # override → 기존 payload 제거
                    Bucket_Store._transit(_cur, *roots, op="Delete", stem=_name)
                if op is not None:
                    Bucket_Store._transit(_entry, *roots, op=op, stem=_name)
                dst.info[_name] = _entry
            elif _name not in dst.info or override:                   # leaf
                if op is not None:
                    getattr(handler, op)(*roots, None, _name, _entry, obj_id=None)
                dst.info[_name] = _entry

    # ── 범주 레벨 편의 (CATEGORIES 의존) ────────────────────────────────────────
    def Category_root(self, category: str) -> str:
        """그 범주의 파일 루트 = ``{root}/{category}`` (handler 가 payload·구조 위치 잡는 용)."""
        return str(Path(self.root) / category)

    def Bucket(self, category: str) -> dict[str, Data_Ref]:
        """그 범주의 항목 dict (``{key: 컨테이너 Data_Ref}``). live 참조."""
        return self.categories[category]

    def Category_of(self, key: str) -> str | None:
        """key 가 사는 범주 (없으면 None; CATEGORIES 순)."""
        for _c in self.CATEGORIES:
            if key in self.categories[_c]:
                return _c
        return None

    def Find(self, key: str) -> Data_Ref | None:
        """key 의 항목(컨테이너 ``Data_Ref``)을 범주 무관하게 찾는다 (CATEGORIES 순; 메모리에 있는 것만)."""
        for _c in self.CATEGORIES:
            _item = self.categories[_c].get(key)
            if _item is not None:
                return _item
        return None

    def Iter_category(self, category: str) -> Iterator[tuple[str, Data_Ref]]:
        """한 범주 항목을 ``(key, 컨테이너 Data_Ref)`` 로 순회."""
        yield from self.categories[category].items()

    def Iter_all(self) -> Iterator[tuple[str, str, Data_Ref]]:
        """전 범주 항목을 ``(category, key, 컨테이너 Data_Ref)`` 로 순회."""
        for _c in self.CATEGORIES:
            for _k, _item in self.categories[_c].items():
                yield _c, _k, _item

    def Iter_refs(self) -> Iterator[tuple[tuple[str, ...], str, Data_Ref]]:
        """forest 전 leaf 를 ``(path, name, ref)`` 로 순회 — params(``path=()``) + 각 항목 subtree union."""
        for _name, _ref in self.params.items():
            yield (), _name, _ref
        for _c, _k, _item in self.Iter_all():
            yield from self._iter_leaves(_item, (_c, _k))

    # ── 구조 영속 (top = params; 범주-항목 사이드카; 전부 Structure 위임) ─────────
    @classmethod
    def Load(cls, root: str | Path) -> "Bucket_Store":
        """디렉터리에서 복원한다 — top(params) + 범주별 항목 사이드카 (경로·읽기는 ``Structure`` 소유)."""
        _top = Structure.Read(str(root), cls.TOP_STEM) or {}
        _store = cls(root=str(root), params=_top.get("params", {}))
        for _cat in cls.CATEGORIES:
            _croot = _store.Category_root(_cat)
            for _stem in Structure.Stems(_croot):
                _d = Structure.Read(_croot, _stem)
                if _d is not None:
                    _store.categories[_cat][_stem] = Data_Ref(**_d)
        return _store

    def Save_top(self) -> None:
        """params(root leaf)만 top 사이드카로 기록한다 (params 만 바뀔 때 O(1))."""
        Structure.Write(self.root, self.TOP_STEM,
                        {"params": {_k: _v.Serialize() for _k, _v in self.params.items()}})

    def Scatter(self) -> None:
        """forest 전체를 흩는다 — top(params) + 모든 범주 항목 구조 사이드카."""
        self.Save_top()
        for _cat, _key, _item in self.Iter_all():
            Structure.Write(self.Category_root(_cat), _key, _item.Serialize())

    def Save_item(self, key: str) -> None:
        """항목 하나의 구조 사이드카만 기록한다 (편집 즉시 저장 — 증분; 없으면 no-op)."""
        _cat = self.Category_of(key)
        if _cat is not None:
            Structure.Write(self.Category_root(_cat), key, self.categories[_cat][key].Serialize())

    def Drop(self, category: str, key: str) -> None:
        """항목 구조 사이드카를 지운다 (전이·삭제로 버킷에서 빠질 때 — 메모리는 안 건드림)."""
        Structure.Delete(self.Category_root(category), key)

    def Gather(
        self, categories: list[str] | None = None, out_file: str = "bundle.json"
    ) -> str:
        """선택 범주(기본 전체)를 한 파일로 뭉친 자기완결 번들을 ``{root}/{out_file}`` 에 쓴다. 경로 반환."""
        _cats = list(self.CATEGORIES) if categories is None else categories
        _d = {
            "params": {_k: _v.Serialize() for _k, _v in self.params.items()},
            **{_c: {_k: _i.Serialize() for _k, _i in self.categories[_c].items()} for _c in _cats},
        }
        _p = Path(self.root) / out_file
        Write_to(_p, _d)
        return str(_p)

    # ── 전이 편의 (_transit[payload] + Structure[구조] + 버킷 조정) ───────────────
    def Move(self, key: str, to_category: str) -> None:
        """항목을 ``to_category`` 버킷으로 옮긴다 — payload 파일·구조 사이드카·버킷 (같은 범주 no-op)."""
        _src = self.Category_of(key)
        if _src is None:
            raise KeyError(f"이동할 항목이 없음: {key}")
        if _src == to_category:
            return
        _src_root, _dst_root = self.Category_root(_src), self.Category_root(to_category)
        _item = self.categories[_src][key]
        self._transit(_item, _src_root, _dst_root, op="Move", stem=key)   # payload 파일 이동
        self.categories[to_category][key] = self.categories[_src].pop(key)
        Structure.Move(_src_root, _dst_root, key)                         # 구조 사이드카 이동

    def Delete(self, key: str) -> None:
        """항목을 완전히 제거한다 — payload 파일·구조 사이드카·버킷 (없으면 no-op)."""
        _cat = self.Category_of(key)
        if _cat is None:
            return
        self._transit(self.categories[_cat][key], self.Category_root(_cat), op="Delete", stem=key)
        self.Drop(_cat, key)
        self.categories[_cat].pop(key, None)

    def Merge_conflicts(self, other: "Bucket_Store") -> list[str]:
        """병합 전 충돌(범주 무관 key 중복) 목록 (GUI 질의용)."""
        return [_k for _, _k, _ in other.Iter_all() if self.Category_of(_k) is not None]

    def Merge(self, other: "Bucket_Store", *, override: bool = False) -> None:
        """다른 store 를 들인다 — **같은 CATEGORIES** 가정, 범주별로 항목(범주 직속)을 병합·즉시 흩기.

        겹치는 항목은 ``_merge_ref`` 로 항목 **내부**를 재귀 병합, 새 항목이면 payload 복사(``_transit`` Copy)
        후 통째 삽입 — 어느 쪽이든 그 항목만 구조 사이드카로 흩기(증분·크래시 내구성). 충돌은 ``override`` 가
        정한다(먼저 ``Merge_conflicts`` 질의 권장).
        """
        for _cat in self.CATEGORIES:
            if _cat not in other.categories:
                continue
            _src, _dst_root = other.Category_root(_cat), self.Category_root(_cat)
            _bucket = self.categories[_cat]
            for _key, _item in other.categories[_cat].items():
                _host_cat = self.Category_of(_key)
                if _host_cat is not None and _host_cat != _cat:  # 다른 범주에 존재 (한 stem=한 범주)
                    if not override:
                        continue                                 # 충돌 → host 배치 유지
                    self.Delete(_key)                            # override → 옛 범주에서 회수
                _cur = _bucket.get(_key)
                if _cur is not None and not override:            # 같은 범주 겹침 → 항목 내부 재귀 병합
                    self._merge_ref(_cur, _item, _src, _dst_root, op="Copy", override=override)
                else:
                    if _cur is not None:                         # override → 기존 payload 제거
                        self._transit(_cur, _dst_root, op="Delete", stem=_key)
                    self._transit(_item, _src, _dst_root, op="Copy", stem=_key)   # payload 복사
                    _bucket[_key] = _item
                Structure.Write(_dst_root, _key, _bucket[_key].Serialize())       # 이 항목 즉시 흩기
        for _name, _ref in other.params.items():                 # params (root leaf)
            if _name not in self.params or override:
                handler.Copy(other.root, self.root, None, _name, _ref)
                self.params[_name] = _ref
        self.Save_top()
