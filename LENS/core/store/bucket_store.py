"""forest 파사드 ``Bucket_Store`` — 범주 = 트리 구조 key (nested) + 자기 영속·전이.

``tree`` 는 단일 ``Data_Ref``(BRANCH), 최상위 ``info`` 키 = ``{params, <범주들>}``. 순회·payload 경로는
``Data_Ref`` 재귀(``Iter_leaves``)에 위임하고, 여기는 범주 정책 + 영속 오케스트레이션만 든다.

**item = 범주 branch 의 직속 자식** — 그것만이 store 의 주소 단위다. key 단위 API(``Find``/``Has``/
``Save``/``Move``/``Delete``)는 정확히 그 자리에서만 찾는다. item 안쪽(객체·leaf)은 트리 내부 구조라
store 가 bare key 로 주소지정하지 않는다 — 그건 ``Data_Ref`` 몫이다. 사이드카 입도도 같은 자리라
**한 item = 한 사이드카**이고, 그래서 save/restore/delete 가 서로 어긋나지 않는다.

영속 경로는 트리 위치에서 파생 — 사이드카 ``{root}/.meta/{범주}/{key}.json``, payload 는 handler 가
kind-major 로(``{root}/{범주}/{종류}/{stem}.{ext}`` — 경로 규칙은 [`../port/README.md`](../port/README.md)).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Iterable, Iterator, Mapping

from python_toolbox.data_schema import Data_Schema

from .. import port
from ..port import Structure
from ..schema import Data_Ref

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

    # ── 조회 — item(범주 직속 자식)만 ────────────────────────────────────────────
    def _item_path(self, key: str) -> tuple[str, str] | None:
        """item 의 트리 경로 ``(범주, key)`` — 범주 직속에서만 찾는다 (없으면 None).

        item 안쪽(객체·leaf)은 안 본다 — 그 이름이 우연히 겹쳐도 item 으로 오인하지 않는다.
        """
        for _c in self.CATEGORIES:
            _b = self.tree.Get(_c)
            if _b is not None and _b.Has(key):
                return _c, key
        return None

    def Find(self, key: str) -> Data_Ref | None:
        """key 의 item (어느 범주에 있든; 없으면 None)."""
        _p = self._item_path(key)
        return self.tree.Get(_p[0]).Get(_p[1]) if _p is not None else None

    def Has(self, key: str) -> bool:
        """그 key 의 item 이 있는지."""
        return self._item_path(key) is not None

    def Conflicts(self, other: "Bucket_Store") -> list[str]:
        """``other`` 를 들일 때 겹치는 key 목록 (범주 무관). 병합 전 질의용."""
        return [_k for _c, _k, _it in other._iter() if self.Has(_k)]

    # ── 순회 — 범주 정책(CATEGORIES; params 제외) ────────────────────────────────
    def Bucket(self, category: str) -> Mapping[str, Data_Ref]:
        """그 범주 branch 의 자식(``{key: item}``) 읽기 전용 뷰."""
        _b = self.tree.Get(category)
        return MappingProxyType(_b.info if _b is not None else {})

    def _iter(self, cats: Iterable[str] | None = None) -> Iterator[tuple[str, str, Data_Ref]]:
        """전 범주(``cats`` 주면 그것만) 항목을 ``(category, key, item)`` 로 순회 (params 제외).

        **내부용** — 밖에서는 범주를 알고 ``Bucket(cat)`` 을 부른다("어느 범주냐"를 안 정한 채 전부를
        훑는 건 store 자신의 일뿐이다: ``Conflicts``·``Merge``).
        """
        for _c in (self.CATEGORIES if cats is None else cats):
            _b = self.tree.Get(_c)
            if _b is not None:
                for _k, _it in _b.Items():
                    yield _c, _k, _it

    # ── 읽기/쓰기 요청 창구 — 위 계층(process)이 port 를 직접 부르지 않게 ──────────
    # 계층 규정: 읽기/쓰기는 store 가 소유하고 process 는 **요청**한다. 그래서 store 가 port 를 아는
    # 유일한 자리고, process 는 파일 포맷·경로 파생을 아예 모른다.
    def Resolve(self, path: tuple[str, ...], node: Data_Ref) -> dict:
        """``node`` 의 **직속 LEAF** 를 payload 로 풀어 ``{이름: 값}`` 으로 (BRANCH 자식=객체는 안 판다).

        대상이 없으면(None) 건너뛴다 — 호출 측은 ``Data_Ref`` 가 아니라 ready-to-use 값만 본다.

        Args:
            path: 이 노드의 트리 key 경로 (예 ``(MODIFIED, stem)`` / ``(MODIFIED, stem, obj_id)``).
            node: 풀어낼 컨테이너 (프레임 / 객체 / params).
        """
        _out: dict = {}
        for _name, _ref in node.Leaves().items():
            _val = port.Load(self.root, path, _name, _ref)
            if _val is not None:
                _out[_name] = _val
        return _out

    def Route(self, path: tuple[str, ...], name: str, spec: dict, value: Any,
              *, params: bool = False) -> Data_Ref:
        """값을 spec 대로 저장하고 그 ``Data_Ref`` 서술자를 돌려준다 (호출 측이 트리에 꽂는다).

        **경로는 spec 이 안 정한다** — 트리 위치(``path``)와 leaf 이름에서 port 가 파생한다(kind-major).
        spec 의 ``level``(위치)은 호출 측이 이미 ``path`` 로 풀어 넘기므로, 여기 오는 건 담을 그릇을
        정하는 키(``to``/``type``/``format``)뿐이다.
        """
        return port.Route(self.root, path, name, spec, value, params=params)

    def Param(self, name: str):
        """``params`` 의 root leaf 하나를 payload 로 풀어 돌려준다 (없으면 None)."""
        _ref = self.tree.Get(self.PARAMS).Get(name)
        return None if _ref is None else port.Load(self.root, (self.PARAMS,), name, _ref)

    def Path_of(self, path: tuple[str, ...], name: str, ref: Data_Ref):
        """이 leaf 를 받치는 파일 경로 (인라인이면 None) — store 밖 레이아웃으로 내보낼 때."""
        return port.Path_of(self.root, path, name, ref)

    # ── 들이기 — 외부 raw → 트리 (Restore·Merge 의 형제) ─────────────────────────
    def Import(self, sources: list[str], globs: dict[str, Any],
               params: dict[str, Any] | None = None,
               progress: Callable[[str, int, int], None] | None = None) -> int:
        """외부 raw 를 발견해 payload 를 저장하고 진입 범주에 item 으로 등록한다.

        **발견은 port, 등록은 store.** ``port.Scan`` 이 "어떤 파일이 있나"만 답하고, "어느 범주에 어떻게
        넣나"는 여기가 정한다 — 그래서 store 는 glob 패턴을 모르고 port 는 범주를 모른다.

        같은 축의 형제들 — ``Restore``(자기 레이아웃) · ``Merge``(다른 store) · ``Import``(외부 raw).

        **이미 있는 stem 은 건드리지 않는다** — 범주도 내용도 그대로 둔다. ingest 는 raw 를 들이는 일이라
        이미 들인 것에 할 일이 없고, 재수집이 검수 이력(staged/skipped)을 덮어써서는 안 된다. 그래서 존재
        검사가 payload write **앞**에 온다(파일도 안 쓴다).

        Args:
            sources: 탐색할 raw 디렉터리들.
            globs: ``{종류: {pattern, type?, format?}}`` — key 가 곧 종류 폴더(kind-major).
            params: 범주 무관 dataset-wide 파일 ``{종류: {pattern, …}}`` (stem 축이 없다).
            progress: 진행 콜백 ``(label, i, total)``.

        Returns:
            **새로** 등록한 item 수 (이미 있던 건 안 센다).
        """
        _groups = port.Scan(sources, globs)
        _total, _added = len(_groups), 0
        for _i, (_stem, _files) in enumerate(_groups.items(), start=1):
            if not self.Has(_stem):                        # 이미 들인 stem → 범주·내용 보존
                _path = (self.DEFAULT_CATEGORY, _stem)
                _info = {_name: port.Save(self.root, _path, _name,
                                          port.Template_for_file(globs[_name]), _src)
                         for _name, _src in _files.items()}
                self.Set(_stem, Data_Ref(info=_info))
                _added += 1
            if progress is not None:
                progress("import", _i, _total)

        for _name, _spec in (params or {}).items():        # dataset-wide root leaf
            _src = Path(port.Pattern_of(_spec))
            if _src.exists():
                self.Set_param(_name, port.Save(
                    self.root, (self.PARAMS,), _name, port.Template_for_file(_spec), _src))
        return _added

    # ── 영속 — 사이드카 = item 하나 (경로 = 트리 위치) ────────────────────────────
    @classmethod
    def Restore(cls, root: str | Path) -> "Bucket_Store":
        """``{root}/.meta`` 트리를 walk 해 복원 — 경로 key 가 곧 트리 위치 ``(최상위, item)``.

        Raises:
            ValueError: 사이드카 경로가 ``{범주|params}/{key}.json`` 모양이 아닐 때 (모르는 최상위 key
                또는 깊이 불일치). 조용히 버리지 않는다 — 옛 레이아웃이면 마이그레이션이 필요하다.
        """
        _store = cls(root=str(root))
        _tops = (cls.PARAMS, *cls.CATEGORIES)
        for _keys, _d in Structure.Walk(str(root)):
            if len(_keys) != 2 or _keys[0] not in _tops:
                raise ValueError(
                    f"{cls.__name__}: 복원 불가한 사이드카 .meta/{'/'.join(_keys)}.json — "
                    f"{{최상위}}/{{item}}.json 이어야 한다 (최상위: {', '.join(_tops)}). "
                    f"옛 레이아웃이면 마이그레이션 필요.")
            _store.tree.Get(_keys[0]).Push(_keys[1], Data_Ref(**_d))
        return _store

    def Save(self, key: str | None = None) -> None:
        """구조를 사이드카로 흩는다 — ``key`` 면 그 item 하나, 아니면 전 item (params 포함).

        Raises:
            KeyError: ``key`` 가 item 이 아닐 때 (item 안쪽 노드는 store 의 저장 단위가 아니다).
        """
        if key is None:
            for _top, _b in list(self.tree.Items()):
                for _item_key, _item in list(_b.Items()):
                    Structure.Write(self.root, (_top, _item_key), _item.Serialize())
            return
        _p = self._item_path(key)
        if _p is None:
            raise KeyError(f"저장할 item 이 없음: {key}")
        Structure.Write(self.root, _p, self.tree.Get(_p[0]).Get(_p[1]).Serialize())

    # ── 전이 — 범주 key 사이 pop→push (payload 도 재귀로 함께 이동) ────────────────
    def _relocate(self, item: Data_Ref, src: tuple[str, ...], dst: tuple[str, ...]) -> None:
        """item 의 payload leaf 들을 ``src`` prefix → ``dst`` prefix 로 옮기고 옛 사이드카를 지운다."""
        for _lp, _name, _leaf in item.Iter_leaves():
            port.Move(self.root, src + _lp, self.root, dst + _lp, _name, _leaf)
        Structure.Delete(self.root, src)

    def Move(self, key: str, to_category: str) -> None:
        """item 을 다른 범주로 — pop→push + payload/사이드카를 새 범주 경로로 이동."""
        _p = self._item_path(key)
        if _p is None:
            raise KeyError(f"이동할 item 이 없음: {key}")
        _item = self.tree.Get(_p[0]).Pop(key)
        if _p[0] != to_category:
            self._relocate(_item, _p, (to_category, key))
        self.tree.Get(to_category).Push(key, _item)
        self.Save(key)

    def Delete(self, key: str) -> None:
        """item 을 완전히 제거 — payload·사이드카·tree (없으면 no-op)."""
        _p = self._item_path(key)
        if _p is None:
            return
        _item = self.tree.Get(_p[0]).Pop(key)
        for _lp, _name, _leaf in _item.Iter_leaves():
            port.Delete(self.root, _p + _lp, _name, _leaf)
        Structure.Delete(self.root, _p)

    def Merge(self, other: "Bucket_Store", *, mode: str = SKIP) -> None:
        """다른 store 를 항목 단위로 들인다 (같은 타입끼리만). 충돌은 ``mode`` (skip/overwrite/merge).

        overwrite/merge 는 내용이 바뀌므로 ``DEFAULT_CATEGORY`` 로 되돌린다. 들이는 노드는 ``Clone``.
        """
        if type(self) is not type(other):
            raise TypeError(f"병합은 같은 타입끼리만: {type(self).__name__} ← {type(other).__name__}")
        if mode not in MERGE_MODES:
            raise ValueError(f"알 수 없는 mode {mode!r} ({' / '.join(MERGE_MODES)})")

        for _src_cat, _key, _item in other._iter():
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
                _p = self._item_path(_key)
                _new = self.tree.Get(_p[0]).Pop(_key)
                if _p[0] != _dst_cat:                             # 기존 payload 를 진입 범주로 이동
                    self._relocate(_new, _p, (_dst_cat, _key))
                _leaves = _new.Merge_from(_item)                  # 삽입분만
                self.tree.Get(_dst_cat).Push(_key, _new)

            for _lp, _n, _lf in _leaves:                          # payload: other → self
                port.Copy(other.root, (_src_cat, _key) + _lp,
                             self.root, (_dst_cat, _key) + _lp, _n, _lf)
            self.Save(_key)

        _po, _ps = other.tree.Get(other.PARAMS), self.tree.Get(self.PARAMS)   # params
        for _name, _ref in list(_po.Items()):
            if not _ps.Has(_name) or mode == OVERWRITE:
                port.Copy(other.root, (other.PARAMS,), self.root, (self.PARAMS,), _name, _ref)
                _ps.Push(_name, _ref.Clone())
        self.Save()
