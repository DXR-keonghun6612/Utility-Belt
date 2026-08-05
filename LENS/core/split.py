"""정본(staged)을 비율대로 갈라 폴더별로 내보낸다 — **binder 계층** (배정 정책 + 내보내기 조율).

`Sampler`(파생 학습셋 빌드)가 하던 일 중 실제로 쓰이던 것만 남긴 것이다: 검수 끝난 프레임을 몫으로
갈라 학습 레이아웃으로 낸다. 중간 store(`sample/{tasker}`)를 짓지 않는다 — 배정은 **인자**일 뿐이라
[`store/split.py`](store/split.py) 의 껍데기에 담아 [`export/`](export) 에 바로 먹인다.

## 배정 — 해시로 세우고 잘라 쓴다

`salt + stem` 의 md5 로 **순서를 세우고**, 그 순서를 비율 누적 지점에서 **자른다**. 그래서:

- **재현된다** — 같은 (salt, stem 집합)이면 언제나 같은 결과다. salt 를 바꾸면 다시 섞인다.
- **비율이 정확하다** — 개수로 자르므로 요청한 비율이 표본 수만큼 정확히 맞는다.
- **대신 stem 집합이 바뀌면 배정도 바뀐다.** 프레임 100장을 더 검수하고 다시 돌리면 기존 프레임의 몫도
  달라질 수 있다. 옛 `Sample_stage` 는 해시를 **임계와 비교**해 이 성질을 피했지만(데이터가 늘어도
  기존 배정 불변) 그 대가로 비율이 근사였다. 여기서는 **일회성 내보내기**라 정확한 비율을 택했다 —
  이어붙여 학습하는 흐름이 생기면 그때 임계 방식이 필요하다.

## 공평 배분(stratified) — 무엇을 기준으로 세나

켜면 **class 마다 따로 세우고 따로 자른다**. 그래서 표본이 적은 class 도 각 몫에 비율대로 들어간다
(안 켜면 희귀 class 가 통째로 한 몫에 몰릴 수 있다).

기준 class 는 프레임 하나에 하나여야 하는데 정본은 **객체마다** class 를 든다. **0번 객체의 class**
를 쓴다 — 순회 축이 그것(``obj_index=0`` = 중심 최근접)이라 프레임의 대표가 곧 0번이다.

한때 ``① 프레임 attr → ② 객체 최빈값`` 순으로 봤는데, 프레임 attr 을 든 정본에서는 ①에서 끝나
객체와 무관한 값이 기준이 됐다(실측 600 프레임 전부 0번 객체와 달랐다). **프레임이 여러 class 를
섞어 들면 0번 하나로 접히므로** 공평 배분은 "대표 class 기준"이지 class별 개수의 완전한 균형이 아니다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from .constant import STAGED, UNCLASSIFIED_ID
from .store import Dataset_Meta, Split_Set


def Normalize(ratios: dict[str, float]) -> dict[str, float]:
    """비율을 합=1 로 정규화한다 (합이 0 이하면 균등).

    Raises:
        ValueError: 몫이 하나도 없거나 음수 비율이 있을 때 — 조용히 0 으로 깎지 않는다.
    """
    if not ratios:
        raise ValueError("몫이 없다 — 이름과 비율을 하나 이상 지정하라")
    if any(_v < 0 for _v in ratios.values()):
        raise ValueError(f"음수 비율: {[_k for _k, _v in ratios.items() if _v < 0]}")
    _total = sum(ratios.values())
    if _total <= 0:
        return {_k: 1.0 / len(ratios) for _k in ratios}
    return {_k: _v / _total for _k, _v in ratios.items()}


def _rank(stems: list[str], salt: str) -> list[str]:
    """``salt + stem`` 해시 순 — 재현되는 셔플."""
    return sorted(stems, key=lambda _s: hashlib.md5(f"{salt}{_s}".encode()).hexdigest())


def _cut(stems: list[str], ratios: dict[str, float], salt: str) -> dict[str, list[str]]:
    """해시 순으로 세운 뒤 비율 누적 지점에서 자른다 — **마지막 몫이 나머지를 전부** 받는다(반올림 잔여)."""
    _order = _rank(stems, salt)
    _names = list(ratios)
    _out: dict[str, list[str]] = {}
    _at, _acc = 0, 0.0
    for _i, _name in enumerate(_names):
        _acc += ratios[_name]
        _end = len(_order) if _i == len(_names) - 1 else round(len(_order) * _acc)
        _out[_name] = _order[_at:_end]
        _at = _end
    return _out


def Assign(items: list[tuple[str, str]], ratios: dict[str, float], *,
           salt: str = "", stratified: bool = False) -> dict[str, list[str]]:
    """``[(stem, 기준 class)]`` → ``{몫 이름: [stem…]}`` (모듈 docstring 이 규칙을 소유).

    Args:
        items:      배정 대상 — 기준 class 는 ``stratified`` 일 때만 쓰인다.
        ratios:     ``{몫 이름: 비율}`` — 순서가 자르는 순서다. 합은 알아서 정규화한다.
        salt:       해시 salt — 같은 데이터를 다르게 나누되 재현 가능하게.
        stratified: class 마다 따로 자를지 (공평 배분).

    Returns:
        모든 몫 이름을 키로 가진 dict — 대상이 없는 몫도 **빈 목록으로 남는다**.
    """
    _norm = Normalize(ratios)
    _groups: dict[str, list[str]] = {}
    for _stem, _cls in items:
        _groups.setdefault(_cls if stratified else "", []).append(_stem)

    _out: dict[str, list[str]] = {_k: [] for _k in _norm}
    for _key in sorted(_groups):                       # 그룹 순서도 결정적으로 (dict 삽입순 의존 제거)
        for _name, _stems in _cut(_groups[_key], _norm, salt).items():
            _out[_name].extend(_stems)
    return {_k: sorted(_v) for _k, _v in _out.items()}


def Class_of(item) -> str:
    """프레임 하나의 **기준 class** — **0번 객체**의 ``class_id`` (없으면 미분류).

    프레임 자신의 ``class_id`` attr 은 안 본다 — 객체와 따로 노는 값이라 기준으로 쓰면 공평 배분이
    내용과 무관해진다(모듈 docstring 참고).
    """
    _objs = list(item.Branches().values())
    _c = _objs[0].Attr("class_id") if _objs else None
    return str(_c) if _c not in (None, "") else str(UNCLASSIFIED_ID)


def Run_split(meta: Dataset_Meta, dest: str | Path, ratios: dict[str, float], *,
              salt: str = "", stratified: bool = False,
              task: str = "segmentation", format: str | None = "coco",
              id_map: dict[str, dict] | None = None, min_count: int = 0,
              progress: Callable[[str, int, int], None] | None = None) -> Path:
    """검수 끝난(`staged`) 프레임을 몫으로 갈라 ``dest`` 아래에 내보낸다 (원본 비파괴).

    레이아웃은 내보내기가 정한다 — ``{dest}/{몫}/images/…`` + ``instances_{몫}.json``(coco).
    몫 이름이 곧 폴더 이름이라 ``train``/``val`` 같은 관례에 매이지 않는다.

    Args:
        meta:       정본 store — 배정 대상(`staged`)이자 픽셀·객체의 출처.
        dest:       산출물 루트.
        ratios:     ``{몫 이름: 비율}``.
        salt:       해시 salt.
        stratified: class별 공평 배분.
        task:       데이터 성격 (``detection``/``segmentation`` — 후자는 객체 mask 필요).
        format:     직렬화 레이아웃 (기본 ``coco``).
        id_map:     class 표 — 없으면 데이터에 나온 번호로 짓는다.
        min_count:  이만큼 안 나온 class 의 **주석을 안 적는다** (0 = 끄기). id_map 은 안 건드린다.
        progress:   진행 콜백 ``(label, i, total)``.

    Raises:
        ValueError: staged 가 비었거나 비율이 잘못됐을 때 (빈 산출물을 조용히 내지 않는다).
    """
    from .export import Run_export
    # **정본 안으로는 못 낸다.** ``{dest}/params/`` 가 정본의 그 자리와 겹쳐 파일을 자기 자신에게
    # 복사하고(`SameFileError`), 운 나쁘면 정본 params 를 산출물로 덮는다. 내보내기는 비파괴다.
    _dest, _root = Path(dest).resolve(), Path(meta.root).resolve()
    if _dest == _root or _root in _dest.parents or _dest in _root.parents:
        raise ValueError(
            f"내보낼 곳이 정본과 겹친다 — 정본 '{_root}' · 대상 '{_dest}'. "
            f"정본 밖의 빈 폴더를 고른다 (내보내기는 원본을 안 건드린다)")
    _bucket = meta.Bucket(STAGED)
    if not _bucket:
        raise ValueError("staged 항목이 없다 — 검수 완료된 프레임이 있어야 나눌 수 있다")

    _items: list[tuple[str, str]] = []
    for _i, (_stem, _item) in enumerate(_bucket.items(), 1):
        _items.append((_stem, Class_of(_item) if stratified else ""))
        if progress is not None:
            progress("몫 배정", _i, len(_bucket))

    _assign = Assign(_items, ratios, salt=salt, stratified=stratified)
    if progress is not None:                 # 내보내기 자체는 진행을 안 알린다 — 유휴 표시로 둔다
        progress(f"내보내는 중 ({' · '.join(f'{_k} {len(_v)}' for _k, _v in _assign.items())})", 0, 0)
    return Run_export(Split_Set.Of(_assign), dest, task=task, format=format,
                      meta=meta, id_map=id_map, min_count=min_count)
