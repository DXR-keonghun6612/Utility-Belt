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

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Iterable, Iterator, Mapping

from python_toolbox.data_schema import Data_Schema

from .. import port
from ..constant import TRACE_DIR
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

    # ── 트리 임의 위치의 노드 더하기/지우기 (라이프사이클) ─────────────────────────
    def Add_leaf(self, path: tuple[str, ...], name: str, spec: dict, value: Any) -> Data_Ref:
        """``path`` 컨테이너에 LEAF 를 새로 만든다 — payload 저장 + 노드 등록 (새 ref 반환).

        빈 mask 를 만들어 그리기 시작하는 자리다 — 없던 종류를 **새로 낳는다**. 경로는 트리 위치에서
        파생되므로 호출 측은 파일이 어디 앉는지 몰라도 된다.

        Raises:
            KeyError: ``path`` 에 컨테이너가 없을 때.
        """
        _parent = self.tree.At(path)
        if _parent is None or not _parent.Is_branch():
            raise KeyError(f"컨테이너가 없음: {'/'.join(path)}")
        _ref = self.Route(path, name, spec, value)
        _parent.Push(name, _ref)
        return _ref

    def Add_branch(self, path: tuple[str, ...], name: str | None = None) -> str:
        """``path`` 컨테이너에 빈 BRANCH(객체)를 더한다 — 이름을 안 주면 **다음 순번** (반환).

        객체 id 는 부모 ``info`` 의 key 다(별도 필드가 아니다). 빈 자리를 찾아 채운다.

        **id 는 정수만 된다.** 객체는 라벨맵의 한 라벨(= id + 1)로 사는데, 정수가 아니면 앉을 자리가
        없다. 여기서 막아 그 사례를 없애므로, 소비처(``Remove_object``·``Merge_objects``·gui 의 조준)는
        ``int(obj_id) + 1`` 을 **방어 없이** 쓴다.

        Raises:
            ValueError: ``name`` 이 정수 문자열이 아닐 때.
        """
        _parent = self.tree.At(path)
        if _parent is None or not _parent.Is_branch():
            raise KeyError(f"컨테이너가 없음: {'/'.join(path)}")
        if name is None:
            _i = 0
            while str(_i) in _parent.info:
                _i += 1
            name = str(_i)
        elif not name.isdigit():
            raise ValueError(f"객체 id 는 정수여야 한다 (라벨 = id + 1): {name!r}")
        _parent.Push(name, Data_Ref(info={}))
        return name

    def Delete_node(self, path: tuple[str, ...], name: str) -> None:
        """``path`` 아래 노드 하나를 지운다 — LEAF 든 BRANCH 든 **payload 파일까지** (없으면 no-op).

        사이드카는 여기서 안 지운다 — item 단위라 ``Save(key)`` 가 통째로 다시 쓴다(그게 저장 입도다).
        item 자체를 지우는 건 ``Delete``, params 는 ``Delete_param``.
        """
        _parent = self.tree.At(path)
        if _parent is None:
            return
        _ref = _parent.Pop(name)
        if _ref is None:
            return
        if _ref.Is_branch():                                   # 객체 — 그 안의 payload 를 전부
            for _lp, _n, _leaf in _ref.Iter_leaves():
                port.Delete(self.root, path + (name,) + _lp, _n, _leaf)
        else:
            port.Delete(self.root, path, name, _ref)           # 인라인이면 no-op

    def Import_param(self, name: str, src: str | Path, *, type: str) -> Data_Ref:
        """dataset-wide **파일 하나**를 params 로 들인다 — payload 복사 + leaf 등록 (갱신된 ref 반환).

        ``Import`` 의 단건 판이다 — 그쪽은 stem 축이 있는 raw 를 훑고, 이건 축이 없는 파일 하나다.
        호출 측은 파일이 어디로 복사되는지 몰라도 된다(경로는 트리 위치에서 파생).

        Args:
            name: params key (= 종류. 저장 폴더도 이 이름이다).
            src: 들일 파일 경로.
            type: 핸들러 (image/segmap/array/docs …) — **추론하지 않는다**.
        """
        _ref = port.Save(self.root, (self.PARAMS,), name,
                         port.Template_for_file({"pattern": str(src), "type": type}), Path(src))
        self.Set_param(name, _ref)
        return _ref

    def Delete_param(self, name: str) -> None:
        """params leaf 하나를 제거한다 — payload · **사이드카** · 트리 (없으면 no-op).

        사이드카를 같이 지우는 게 핵심이다 — 안 지우면 다음 ``Restore`` 가 그 파일을 읽어 **지운 항목을
        되살린다**(트리에선 사라졌는데 디스크엔 남아 있으니). 삭제의 입도는 저장의 입도와 같아야 한다.
        """
        _ref = self.tree.Get(self.PARAMS).Pop(name)
        if _ref is None:
            return
        port.Delete(self.root, (self.PARAMS,), name, _ref)       # payload (인라인이면 no-op)
        Structure.Delete(self.root, (self.PARAMS, name))         # 사이드카

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

    def Category_of(self, key: str) -> str | None:
        """이 item 이 **어느 범주에 있나** (없으면 None).

        범주가 곧 트리 위치라 이 물음의 답은 store 만 안다 — 호출 측(GUI 의 상태 뱃지 등)이 스스로
        버킷을 뒤지지 않게 하는 자리다.
        """
        _p = self._item_path(key)
        return _p[0] if _p is not None else None

    def Item_path(self, key: str) -> tuple[str, str] | None:
        """item 의 트리 경로 ``(범주, key)`` — payload I/O 에 넘길 주소 (없으면 None)."""
        return self._item_path(key)

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

    def Trace(self, run: str, path: tuple[str, ...], name: str, spec: dict, value: Any,
              *, params: bool = False) -> None:
        """진단 payload 를 **트리 밖** ``{root}/.trace/{run}/{종류}/{stem}.{ext}`` 에 쓴다.

        ``Route`` 의 형제이되 **``Data_Ref`` 를 안 돌려준다** — 꽂을 ref 가 없으니 트리에 앉힐 수단이
        구조적으로 없다. 그래서 진단물은 사이드카에 안 실리고, 전이(``Move``)·삭제·병합·내보내기가
        아예 못 본다. 라이프사이클이 없는 것이 이 sink 의 정의다 (지우려면 폴더째 → ``Clear_trace``).

        범주가 경로에 없는 것도 같은 이유다 — 진단은 검수 상태를 따라 옮겨다니지 않는다. 대신 ``run``
        이 앞머리라 같은 종류를 여러 번 내도 실행끼리 안 덮어쓴다.

        Args:
            run:   실행 id (호출 측이 실행 단위로 정한다 — 한 Run = 한 폴더).
            path:  트리 위치에서 온 주소 꼬리 ``(stem[, obj_id])``. 비면 위치 없음(finalize).
            name:  leaf 이름 = 종류(폴더).
            spec:  라우팅 spec (``to: trace``).
            value: 저장할 값.
            params: 위치 없는 dataset-wide 출력인지 (핸들러 ``Claims`` 맥락).
        """
        port.Route(str(Path(self.root, TRACE_DIR)), (run, *path), name, spec, value,
                   params=params)

    def Clear_trace(self, run: str | None = None) -> None:
        """진단 산출물을 지운다 — ``run`` 이면 그 실행 폴더만, 아니면 ``.trace`` 통째 (없으면 no-op)."""
        _dir = Path(self.root, TRACE_DIR, run) if run else Path(self.root, TRACE_DIR)
        if _dir.exists():
            shutil.rmtree(_dir)

    def Load(self, key: str, name: str):
        """item 의 leaf 하나를 payload 로 푼다 (item·leaf 가 없으면 None).

        **범주를 호출 측이 몰라도 된다** — key 만 주면 store 가 자기 트리에서 자리를 찾아 경로를
        파생한다. ``Resolve``(직속 leaf 전부)의 단건 판이다.
        """
        _p = self._item_path(key)
        if _p is None:
            return None
        _ref = self.tree.Get(_p[0]).Get(_p[1]).Get(name)
        return None if _ref is None else port.Load(self.root, _p, name, _ref)

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

    def Vacuum(self) -> int:
        """트리가 참조하지 않는 payload 파일을 지운다 — **트리에서 떨어진 고아** 청소 (지운 파일 수 반환).

        ``Replace_branches``·객체 편집이 서술자를 갈아끼우면 옛 파일은 트리에서 떨어지지만 디스크엔
        남는다 — ``Move``/``Delete`` 는 ``Iter_leaves`` 로 트리를 따라가므로 이런 고아를 못 본다. 여기가
        그 유일한 청소구다: 살아있는 경로 집합을 만들고 범주·params 폴더 아래 그 밖의 파일을 지운다.

        **범주·``params`` 최상위만 훑는다** — ``.meta``(사이드카)·``.trace``(진단)·``sample``(파생)은
        payload 레이아웃이 아니라 건드리지 않는다. 비워진 종류 폴더는 함께 걷는다.
        """
        _live: set[Path] = set()
        for _cat, _key, _item in self._iter():
            for _lp, _name, _leaf in _item.Iter_leaves():
                _p = port.Path_of(self.root, (_cat, _key, *_lp), _name, _leaf)
                if _p is not None:                          # 인라인은 파일이 없다
                    _live.add(_p.resolve())
        for _name, _leaf in self.tree.Get(self.PARAMS).Leaves().items():
            _p = port.Path_of(self.root, (self.PARAMS,), _name, _leaf)
            if _p is not None:
                _live.add(_p.resolve())

        _removed = 0
        for _top in (self.PARAMS, *self.CATEGORIES):
            _root = Path(self.root, _top)
            if not _root.is_dir():
                continue
            for _f in _root.rglob("*"):
                if _f.is_file() and _f.resolve() not in _live:
                    _f.unlink()
                    _removed += 1
            for _d in sorted((_p for _p in _root.rglob("*") if _p.is_dir()),
                             key=lambda _x: len(_x.parts), reverse=True):
                if not any(_d.iterdir()):                    # 비워진 종류 폴더 걷기
                    _d.rmdir()
        return _removed

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
