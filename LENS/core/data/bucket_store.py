"""forest 파사드 ``Bucket_Store`` — 범주 = 트리 구조 key (nested) + 자기 영속·전이.

``tree`` 는 단일 ``Data_Ref``(BRANCH), 최상위 ``info`` 키 = ``{params, <범주들>}``. 각 범주 branch 의
자식이 item. 검색·순회·경로는 전부 ``Data_Ref`` 재귀(``Locate``/``At``/``Iter_leaves``)에 위임하고,
여기는 범주 정책 + 영속 오케스트레이션만 든다. 영속은 재귀 key-path — 사이드카 ``{root}/.meta/<*keys>.json``,
payload ``{root}/<*keys>/{name}.{ext}``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar, Iterable, Iterator, Mapping

from python_toolbox.data_schema import Data_Schema
from python_toolbox.file import Write_to

from .data_ref import Data_Ref

SKIP, OVERWRITE, MERGE = "skip", "overwrite", "merge"
MERGE_MODES = (SKIP, OVERWRITE, MERGE)


@dataclass
class Bucket_Store(Data_Schema):
    """nested tree(``{범주:{key:item}}``) + ``params`` 예약 key. 범주는 구조 key.

    Attributes:
        root: fs 루트 (``Serialize`` 제외 — 로드 위치 주입).
        tree: 단일 BRANCH — ``info`` = ``{params, <범주들>}``, 각 범주 branch 의 자식이 item.
    """

    root: str = ""
    tree: Data_Ref = field(default_factory=dict)

    CATEGORIES:       ClassVar[tuple[str, ...]] = ()
    DEFAULT_CATEGORY: ClassVar[str] = ""          # 새 항목의 진입 범주 (내용이 바뀌면 여기로 되돌린다)
    PARAMS:           ClassVar[str] = "params"     # 범주 무관 root leaf 를 담는 예약 최상위 key

    __exclude_serialize__: ClassVar[set[str]] = {"root"}

    def __post_init__(self) -> None:
        if isinstance(self.tree, dict):
            self.tree = (Data_Ref(**self.tree) if self.tree else
                         Data_Ref(info={self.PARAMS: Data_Ref(),
                                        **{_c: Data_Ref() for _c in self.CATEGORIES}}))

    # ── 쓰기 게이트 ──────────────────────────────────────────────────────────────
    def Set(self, key: str, ref: Data_Ref, *, category: str | None = None) -> None:
        """item 을 범주 branch 에 넣는다 (생략 시 ``DEFAULT_CATEGORY``). 같은 key 재등록은 덮는다."""
        self.tree.Get(category or self.DEFAULT_CATEGORY).Push(key, ref)

    def Set_param(self, name: str, ref: Data_Ref) -> None:
        """범주 무관 root leaf 를 ``params`` 에 넣는다."""
        self.tree.Get(self.PARAMS).Push(name, ref)

    def Get_or_add(self, key: str, ref: Data_Ref, *, category: str | None = None) -> Data_Ref:
        """있으면 그대로(현재 범주 유지), 없으면 심어 넣고 돌려준다 — 재-ingest 가 이력을 안 덮게."""
        _cur = self.Find(key)
        if _cur is not None:
            return _cur
        self.Set(key, ref, category=category)
        return ref

    # ── 조회 — Data_Ref 재귀(Locate/At)에 위임 ───────────────────────────────────
    def Find(self, key: str) -> Data_Ref | None:
        """key 의 item (트리 어디에 있든 재귀로; 없으면 None)."""
        _p = self.tree.Locate(key)
        return self.tree.At(_p) if _p is not None else None

    def Has(self, key: str) -> bool:
        """key 가 트리 어딘가에 있는지."""
        return self.tree.Locate(key) is not None

    def Conflicts(self, other: "Bucket_Store") -> list[str]:
        """``other`` 를 들일 때 겹치는 key 목록 (범주 무관). 병합 전 질의용."""
        return [_k for _c, _k, _it in other.Iter() if self.Has(_k)]

    # ── 순회 — 범주 정책(CATEGORIES; params 제외) ────────────────────────────────
    def Bucket(self, category: str) -> Mapping[str, Data_Ref]:
        """그 범주 branch 의 자식(``{key: item}``) 읽기 전용 뷰."""
        _b = self.tree.Get(category)
        return MappingProxyType(_b.info if _b is not None else {})

    def Iter(self, cats: Iterable[str] | None = None) -> Iterator[tuple[str, str, Data_Ref]]:
        """전 범주(``cats`` 주면 그것만) 항목을 ``(category, key, item)`` 로 순회 (params 제외)."""
        for _c in (self.CATEGORIES if cats is None else cats):
            _b = self.tree.Get(_c)
            if _b is not None:
                for _k, _it in _b.Items():
                    yield _c, _k, _it

    # ── 영속 — 재귀 key-path (경로 = 트리 위치) ──────────────────────────────────
    @classmethod
    def Restore(cls, root: str | Path) -> "Bucket_Store":
        """``{root}/.meta`` 트리를 walk 해 복원 — 경로 key 시퀀스가 곧 트리 위치."""
        from .handler import Structure
        _store = cls(root=str(root))
        for _keys, _d in Structure.Walk(str(root)):
            _parent = _store.tree.At(_keys[:-1])
            if _parent is not None:
                _parent.Push(_keys[-1], Data_Ref(**_d))
        return _store

    def Save(self, key: str | None = None) -> None:
        """구조를 사이드카로 흩는다 — ``key`` 면 그 item 하나, 아니면 전 최상위 branch (params 포함)."""
        from .handler import Structure
        if key is None:
            for _top, _b in list(self.tree.Items()):
                for _stem, _item in list(_b.Items()):
                    Structure.Write(self.root, (_top, _stem), _item.Serialize())
            return
        _p = self.tree.Locate(key)
        if _p is not None:
            Structure.Write(self.root, _p, self.tree.At(_p).Serialize())

    def Export(self, categories: list[str] | None = None,
               out_file: str = "bundle.json") -> str:
        """선택 범주(기본 전체) 서브트리를 params 와 함께 한 파일로 serialize (경로 반환)."""
        _tops = (self.PARAMS, *(self.CATEGORIES if categories is None else categories))
        _d = {_t: {_k: _it.Serialize() for _k, _it in _b.Items()}
              for _t in _tops if (_b := self.tree.Get(_t)) is not None}
        _out = Path(self.root) / out_file
        Write_to(_out, _d)
        return str(_out)

    # ── 전이 — 범주 key 사이 pop→push (payload 도 재귀로 함께 이동) ────────────────
    def _relocate(self, item: Data_Ref, src: tuple[str, ...], dst: tuple[str, ...]) -> None:
        """item 의 payload leaf 들을 ``src`` prefix → ``dst`` prefix 로 옮기고 옛 사이드카를 지운다."""
        from . import handler
        from .handler import Structure
        for _lp, _name, _leaf in item.Iter_leaves():
            handler.Move(self.root, src + _lp, self.root, dst + _lp, _name, _leaf)
        Structure.Delete(self.root, src)

    def Move(self, key: str, to_category: str) -> None:
        """항목을 다른 범주로 — pop→push + payload/사이드카를 새 범주 경로로 이동."""
        _p = self.tree.Locate(key)
        if _p is None:
            raise KeyError(f"이동할 항목이 없음: {key}")
        _item = self.tree.At(_p[:-1]).Pop(key)
        if _p[0] != to_category:
            self._relocate(_item, _p, (to_category,) + _p[1:])
        self.tree.Get(to_category).Push(key, _item)
        self.Save(key)

    def Delete(self, key: str) -> None:
        """항목을 완전히 제거 — payload·사이드카·tree (없으면 no-op)."""
        from . import handler
        from .handler import Structure
        _p = self.tree.Locate(key)
        if _p is None:
            return
        _item = self.tree.At(_p[:-1]).Pop(key)
        for _lp, _name, _leaf in _item.Iter_leaves():
            handler.Delete(self.root, _p + _lp, _name, _leaf)
        Structure.Delete(self.root, _p)

    def Merge(self, other: "Bucket_Store", *, mode: str = SKIP) -> None:
        """다른 store 를 항목 단위로 들인다 (같은 타입끼리만). 충돌은 ``mode`` (skip/overwrite/merge).

        overwrite/merge 는 내용이 바뀌므로 ``DEFAULT_CATEGORY`` 로 되돌린다. 들이는 노드는 ``Clone``.
        """
        from . import handler
        if type(self) is not type(other):
            raise TypeError(f"병합은 같은 타입끼리만: {type(self).__name__} ← {type(other).__name__}")
        if mode not in MERGE_MODES:
            raise ValueError(f"알 수 없는 mode {mode!r} ({' / '.join(MERGE_MODES)})")

        for _src_cat, _key, _item in other.Iter():
            _exists = self.Has(_key)
            if _exists and mode == SKIP:
                continue

            if not _exists:                                       # 신규 → other 범주 그대로
                _dst_cat = _src_cat
                _new = _item.Clone()
                _leaves = _new.Iter_leaves()
                self.tree.Get(_dst_cat).Push(_key, _new)
            elif mode == OVERWRITE:                               # 통째 교체 → 진입 범주
                self.Delete(_key)
                _dst_cat = self.DEFAULT_CATEGORY
                _new = _item.Clone()
                _leaves = _new.Iter_leaves()
                self.tree.Get(_dst_cat).Push(_key, _new)
            else:                                                 # merge — host 에 없는 것만 → 진입 범주
                _dst_cat = self.DEFAULT_CATEGORY
                _p = self.tree.Locate(_key)
                _new = self.tree.At(_p[:-1]).Pop(_key)
                if _p[0] != _dst_cat:                             # 기존 payload 를 진입 범주로 이동
                    self._relocate(_new, _p, (_dst_cat,) + _p[1:])
                _leaves = _new.Merge_from(_item)                  # 삽입분만
                self.tree.Get(_dst_cat).Push(_key, _new)

            for _lp, _n, _lf in _leaves:                          # payload: other → self
                handler.Copy(other.root, (_src_cat, _key) + _lp,
                             self.root, (_dst_cat, _key) + _lp, _n, _lf)
            self.Save(_key)

        _po, _ps = other.tree.Get(other.PARAMS), self.tree.Get(self.PARAMS)   # params
        for _name, _ref in list(_po.Items()):
            if not _ps.Has(_name) or mode == OVERWRITE:
                handler.Copy(other.root, (other.PARAMS,), self.root, (self.PARAMS,), _name, _ref)
                _ps.Push(_name, _ref.Clone())
        self.Save()
