"""``Bucket_Store`` 디스크 I/O — 영속(흩기/모으기) + 전이(이동/복사/삭제/병합).

[`schema.py`](schema.py)의 ``Bucket_Store``(데이터모델: ``params``/``buckets``/``CATEGORIES`` + 순회)와
분리된 **오케스트레이션 층**이다 — ``store`` 를 인자로 받아 구조 사이드카(``Structure``)·payload(``handler``)
I/O 를 엮는다. store 의 공개 순회/범주 API(``Iter_all``/``Bucket``/``Category_root``/``Category_of``)와
내부 dict(``buckets``/``params``)를 직접 다루는 **친구 모듈**. payload 트리 전이 헬퍼(``_transit``/
``_merge_ref``)도 여기 소유한다(전이가 유일 소비자).

인스턴스 메서드가 아니라 **자유함수**(``store_io.Move(store, …)``) — 데이터모델 클래스가 I/O 를 아예
모른다. 호출측(``Pipeline``·GUI·학습 코드)이 이 모듈을 직접 부른다. leaf payload 는 ``handler.<op>``
(ref.type 디스패치), 구조 사이드카는 ``Structure``(``.meta/{stem}.json``, 항목 단위). ``op`` 는 언제나
handler 함수명 키워드(Move/Copy/Delete) — 센티널 없음.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from python_toolbox.file import Write_to

from . import handler
from .handler import Data_Ref, Structure
from .schema import Bucket_Store

_S = TypeVar("_S", bound=Bucket_Store)


# ── payload 트리 헬퍼 (stateless — type 으로 leaf/stem 을 가름) ────────────────────
def _transit(ref: Data_Ref, *roots: str,
             op: str, stem: str, obj_id: str | None = None) -> None:
    """컨테이너 ``ref`` 아래 leaf payload 파일을 재귀 전이한다 — ``op`` = handler 함수명(Move/Copy/Delete).

    leaf entry 는 현재 ``obj_id`` 로 ``getattr(handler, op)`` 디스패치, stem entry 는 ``obj_id`` = 그
    stem 의 key 로 파고든다(중첩 stem 자체는 파일이 없어 사이드카는 항목 단위로 store 가 따로 씀).
    """
    for _name, _entry in ref.info.items():
        if _entry.type == "stem":
            _transit(_entry, *roots, op=op, stem=stem, obj_id=_name)
        else:
            getattr(handler, op)(*roots, stem, _name, _entry, obj_id=obj_id)


def _merge_ref(dst: Data_Ref, src: Data_Ref, *roots: str,
               op: str | None = None, override: bool = False) -> None:
    """컨테이너 ``src`` 를 ``dst`` 에 재귀 병합 — 겹치는 stem 은 파고들고, 없으면 통째 삽입.

    stem entry 는 재귀/삽입, leaf entry 는 직접 dispatch. ``op=None`` 이면 in-memory 만(파일 전이 없음).
    항목 내부 깊은 병합의 payload 경로 정밀도는 ``_transit`` 의 stem 인자 수준.
    """
    for _name, _entry in src.info.items():
        _cur = dst.info.get(_name)
        if _entry.type == "stem":                                 # 하위 컨테이너
            if isinstance(_cur, Data_Ref) and _cur.type == "stem" and not override:
                _merge_ref(_cur, _entry,
                           *(str(Path(_r) / _name) for _r in roots),
                           op=op, override=override)
                continue
            if isinstance(_cur, Data_Ref) and op is not None:     # override → 기존 payload 제거
                _transit(_cur, *roots, op="Delete", stem=_name)
            if op is not None:
                _transit(_entry, *roots, op=op, stem=_name)
            dst.info[_name] = _entry
        elif _name not in dst.info or override:                   # leaf
            if op is not None:
                getattr(handler, op)(*roots, None, _name, _entry, obj_id=None)
            dst.info[_name] = _entry


# ── 영속 (top = params; 범주-항목 사이드카; 전부 Structure 위임) ──────────────────
def Restore(cls: type[_S], root: str | Path) -> _S:
    """디렉터리에서 store 를 복원한다 — top(params) + 범주별 항목 사이드카 (경로·읽기는 ``Structure`` 소유)."""
    _top = Structure.Read(str(root), cls.TOP_STEM) or {}
    _store = cls(root=str(root), params=_top.get("params", {}))
    for _cat in cls.CATEGORIES:
        _croot = _store.Category_root(_cat)
        for _stem in Structure.Stems(_croot):
            _d = Structure.Read(_croot, _stem)
            if _d is not None:
                _store.buckets[_cat][_stem] = Data_Ref(**_d)
    return _store


def Save_top(store: Bucket_Store) -> None:
    """params(root leaf)만 top 사이드카로 기록한다 (params 만 바뀔 때 O(1))."""
    Structure.Write(store.root, store.TOP_STEM,
                    {"params": {_k: _v.Serialize() for _k, _v in store.params.items()}})


def Scatter(store: Bucket_Store) -> None:
    """forest 전체를 흩는다 — top(params) + 모든 범주 항목 구조 사이드카."""
    Save_top(store)
    for _cat, _key, _item in store.Iter_all():
        Structure.Write(store.Category_root(_cat), _key, _item.Serialize())


def Save_item(store: Bucket_Store, key: str) -> None:
    """항목 하나의 구조 사이드카만 기록한다 (편집 즉시 저장 — 증분; 없으면 no-op)."""
    _cat = store.Category_of(key)
    if _cat is not None:
        Structure.Write(store.Category_root(_cat), key, store.buckets[_cat][key].Serialize())


def Drop(store: Bucket_Store, category: str, key: str) -> None:
    """항목 구조 사이드카를 지운다 (전이·삭제로 버킷에서 빠질 때 — 메모리는 안 건드림)."""
    Structure.Delete(store.Category_root(category), key)


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
def _transfer(store: Bucket_Store, key: str, to_category: str, *,
              keep: bool, verb: str) -> None:
    """항목을 ``to_category`` 로 옮기거나(``keep=False``) 복제(``keep=True``)한다 — 공유 전이 골격.

    전반부(항목 찾기·no-op 체크·roots·payload ``_transit``)는 동일하고 후반부만 갈린다: **Move**(``keep``
    False)는 원본 버킷에서 회수(``pop``)하고 사이드카를 이동(``Structure.Move``), **Copy**(``keep`` True)는
    원본을 보존한 채 aliasing 없는 깊은 사본(``Serialize`` 왕복)을 대상에 새로 쓴다. 같은 범주면 no-op.
    """
    _src = store.Category_of(key)
    if _src is None:
        raise KeyError(f"{verb}할 항목이 없음: {key}")
    if _src == to_category:
        return
    _src_root, _dst_root = store.Category_root(_src), store.Category_root(to_category)
    _item = store.buckets[_src][key]
    _transit(_item, _src_root, _dst_root, op="Copy" if keep else "Move", stem=key)  # payload 파일
    if keep:                                                      # Copy — 원본 보존
        _clone = Data_Ref(**_item.Serialize())                   # 깊은 사본 (트리 aliasing 방지)
        store.buckets[to_category][key] = _clone
        Structure.Write(_dst_root, key, _clone.Serialize())      # 구조 사이드카 write
    else:                                                        # Move — 원본 회수
        store.buckets[to_category][key] = store.buckets[_src].pop(key)
        Structure.Move(_src_root, _dst_root, key)                # 구조 사이드카 이동


def Move(store: Bucket_Store, key: str, to_category: str) -> None:
    """항목을 ``to_category`` 버킷으로 옮긴다 — payload 파일·구조 사이드카·버킷 (같은 범주 no-op)."""
    _transfer(store, key, to_category, keep=False, verb="이동")


def Copy(store: Bucket_Store, key: str, to_category: str) -> None:
    """항목을 ``to_category`` 버킷으로 **복제**한다 — 원본(현재 범주)은 유지 (``Move`` 의 비파괴 짝, 같은 범주 no-op)."""
    _transfer(store, key, to_category, keep=True, verb="복사")


def Delete(store: Bucket_Store, key: str) -> None:
    """항목을 완전히 제거한다 — payload 파일·구조 사이드카·버킷 (없으면 no-op)."""
    _cat = store.Category_of(key)
    if _cat is None:
        return
    _transit(store.buckets[_cat][key], store.Category_root(_cat), op="Delete", stem=key)
    Drop(store, _cat, key)
    store.buckets[_cat].pop(key, None)


def Merge_conflicts(store: Bucket_Store, other: Bucket_Store) -> list[str]:
    """병합 전 충돌(범주 무관 key 중복) 목록 (GUI 질의용)."""
    return [_k for _, _k, _ in other.Iter_all() if store.Category_of(_k) is not None]


def Merge(store: Bucket_Store, other: Bucket_Store, *, override: bool = False) -> None:
    """다른 store 를 들인다 — **같은 CATEGORIES** 가정, 범주별로 항목(범주 직속)을 병합·즉시 흩기.

    겹치는 항목은 ``_merge_ref`` 로 항목 **내부**를 재귀 병합, 새 항목이면 payload 복사(``_transit`` Copy)
    후 통째 삽입 — 어느 쪽이든 그 항목만 구조 사이드카로 흩기(증분·크래시 내구성). 충돌은 ``override`` 가
    정한다(먼저 ``Merge_conflicts`` 질의 권장).
    """
    for _cat in store.CATEGORIES:
        if _cat not in other.buckets:
            continue
        _src, _dst_root = other.Category_root(_cat), store.Category_root(_cat)
        _bucket = store.buckets[_cat]
        for _key, _item in other.buckets[_cat].items():
            _host_cat = store.Category_of(_key)
            if _host_cat is not None and _host_cat != _cat:  # 다른 범주에 존재 (한 stem=한 범주)
                if not override:
                    continue                                 # 충돌 → host 배치 유지
                Delete(store, _key)                          # override → 옛 범주에서 회수
            _cur = _bucket.get(_key)
            if _cur is not None and not override:            # 같은 범주 겹침 → 항목 내부 재귀 병합
                _merge_ref(_cur, _item, _src, _dst_root, op="Copy", override=override)
            else:
                if _cur is not None:                         # override → 기존 payload 제거
                    _transit(_cur, _dst_root, op="Delete", stem=_key)
                _transit(_item, _src, _dst_root, op="Copy", stem=_key)   # payload 복사
                _bucket[_key] = _item
            Structure.Write(_dst_root, _key, _bucket[_key].Serialize())  # 이 항목 즉시 흩기
    for _name, _ref in other.params.items():                 # params (root leaf)
        if _name not in store.params or override:
            handler.Copy(other.root, store.root, None, _name, _ref)
            store.params[_name] = _ref
    Save_top(store)
