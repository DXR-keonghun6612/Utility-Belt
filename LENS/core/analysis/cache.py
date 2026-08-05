"""캐시 — 정본에 흩어진 표본 벡터를 **묶음별 npz 한 장**으로 모아 둔다.

정본은 표본 하나의 값을 stem 배열에 든다(``process/stream/mask/profile.py``). 묶기는 그것을 **전부**
필요로 하는데, 6만 표본을 stem 수만큼 파일을 열어 모으면 적재가 초 단위로 늘어난다. 그래서 묶음마다
한 장으로 모아 둔다 — 연속 읽기 한 번이면 그 묶음이 통째로 실린다.

**소유는 정본이고 여기는 사본이다.** 언제든 지우고 다시 모을 수 있으며, 정본과 어긋나면 정본이 이긴다.
``.analysis`` 의 다른 산출물과 같은 성질이다(설정이 바뀌면 계약이 바뀌고, 계약이 바뀌면 다시 뽑는다).

## 묶음 축은 있는 것을 쓴다

- **class** — 정본이 이미 아는 값이라 묶기 **전에** 쓸 수 있다. 첫 적재가 이 축이다.
- **type** — 묶기가 낸 배정이라 그 **뒤에** 선다. 재군집·템플릿이 이 축을 읽는다.

축이 이름에 들어가는 이유는 같은 번호가 축마다 다른 것을 가리키기 때문이다(class 3 과 type 3 은 무관).

## npz 한 장이 드는 것

``rows`` ``(N, …)`` 와 그 행이 누구인지 말하는 ``keys`` ``(N,)`` 다. **행 번호만으로는 표본을 못
가리킨다** — 편집으로 obj_id 가 재부여되므로 순서가 정체가 아니다. 그래서 주소 문자열을 함께 든다
(``Cluster_Bucket.Key``).
"""

from __future__ import annotations

import numpy as np

from ..constant import TO_STORAGE

_NPZ = {"to": TO_STORAGE, "type": "arrays", "format": "npz"}
#: params leaf 이름 앞머리 — ``/`` 를 쓰면 사이드카가 한 겹 깊어져 ``Restore`` 가 거부한다.
_PREFIX = "cache"

#: 묶음 축 — 정본이 아는 것 / 묶기가 낸 것.
CLASS = "class"
TYPE  = "type"


def Name(axis: str, group: str) -> str:
    """params leaf 이름 — ``cache__class__241``."""
    return f"{_PREFIX}__{axis}__{group}"


def Save(bucket, axis: str, group: str, keys: list[str], rows: np.ndarray) -> None:
    """묶음 하나의 표본들을 npz 한 장으로 쓴다.

    Args:
        bucket: ``Cluster_Bucket``.
        axis: 묶음 축 (:data:`CLASS` | :data:`TYPE`).
        group: 그 축 안의 묶음 id.
        keys: 행마다 그 표본의 주소 문자열 — **행 번호는 정체가 아니다**(편집으로 obj_id 가 바뀐다).
        rows: ``(N, …)`` 표본 벡터들. ``len(keys)`` 와 행 수가 같아야 한다.

    Raises:
        ValueError: 행 수와 ``keys`` 길이가 다를 때 (어긋난 채 저장하면 다음에 읽는 쪽이 잘못된
            표본을 가리킨다 — 조용히 자르지 않는다).
    """
    _r = np.asarray(rows)
    if len(keys) != len(_r):
        raise ValueError(f"keys {len(keys)}개 ≠ rows {len(_r)}행 — 행이 누구인지 어긋난다")
    bucket.Put_param(Name(axis, group), dict(_NPZ),
                     {"keys": np.asarray(list(keys), dtype=np.str_), "rows": _r})


def Load(bucket, axis: str, group: str) -> tuple[list[str], np.ndarray] | None:
    """그 묶음의 ``(keys, rows)`` (없으면 None)."""
    _raw = bucket.Param(Name(axis, group))
    if not _raw or "rows" not in _raw:
        return None
    return [str(_k) for _k in np.asarray(_raw["keys"]).ravel()], np.asarray(_raw["rows"])


