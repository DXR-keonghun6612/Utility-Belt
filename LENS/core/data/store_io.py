"""``Bucket_Store`` 디스크 I/O — 데이터모델이 I/O 를 모르게 하는 자유함수 층.

[`schema.py`](schema.py)의 ``Bucket_Store`` 는 ``handler`` 를 import 하지 않는다(그래야 cv2 없이 선다).
그 대가로 영속·전이는 **store 를 인자로 받는 자유함수**가 지고, 내부 dict(``buckets``/``params``)를
직접 다루는 **친구 모듈**이 된다 — ``Bucket()`` 읽기 전용 뷰는 바깥 소비자용이지 여기 것이 아니다.

공개 표면은 다섯 갈래뿐이다:

- **읽기** ``Restore`` — 디렉터리 → store (범주별 stem 사이드카를 전부 읽음).
- **쓰기** ``Save`` — ``key`` 있으면 그 stem 사이드카 하나(증분), 없으면 params + 전 항목.
- **stem 배치** ``Move``/``Delete`` — 버킷 이동 / 완전 제거 (payload+사이드카+버킷을 함께).
- **병합** ``Merge`` — 다른 store 를 들인다 (충돌 질의는 ``Bucket_Store.Conflicts``, 디스크 무관).
- **내보내기** ``Gather`` — 선택 범주를 자기완결 번들 한 파일로.

**트리 연산은 여기 없다.** 순회(``schema.Iter_leaves``)·깊은 사본(``Data_Ref.Clone``)·병합
(``schema.Merge_into``)은 디스크를 모르는 데이터모델의 일이다. 여기가 하는 건 그 결과를 **주소로
해석**하는 것뿐이다 — ``_payload`` 하나가 ``path[-1] → obj_id`` 를 알고, 나머지는 버킷 장부다.

leaf payload 는 ``handler.<Move|Copy|Delete>``(``ref.type`` 디스패치), 구조 사이드카는
``Structure``(``.meta/{stem}.json``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from python_toolbox.file import Write_to

from . import handler
from .handler import Structure
from .schema import Bucket_Store, Data_Ref, Iter_leaves, Merge_into

_S = TypeVar("_S", bound=Bucket_Store)


# ── payload I/O — 트리 순회는 schema 가, 주소 해석만 여기가 ──────────────────────
def _payload(leaves: Iterable[tuple[tuple[str, ...], str, Data_Ref]],
             stem: str, fn: Callable[..., Any], *roots: str) -> None:
    """``leaves`` 각각에 handler 연산 ``fn`` 을 건다 (``fn`` 은 함수 **값** — 이름 문자열이 아니다).

    ``schema.Iter_leaves`` 가 내는 ``path`` 를 핸들러의 ``obj_id`` 로 해석하는 **유일한 자리**다:
    payload 파일은 ``{root}/{dir}/{stem}[_{obj_id}].{fmt}`` 에 살고, ``obj_id`` 는 그 leaf 를 감싼
    가장 안쪽 stem 의 key(= ``path[-1]``)다. 인라인 leaf(attr/rle)는 핸들러가 no-op 한다.

    Args:
        leaves: ``(path, name, ref)`` 들 — 전량(``Iter_leaves``)이든 삽입분(``Merge_into``)이든.
        stem: 최상위 항목 key (파일명 앞부분).
        fn: ``handler.Move`` / ``handler.Copy`` / ``handler.Delete``.
        roots: ``fn`` 이 받는 root 들 — Move/Copy 는 ``(src, dst)``, Delete 는 ``(root,)``.
    """
    for _path, _name, _ref in leaves:
        fn(*roots, stem, _name, _ref, obj_id=_path[-1] if _path else None)


# ── 영속 (top = params; 범주-항목 사이드카; 전부 Structure 위임) ──────────────────
def Restore(cls: type[_S], root: str | Path) -> _S:
    """디렉터리에서 store 를 복원한다 — top(params) + 범주별 항목 사이드카 (경로·읽기는 ``Structure`` 소유).

    **디스크에서 들어오는 불변식 위반을 막는 문**이다. 같은 stem 사이드카가 두 범주 디렉터리에 있으면
    (``Move`` 도중 크래시하면 그렇게 된다) 조용히 둘 다 올리지 않고 실패한다 — 그대로 두면
    ``Category_of`` 가 선언 순서로 하나를 고르고 ``Delete`` 는 하나만 지운다.

    Raises:
        KeyError: 한 stem 이 둘 이상의 범주 디렉터리에 사이드카를 가질 때.
    """
    _top = Structure.Read(str(root), cls.TOP_STEM) or {}
    _store = cls(root=str(root), params=_top.get("params", {}))
    _seen: dict[str, str] = {}
    for _cat in cls.CATEGORIES:
        _croot = _store.Category_root(_cat)
        for _stem in Structure.Stems(_croot):
            _d = Structure.Read(_croot, _stem)
            if _d is None:
                continue
            if _stem in _seen:
                raise KeyError(
                    f"{cls.__name__}: stem '{_stem}' 사이드카가 '{_seen[_stem]}' 와 '{_cat}' 양쪽에 있다 "
                    f"(한 stem = 한 범주). 전이 중 중단된 흔적 — 한쪽을 지우고 다시 여십시오: {root}")
            _seen[_stem] = _cat
            _store.buckets[_cat][_stem] = Data_Ref(**_d)
    return _store


def _save_params(store: Bucket_Store) -> None:
    """params(root leaf)만 top 사이드카로 — 항목 사이드카는 건드리지 않는다 (O(1))."""
    Structure.Write(store.root, store.TOP_STEM,
                    {"params": {_k: _v.Serialize() for _k, _v in store.params.items()}})


def Save(store: Bucket_Store, key: str | None = None) -> None:
    """구조를 사이드카로 흩는다 — ``key`` 를 주면 **그 항목 하나만**, 안 주면 params + 전 항목.

    항목 하나 저장이 first-class 라 20k+ 프레임에서 한 stem 편집이 한 파일 write 로 끝난다("하나
    바뀌었다고 전체 내보내기" 없음). 전량 저장은 그 반복 + params 이므로 별도 연산이 아니다.

    payload(이미지·배열) 파일은 여기서 안 쓴다 — 생산 시점에 ``handler.Route`` 가 이미 썼다.
    ``key`` 가 어느 범주에도 없으면 no-op.
    """
    if key is None:
        _save_params(store)
        for _cat, _k, _item in store.Iter_all():
            Structure.Write(store.Category_root(_cat), _k, _item.Serialize())
        return
    _cat = store.Category_of(key)
    if _cat is not None:
        Structure.Write(store.Category_root(_cat), key, store.buckets[_cat][key].Serialize())


def Gather(store: Bucket_Store, categories: list[str] | None = None,
           out_file: str = "bundle.json") -> str:
    """선택 범주(기본 전체)를 한 파일로 뭉친 자기완결 번들을 ``{root}/{out_file}`` 에 쓴다. 경로 반환."""
    _cats = list(store.CATEGORIES) if categories is None else categories
    _d = {
        "params": {_k: _v.Serialize() for _k, _v in store.params.items()},
        **{_c: {_k: _i.Serialize() for _k, _i in store.buckets[_c].items()} for _c in _cats},
    }
    _p = Path(store.root) / out_file
    Write_to(_p, _d)
    return str(_p)


# ── 전이 (_transit[payload] + Structure[구조] + 버킷 조정) ─────────────────────────
def Move(store: Bucket_Store, key: str, to_category: str) -> None:
    """항목을 ``to_category`` 버킷으로 옮긴다 — payload 파일·구조 사이드카·버킷 (같은 범주 no-op).

    버킷 간 **복제는 없다** — 한 key 는 정확히 한 버킷에 산다(``Bucket_Store`` 불변식). 그래서 전이는
    이 하나뿐이다.
    """
    _src = store.Category_of(key)
    if _src is None:
        raise KeyError(f"이동할 항목이 없음: {key}")
    if _src == to_category:
        return
    _src_root, _dst_root = store.Category_root(_src), store.Category_root(to_category)
    _item = store.buckets[_src][key]
    _payload(Iter_leaves(_item), key, handler.Move, _src_root, _dst_root)   # payload 파일
    store.buckets[to_category][key] = store.buckets[_src].pop(key)          # 버킷
    Structure.Move(_src_root, _dst_root, key)                               # 구조 사이드카


def Delete(store: Bucket_Store, key: str) -> None:
    """항목을 완전히 제거한다 — payload 파일·구조 사이드카·버킷 (없으면 no-op)."""
    _cat = store.Category_of(key)
    if _cat is None:
        return
    _root = store.Category_root(_cat)
    _payload(Iter_leaves(store.buckets[_cat][key]), key, handler.Delete, _root)   # payload
    Structure.Delete(_root, key)                                                  # 사이드카
    store.buckets[_cat].pop(key, None)                                            # 버킷


SKIP, OVERWRITE, MERGE = "skip", "overwrite", "merge"
MERGE_MODES = (SKIP, OVERWRITE, MERGE)


def Merge(store: _S, other: _S, *, mode: str = SKIP) -> None:
    """다른 store 를 들인다 — 항목 단위(key)로, 충돌은 ``mode`` 가 정한다.

    **같은 타입끼리만 병합한다** — 타입이 트리 모양 보장이라, 모양이 다른 store(예: classification 대
    detection 학습셋)를 key 단위로 섞으면 무의미하다.

    새 항목은 ``other`` 의 범주 그대로 들어온다. 이미 있는 항목은 ``mode`` 로 갈린다:

    - ``skip``      — 손대지 않는다. host 의 범주·내용 모두 유지.
    - ``overwrite`` — host 것을 지우고 ``other`` 것으로 통째 교체.
    - ``merge``     — 항목 **내부**를 재귀 병합한다(host 에 없는 leaf/객체만 들임; host 값이 이긴다).

    ``overwrite``/``merge`` 는 내용을 바꾸므로 그 항목을 **``DEFAULT_CATEGORY`` 로 되돌린다** — 검수는
    내용에 대한 것이라, 내용이 달라지면 "검수 완료" 표시를 유지할 수 없다. ``skip`` 만 상태를 보존한다.

    들이는 항목·params 는 전부 ``_clone`` 을 거치므로 병합 뒤 두 store 가 노드를 공유하지 않는다
    (``other`` 를 재사용해도 안전). 항목마다 즉시 사이드카를 흩는다(증분·크래시 내구성).

    Raises:
        TypeError: ``store`` 와 ``other`` 의 타입이 다를 때.
        ValueError: ``mode`` 가 :data:`MERGE_MODES` 밖일 때.
    """
    if type(store) is not type(other):
        raise TypeError(f"병합은 같은 타입끼리만: {type(store).__name__} ← {type(other).__name__}")
    if mode not in MERGE_MODES:
        raise ValueError(f"알 수 없는 mode {mode!r} ({' / '.join(MERGE_MODES)})")

    for _cat, _key, _item in other.Iter_all():
        _host_cat = store.Category_of(_key)
        if _host_cat is not None and mode == SKIP:            # 충돌 → host 유지 (상태·내용)
            continue

        if _host_cat is None:                                 # 신규 → other 의 범주로
            _dst_cat = _cat
        else:                                                 # 내용이 바뀐다 → 진입 범주로 되돌림
            _dst_cat = store.DEFAULT_CATEGORY
            if mode == OVERWRITE:
                Delete(store, _key)                           # payload·사이드카·버킷 회수
            elif _host_cat != _dst_cat:
                Move(store, _key, _dst_cat)                   # merge — 재검수 대상으로 이동

        _src_root, _dst_root = other.Category_root(_cat), store.Category_root(_dst_cat)
        _cur = store.buckets[_dst_cat].get(_key)
        if _cur is None:                                      # 신규 / overwrite 후 → 통째
            store.buckets[_dst_cat][_key] = _item.Clone()
            _leaves = Iter_leaves(store.buckets[_dst_cat][_key])
        else:                                                 # merge — host 에 없는 것만
            _leaves = Merge_into(_cur, _item)
        _payload(_leaves, _key, handler.Copy, _src_root, _dst_root)   # 들어온 leaf 만 복사
        Structure.Write(_dst_root, _key, store.buckets[_dst_cat][_key].Serialize())

    for _name, _ref in other.params.items():                  # params (root leaf)
        if _name not in store.params or mode == OVERWRITE:
            handler.Copy(other.root, store.root, None, _name, _ref)
            store.params[_name] = _ref.Clone()
    _save_params(store)
