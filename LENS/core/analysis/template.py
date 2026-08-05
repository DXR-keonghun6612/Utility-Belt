"""템플릿 — **묶음 하나의 대표 프로파일.** 정렬된 벡터들의 θ별 중앙값.

정본이 표본마다 ``radial_rle`` ``(NT, K)`` 을 들고(``process/stream/mask/profile.py``), 그것들은 이미
같은 좌표에 정렬돼 있다(무게중심·주축각 정준화). 접으면 표본 하나가 ``(NT,)`` 벡터 하나가 되므로,
묶음은 ``(N, NT)`` 행렬이고 **템플릿은 그 열별 중앙값**이다. 그것이 이 모듈의 전부다.

## 여기가 ``.analysis`` 인 이유

표본 **하나**의 측정값은 정본이 든다(편집과 함께 움직여야 하므로). 표본을 **묶은** 것은 여기다 —
묶음이 바뀌면 다시 서는 값이라 정본에 적을 자리가 없다. class 를 하나 옮기면 그 class 의 템플릿과
옮겨간 곳의 템플릿이 **둘 다** 달라지는데, 그때 정본 사이드카 수만 개를 다시 쓸 수는 없다.
``Type_stats`` 가 같은 자리의 선례다.

## 평균이 아니라 중앙값

평균은 오라벨 한 건에 끌려간다 — 다른 부품이 섞이면 그쪽으로 경계가 밀린다. 중앙값은 절반이 넘게
틀려야 움직인다. 실측(합성 40건, 다른 부품 섞기): 오염 35% 에서도 중앙값 이동 0.7px.

## 슬롯이 아니라 접어서 쌓는다

``(NT, K)`` 원본은 밴드가 하나 늘면 슬롯이 통째로 밀린다 — 광선이 구멍을 스칠 때 값이 계단으로 뛰므로
그 좌표에서 중앙값을 내면 서로 다른 뜻의 슬롯이 섞인다. 접은 뒤에는 ``(NT,)`` px 반경이라 θ마다 같은
뜻의 값이 모인다. 채널 둘의 쓸모가 다르다 — ``outline`` 은 실루엣(정합의 자), ``signed`` 는 구멍
총량까지(속이 다른가).
"""

from __future__ import annotations

import numpy as np

from ..constant import TO_STORAGE
from .extract import Fold

#: 템플릿이 드는 채널 — ``RADIAL_FOLDS`` 의 접기 이름. 순서가 곧 배열의 마지막 축이다.
CHANNELS = ("outline", "signed")

_NPZ = {"to": TO_STORAGE, "type": "arrays", "format": "npz"}
#: params leaf 이름 앞머리 — ``/`` 를 쓰면 사이드카가 한 겹 깊어져 ``Restore`` 가 거부한다.
_PREFIX = "template"


def Folded(rle: np.ndarray) -> np.ndarray:
    """``radial_rle`` ``(NT, K)`` (또는 배치 ``(N, NT, K)``) → 채널 ``(…, NT, C)``.

    접는 식은 ``torch_toolbox`` 의 ``RADIAL_FOLDS`` 가 소유한다 (:func:`extract.Fold`) — 여기서 다시
    적으면 템플릿이 쓰는 좌표와 가르기가 쓰는 좌표가 갈린다.
    """
    _a = np.asarray(rle, np.float32)
    return np.stack([Fold((_c,), _a, batched=_a.ndim == 3) for _c in CHANNELS], -1)


def Build(rows: np.ndarray) -> np.ndarray | None:
    """정렬된 표본들 → 템플릿 ``(NT, C)``. 쓸 표본이 없으면 None.

    Args:
        rows: ``(N, NT, K)`` 원본 또는 ``(N, NT, C)`` 접힌 값. NaN 행(mask 없는 객체)은 빠진다.

    Returns:
        θ별 채널 중앙값 ``(NT, C)`` — 채널 순서는 :data:`CHANNELS`. 살아있는 행이 없으면 None.
    """
    _a = np.asarray(rows, np.float64)
    if _a.ndim != 3:
        raise ValueError(f"(N, NT, ·) 이어야 한다 (받은 것: {_a.shape})")
    if _a.shape[-1] != len(CHANNELS):
        _a = Folded(_a).astype(np.float64)
    _live = _a[~np.isnan(_a).all(axis=(1, 2))]              # mask 없던 자리를 뺀다
    return np.nanmedian(_live, axis=0) if len(_live) else None


def Channel(template: np.ndarray, name: str) -> np.ndarray:
    """채널 하나 ``(NT,)``.

    Raises:
        KeyError: 이 템플릿이 안 든 채널.
    """
    if name not in CHANNELS:
        raise KeyError(f"모르는 채널 '{name}' (있는 것: {', '.join(CHANNELS)})")
    return np.asarray(template)[:, CHANNELS.index(name)]


# ── 영속 — 묶음 축마다 한 장 ─────────────────────────────────────────────────────
def Name(axis: str, group: str) -> str:
    """params leaf 이름 — ``template__class__241`` 처럼 **축과 묶음 id 를 담는다**.

    축을 이름에 넣는 이유는 같은 번호가 축마다 다른 것을 가리키기 때문이다(class 3 과 type 3 은 무관).
    """
    return f"{_PREFIX}__{axis}__{group}"


def Save(bucket, axis: str, group: str, template: np.ndarray, count: int) -> None:
    """템플릿 하나를 npz 로 쓴다 (``.analysis`` params).

    Args:
        bucket: ``Cluster_Bucket``.
        axis: 묶음 축 — ``class`` | ``type`` | 종합 축 이름.
        group: 그 축 안의 묶음 id (class_id · type 번호).
        template: ``(NT, C)`` 중앙값.
        count: 그것을 만든 표본 수 — **몇으로 낸 중앙값인지 모르면 믿을 만한지도 모른다**.
    """
    bucket.Put_param(Name(axis, group), dict(_NPZ),
                     {"median": np.asarray(template, np.float32),
                      "count":  np.asarray([int(count)], np.int32)})


def Load(bucket, axis: str, group: str) -> tuple[np.ndarray, int] | None:
    """그 묶음의 ``(템플릿, 표본 수)`` (없으면 None)."""
    _raw = bucket.Param(Name(axis, group))
    if not _raw or "median" not in _raw:
        return None
    return np.asarray(_raw["median"], np.float64), int(np.asarray(_raw["count"]).ravel()[0])