def Drop(bucket, axis: str, group: str) -> None:
    """그 묶음의 캐시를 걷는다 (없으면 no-op) — 사본이라 언제든 버릴 수 있다."""
    try:
        bucket.Delete_param(Name(axis, group))
    except KeyError:
        pass


def Groups(bucket, axis: str) -> list[str]:
    """이 축에 캐시가 있는 묶음 id 들 (정렬)."""
    _head = f"{_PREFIX}__{axis}__"
    return sorted(_n[len(_head):] for _n in bucket.Params() if _n.startswith(_head))


def Iter_rows(bucket, axis: str, groups: dict[str, list[str]], progress=None,
              label: str = "적재"):
    """묶음마다 npz 를 **한 번 열어** ``(키들, 행들)`` 을 흘린다.

    표본마다 사이드카를 여는 것과 갈리는 자리다 — 6만 표본이면 그쪽은 파일 열기가 6만 번이고,
    여기는 묶음 수(수백)만큼이다. 그래서 순회의 단위가 표본이 아니라 **묶음**이다.

    Args:
        bucket: ``Cluster_Bucket``.
        axis: 묶음 축 (:data:`CLASS` | :data:`TYPE`).
        groups: ``{묶음 id: 그 안에서 쓸 키들}``. 키 순서가 결과 순서를 정한다.
        progress: ``(라벨, 한 것, 전체)`` 콜백.
        label: 진행 라벨.

    Yields:
        ``(쓴 키들, ``(m, …)`` 행들)`` — 캐시에 없는 키는 **빠진다**(배열만 짧아지면 배정이 엉뚱한
        표본에 붙으므로 키를 함께 낸다).
    """
    _total = sum(len(_v) for _v in groups.values())
    _done = 0
    for _g, _want in groups.items():
        _got = Load(bucket, axis, _g)
        _done += len(_want)
        if progress is not None:
            progress(label, min(_done, _total), _total)
        if _got is None:
            continue
        _keys, _rows = _got
        _at = {_k: _i for _i, _k in enumerate(_keys)}
        _idx = [_at[_k] for _k in _want if _k in _at]
        if _idx:
            yield [_keys[_i] for _i in _idx], _rows[_idx]


def Collect(store, addresses, leaf: str, key_of) -> tuple[list[str], np.ndarray] | None:
    """정본에서 표본 벡터를 모은다 — **stem 배열 한 장을 한 번만 읽는다**.

    같은 stem 의 객체들이 한 배열에 살므로(행 = obj_id), 주소를 stem 으로 묶어 파일을 재사용한다.
    6만 표본을 주소마다 열면 그 자체가 적재보다 비싸진다.

    Args:
        store: 정본 ``Dataset_Meta``.
        addresses: ``(stem, obj_index)`` 목록.
        leaf: 읽을 stem leaf 이름 (``radial_rle``).
        key_of: ``(stem, obj_index) -> 주소 문자열`` (``Cluster_Bucket.Key``).

    Returns:
        ``(keys, rows)`` — 배열이 없거나 그 행이 NaN 인 표본은 **빠진다**(mask 가 없던 객체).
        하나도 못 모으면 None.
    """
    _by_stem: dict[str, list[tuple[int, str]]] = {}
    for _addr in addresses:
        _stem, _idx = _addr[0], int(_addr[1])
        _by_stem.setdefault(_stem, []).append((_idx, key_of(_addr)))

    _keys: list[str] = []
    _rows: list[np.ndarray] = []
    for _stem, _items in _by_stem.items():
        _arr = store.Load(_stem, leaf)
        if _arr is None:
            continue
        _a = np.asarray(_arr)
        for _idx, _key in _items:
            if _idx >= len(_a) or np.isnan(_a[_idx]).all():   # 없는 행·mask 없던 객체
                continue
            _keys.append(_key)
            _rows.append(_a[_idx])
    return (_keys, np.stack(_rows)) if _rows else None
