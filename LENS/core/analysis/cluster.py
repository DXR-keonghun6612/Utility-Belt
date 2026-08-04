"""가르기와 묻기 — **순수 함수**. store 도 트리도 모르고, 값을 받아 값을 낸다.

한 번에 **도메인 하나**를 다룬다. 도메인은 서로 직교라 한 좌표로 합칠 일이 없다 — 옛
``axis_of``/``axis_weights`` 가 여러 도메인을 이어 붙이며 가중을 정하던 자리는 통째로 사라졌다.
표본 하나는 도메인 수만큼의 type id 를 갖고, 그것들을 **좌표로 본 점**이 종합 판정이다(:func:`join`).

가르는 단위도 class 가 아니다. 옛 ``split_class`` 는 class 하나만 보고 그 안에서 갈랐는데, 묻고
싶은 것이 "class 정의가 맞나" 였으므로 class 를 전제로 class 를 검증하는 순환이었다. 여기서는
**표본이 그냥 들어오고** type 이 데이터에서 나온다. class 는 obj 에 붙은 정보일 뿐이라 이 파일에
한 번도 나오지 않는다.

## 구(球)를 버렸다 — 이웃 그래프다

``k`` 안에 든 것을 중심에 붙이던 방식은 **class 를 구로 감쌀 수 있다**고 전제하는데, 실측에서
그 전제가 깨졌다. class 안쪽 퍼짐 r95 는 중앙 0.139 인데 최대 1.043 이고 가장 가까운 남까지는
중앙 0.178 · 최소 0.013 이라, ``r95 < 가장가까운남`` 인 class 가 **39% 뿐**이다 — 90% class 를
담는 ``k`` 구간이 아예 **비어 있다**. 그래서 ``k`` 를 올리면 순도가 무너지고 내리면 안 붙는다
(표본 10,000 · class 134)::

    구       k=0.08  배정 88.2%  순도 76.4%  최대 type   560
             k=0.30  배정 99.5%  순도 37.6%  최대 type 5,609   ← 하나가 절반을 먹는다
    이웃그래프 k=0.08  배정 79.5%  순도 88.0%  최대 type   396
             k=0.15  배정 85.5%  순도 87.8%  최대 type   396   ← k 를 두 배로 해도 안 흔들린다

feature 는 멀쩡했다 — 1-NN 이 같은 class 인 비율이 87.6% 라 **국소 정보는 충분한데 모델이 안
맞았다**. 88% 는 이 데이터의 천장이다(1-NN 과 같은 값). 남은 12% 는 묶기 실패가 아니라 class
라벨을 의심할 자리고, 이 도구가 원래 찾던 것이 그것이다.

지금 규칙은 둘뿐이다::

    간선   서로가 서로의 이웃 목록에 있고 거리 ≤ k   (**상호** 최근접)
    type   그 간선으로 이어진 연결 성분 (min_members 미만은 대기 풀)

상호성이 사슬을 끊는다 — 촘촘한 덩어리 옆에 붙은 표본은 자기 쪽에서만 이웃이라 간선이 안 생긴다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Annotated

import numpy as np

from ..typing import Arg_Info as UI

#: 대기 풀에 남은 표본 — 아직 어느 type 에도 안 붙었다.
POOL = -1

#: **종합 판정**의 자리 이름 — 축이 아니라 축들의 곱집합(:func:`join`)이다.
#:
#: 도메인과 같은 서랍(``index.types`` · ``Composition`` · ``Keys``)을 쓰므로 화면이 축 하나처럼
#: 다룰 수 있다. 대신 **좌표가 없다** — 중심·퍼짐·3D 배치는 축에서만 정의된다. 잣대 이름으로
#: 쓰일 수 없게 :class:`~.extract.Mask_Geometry` 가 막는다.
JOINT = "joint"


@dataclass
class Cluster_Params:
    """묶기 파라미터 — **필드가 곧 GUI 폼**이다(`gui/form` 이 introspect 한다)."""

    threshold: Annotated[float, UI(
        label="이웃 거리 상한 (σ)",
        tip="이보다 먼 쌍은 **간선을 안 만든다**. 단위는 **표준편차** — 도메인 정규화 상수 위의 "
            "상수라 도메인이 몇 개든 같은 뜻이다.\n"
            "구 방식과 달리 여기서는 이 값이 type 의 **크기**가 아니라 **이을지 말지**만 정한다. "
            "그래서 민감하지 않다 — 실측 0.08 ↔ 0.15 에서 순도가 88.0% ↔ 87.8% 로 거의 같다"
            "(구 방식은 76.4% → 60.2% 로 무너졌다).\n"
            "바닥은 **노이즈 하한**이다(같은 물체가 흔들렸을 때 값이 움직이는 거리)",
        min=0.01, max=2.0, step=0.01)] = 0.1

    neighbors: Annotated[int, UI(
        label="이웃 수",
        tip="표본마다 몇 번째 이웃까지 볼지. **서로가 서로의 목록에 있어야** 간선이 생긴다 — 그 "
            "상호성이 사슬을 끊는다(촘촘한 덩어리 옆에 붙은 표본은 자기 쪽에서만 이웃이다).\n"
            "키우면 잘 이어져 배정률이 오르고 잘게 부서지지 않는 대신, 다른 class 로 새는 간선도 "
            "함께 는다",
        min=1, max=50)] = 5

    #: **도메인별 승격 문턱** ``{도메인: n}`` — 없는 도메인은 위 공통값. ``thresholds`` 와 같은 자리.
    #:
    #: 이것까지 도메인별인 이유는 **서명 때문**이다. 전역으로 두면 값 하나를 만졌을 때 전 게이지의
    #: 서명이 바뀌어 다 다시 돈다 — 실제로 바뀐 건 하나인데.
    min_member_counts: dict[str, int] = field(default_factory=dict)

    min_members: Annotated[int, UI(
        label="type 승격 최소 표본",
        tip="이만큼 안 모인 연결 성분은 type 이 아니라 **대기 풀**로 간다.\n"
            "1 로 두면 표본 하나가 곧 type 이라 고립 표본이 전부 type 이 된다(옛 구현이 그래서 "
            "type 13,577 중 10,007 이 1개짜리였다)",
        min=1, max=50)] = 3

    impute_bound: Annotated[float, UI(
        label="종합 — 기권 메우기 한계 (σ)",
        tip="한 축이 기권한 표본을 **다른 축을 참고해** 그 축의 type 에 붙인다 — 다른 축이 후보를 "
            "좁히고, 자기 축 중심까지의 거리가 그중 하나를 고른다.\n"
            "이 값보다 멀면 안 붙이고 기권으로 남긴다(**진짜 고립**이라 보류로 읽혀야 한다).\n"
            "0 으로 두면 메우기를 끈다. 실측(k=0.08) 0.3 에서 1건짜리 종합 type 이 85 → 10 으로 "
            "줄고 순도는 88.4% 그대로다 — 풀어 버리면(∞) 4까지 줄지만 순도가 88.1% 로 빠진다.\n"
            "**축 화면은 안 바뀐다** — 메운 값은 종합 전용이다",
        min=0.0, max=3.0, step=0.05)] = 0.3

    weld_types: Annotated[bool, UI(
        label="종합 — 자의적 경계 병합",
        tip="종합에서 **모든 축이 같거나 이웃**인 조합끼리 붙인다. 한 축이라도 멀면 안 붙는다 — "
            "그 축이 실제로 가른 자리다.\n"
            "축이 쪼갠 것을 되돌리는 게 아니다 — 두 type 이 서로 이웃이면 그 사이 선은 데이터가 그은 "
            "게 아니라 연결이 한 번 끊긴 자리다.\n"
            "실측: 종합 type 1,585 → 832 · 순도 88.5% → 88.1% · 1건짜리 53 → 22.\n"
            "끄면 조합이 곧 type 이다(더 잘게 쪼개진다)")] = True

    max_axis_types: Annotated[int, UI(
        label="type 축 경고 상한",
        tip="화면이 type 끼리 거리를 재려면 **자리 수의 제곱**짜리 행렬이 든다(5,000 → 200 MB · "
            "65,000 → 33 GB). 이 수를 넘으면 그리지 않고 경고한다",
        min=500, max=30000)] = 5000

    #: **도메인별 거리 상한** ``{도메인: k}`` — 없는 도메인은 위 공통값을 쓴다. 폼이 아니라
    #: 목록에서 고친다(고를 목록이 dataclass 가 아니라 **추출기 계약**에 달렸다 —
    #: `Extract_Spec.Domains()`).
    #:
    #: 도메인마다 값이 달라야 하는 이유는 같은 흔들림에도 도메인이 반응하는 크기가 다르기
    #: 때문이다 — 마스크를 1° 돌리면 ``radial_rle`` 은 반경 프로파일이 통째로 밀리지만 ``area``
    #: 는 거의 안 변한다.
    thresholds: dict[str, float] = field(default_factory=dict)

    #: **도메인별 이웃 수** ``{도메인: m}`` — 없는 도메인은 위 공통값. 자리는 ``thresholds`` 와 같다.
    #:
    #: 무차원이라 축척은 안 타지만 **밀도**를 탄다. 도메인마다 표본이 몰린 정도가 달라(``area``
    #: 는 2채널이라 값이 겹치고 ``radial_outline`` 은 512채널이라 흩어진다) 같은 이웃 수가 같은
    #: 뜻이 되지 않는다.
    neighbor_counts: dict[str, int] = field(default_factory=dict)


def threshold_of(params: dict, domain: str | None = None) -> float:
    """그 도메인에 실제로 적용될 **거리 상한** ``k`` — 표준화 공간의 상수. 환산이 없다.

    한때 이 값을 px 로 받아 ``norm`` 의 std 로 환산했다. 그 환산이 정의되지 않는다는 게 실측으로
    드러났다 — 도메인마다 단위가 달라(``area`` px² std 14948 · ``moment`` 무차원 std 0.025) std 들의
    RMS 는 가장 큰 도메인이 지배한다. 비교는 애초에 :func:`equalize` 가 만든 표준화 좌표에서만
    일어나므로 임계도 거기서 살면 된다.

    Args:
        params: :class:`Cluster_Params` 를 dict 로 편 것.
        domain: 도메인 이름. ``params["thresholds"]`` 에 있으면 그것이 이긴다.

    Returns:
        거리 상한 ``k``.
    """
    _per = params.get("thresholds") or {}
    if domain is not None and str(domain) in _per:
        return float(_per[str(domain)])
    return float(params.get("threshold", 0.1))


def neighbors_of(params: dict, domain: str | None = None) -> int:
    """그 도메인에 적용될 **이웃 수** — :func:`threshold_of` 와 같은 규칙(개별이 공통을 이긴다)."""
    _per = params.get("neighbor_counts") or {}
    if domain is not None and str(domain) in _per:
        return max(int(_per[str(domain)]), 1)
    return max(int(params.get("neighbors", 5)), 1)


def members_of(params: dict, domain: str | None = None) -> int:
    """그 도메인의 **승격 문턱** — :func:`threshold_of` 와 같은 규칙(개별이 공통을 이긴다)."""
    _per = params.get("min_member_counts") or {}
    if domain is not None and str(domain) in _per:
        return max(int(_per[str(domain)]), 1)
    return max(int(params.get("min_members", 3)), 1)


def gauge_params(params: dict, domain: str) -> dict:
    """그 도메인의 **묶기 입력 전부** — 서명이 해싱하는 것이 곧 이것이다.

    한자리에 모아 두는 이유: 손잡이를 더할 때 여기만 고치면 서명이 따라온다. 흩어 두면 새 값이
    서명에 안 들어가 **설정을 바꿔도 안 다시 도는** 자리가 생긴다(실제로 그렇게 어긋났다).
    """
    return {"threshold": threshold_of(params, domain),
            "neighbors": neighbors_of(params, domain),
            "min_members": members_of(params, domain)}


# ── 도메인 축 — 정규화 상수와 그 위의 좌표 ─────────────────────────────────────
def equalize(arr: np.ndarray, norm_d: dict | None) -> np.ndarray:
    """도메인 **배치** → 표준화 좌표 ``(n, dim)``: ``(x - mean)/std`` 후 ``1/√dim``.

    ``√dim`` 으로 나누므로 거리²가 **채널당 평균 표준화 편차²** 가 된다 — 거리 1 = "채널마다
    평균 1σ 차이". 그래서 채널 수가 다른 도메인끼리도 ``k`` 가 같은 뜻으로 읽힌다(값은 달라도
    좋지만 뜻이 같아야 견줄 수 있다).

    **첫 축은 늘 배치다.** 표본 하나면 호출 측이 ``arr[None]`` 로 넣는다 — 옛 구현은 1D 를 표본
    하나로 봐주는 분기가 있었는데, 그러면 sequence 도메인의 단일 표본 ``(NT, K)`` 을 "표본 NT 개 ×
    K 채널" 로 조용히 오해한다(실측 ``radial_rle`` 에서 그렇게 깨졌다). 도메인마다 native shape 이
    달라 배치 여부를 값만 보고는 알 수 없으므로 규약으로 못박는다.

    옛 구현에는 ``weight`` 인자도 있어 밖에서 나눔수를 받았다. 여러 도메인을 한 좌표로 이어 붙일
    때 도메인마다 몫을 맞추려던 것인데, 도메인이 직교가 되면서 필요가 없어졌다.
    """
    _a = np.asarray(arr, np.float64)
    if norm_d:
        _a = (_a - norm_d["mean"]) / norm_d["std"]
    _flat = _a.reshape(_a.shape[0], -1)
    return _flat / np.sqrt(max(_flat.shape[1], 1))


def totals_of(values: dict[str, np.ndarray]) -> dict[str, list[float]]:
    """도메인별 ``[원소수, Σx, Σx²]`` — 정규화 상수의 재료. 값은 안 들고 누적만 남긴다."""
    return {_d: [float(np.asarray(_a).size), float(np.asarray(_a, np.float64).sum()),
                 float((np.asarray(_a, np.float64) ** 2).sum())]
            for _d, _a in values.items()}


def merge_totals(totals) -> dict[str, list[float]]:
    """누적 여럿을 합친다 — 표본마다 나온 재료를 하나로."""
    _acc: dict[str, list[float]] = {}
    for _m in totals:
        for _d, (_n, _s, _q) in _m.items():
            _a = _acc.setdefault(_d, [0.0, 0.0, 0.0])
            _a[0] += _n
            _a[1] += _s
            _a[2] += _q
    return _acc


def norm_from_totals(totals) -> dict[str, dict[str, float]]:
    """재료 → **정규화 상수** ``{도메인: {mean, std}}`` (도메인마다 스칼라 하나).

    도메인당 스칼라 하나인 것은 타협이 아니라 **불변식**이다 — 도메인은 scale 을 공유하는 채널
    묶음이다(``radial_rle`` 8슬롯은 전부 px 길이라 슬롯 1의 30px 과 슬롯 3의 30px 이 같은 뜻).
    채널별로 표준화하면 그 사실이 깨진다. 채널끼리 scale 이 다른 도메인이 있다면 고칠 것은
    정규화가 아니라 **도메인 분할**이다.
    """
    _out = {}
    for _d, (_n, _s, _q) in merge_totals(totals).items():
        _mean = _s / max(_n, 1.0)
        _var = _q / max(_n, 1.0) - _mean ** 2
        _out[_d] = {"mean": _mean, "std": max(float(np.sqrt(max(_var, 0.0))), 1e-6)}
    return _out


# ── 충분통계 — 묶기의 결과 요약 ────────────────────────────────────────────────
@dataclass
class Stats:
    """한 도메인의 type 별 충분통계 ``(n, Σx, Σ‖x‖²)`` — 첫 축이 type 번호.

    묶기의 **재료가 아니라 요약**이다 — 화면이 중심을 읽고 형상을 되돌리는 데 쓴다. 전 표본을
    상주시키지 않는다.

    ``sqsum`` 이 차원별 배열이 아니라 **스칼라**인 이유: 퍼짐은 차원별 분산을 합쳐서만 쓰므로
    ``Σ_d Var_d = Σ‖x‖²/n − ‖Σx‖²/n²`` 로 스칼라 하나면 된다(4096 → 1). 차원별 분산이 필요한
    곳은 채널별 표준화뿐인데 그건 :func:`norm_from_totals` 의 불변식이 닫았다.

    합은 **float64** 로 누적한다 — float32 로 6만을 더하면 ``Σ‖x‖²`` 이 드리프트한다(실측 상대오차
    ~1e-3).

    Attributes:
        n: ``(M,)`` type 별 표본 수.
        sum: ``(M, D)`` ``Σx``.
        sqsum: ``(M,)`` ``Σ‖x‖²``.
    """

    n:     np.ndarray
    sum:   np.ndarray
    sqsum: np.ndarray

    @classmethod
    def Empty(cls, dim: int) -> "Stats":
        """type 0개짜리 빈 통계 (차원만 정해진 상태)."""
        return cls(np.zeros(0), np.zeros((0, int(dim))), np.zeros(0))

    @property
    def count(self) -> int:
        """type 수."""
        return len(self.n)


def centers(stats: Stats) -> np.ndarray:
    """type 별 중심 ``(M, D)`` = ``Σx/n`` (구성원이 없는 type 은 0)."""
    return stats.sum / np.maximum(stats.n, 1.0)[:, None]


def radii(stats: Stats) -> np.ndarray:
    """type 별 **RMS 반경** ``(M,)`` = ``√(Σ‖x‖²/n − ‖Σx‖²/n²)``. 거리와 같은 축척.

    **묶기는 이 값을 안 쓴다** — 이웃 그래프는 반경을 문지기로 삼지 않는다(구 방식에서 그게
    폭주의 원인이었다: 반경이 크기 가중이라 큰 type 이 작은 것을 거의 공짜로 흡수했다).

    남은 쓸모는 **진단**이다. type 이 연결 성분이라 사슬처럼 늘어질 수 있는데, 그때 반경만 커지고
    ``k`` 는 그대로다 — ``반경 ÷ k`` 가 크면 그 type 은 공이 아니라 줄이다. 아직 화면에 안 걸렸다
    (→ [`TODO.md`](TODO.md)).
    """
    _n = np.maximum(stats.n, 1.0)
    return np.sqrt(np.maximum(stats.sqsum / _n - (stats.sum ** 2).sum(1) / _n ** 2, 0.0))


# ── 거리 ──────────────────────────────────────────────────────────────────────
def _pairwise(X: np.ndarray, Y: np.ndarray | None = None) -> np.ndarray:
    """유클리드 거리 행렬. ``Y`` 가 없으면 ``X`` 자기끼리."""
    _Y = X if Y is None else Y
    _qx, _qy = (X ** 2).sum(1), (_Y ** 2).sum(1)
    return np.sqrt(np.maximum(_qx[:, None] + _qy[None, :] - 2.0 * X @ _Y.T, 0.0))


def knn(X: np.ndarray, neighbors: int, *, block: int = 1024,
        progress: object = None) -> tuple[np.ndarray, np.ndarray]:
    """각 표본의 최근접 ``neighbors`` 개 — ``(거리 (n, m), 상대 (n, m))``. 자기 자신은 뺀다.

    블록으로 끊어 거리를 만든다 — 전체 행렬은 ``n²`` 이라(6만이면 15 GB) 못 든다. 한 블록은
    ``(block, n)`` 이고 그중 ``neighbors`` 개만 남기므로 상주는 ``(n, m)`` 두 장뿐이다.

    Args:
        X: 표준화 좌표 ``(n, D)``.
        neighbors: 이웃 수 ``m``. 표본이 그보다 적으면 있는 만큼.
        block: 한 번에 거리를 잴 행 수.
        progress: ``(라벨, 한 것, 전체)``.

    Returns:
        ``(거리, 상대 index)`` — 각각 ``(n, m)``, 거리 오름차순.
    """
    _n = len(X)
    _m = max(min(int(neighbors), _n - 1), 0)
    if _m == 0:
        return np.zeros((_n, 0), np.float32), np.zeros((_n, 0), np.int32)
    _X = np.asarray(X, np.float32)
    _q = (_X ** 2).sum(1)
    _d = np.empty((_n, _m), np.float32)
    _j = np.empty((_n, _m), np.int32)
    for _s in range(0, _n, block):
        _rows = np.arange(_s, min(_s + block, _n))
        _M = _q[_rows][:, None] + _q[None, :] - 2.0 * (_X[_rows] @ _X.T)
        _M[np.arange(len(_rows)), _rows] = np.inf          # 자기 자신
        _part = np.argpartition(_M, _m - 1, axis=1)[:, :_m]
        _val = np.take_along_axis(_M, _part, 1)
        _order = np.argsort(_val, 1)
        _j[_rows] = np.take_along_axis(_part, _order, 1)
        _d[_rows] = np.sqrt(np.maximum(np.take_along_axis(_val, _order, 1), 0.0))
        if progress is not None:
            progress("이웃 찾기", int(_rows[-1]) + 1, _n)
    return _d, _j


def mutual_edges(dist: np.ndarray, idx: np.ndarray, k: float) -> np.ndarray:
    """상호 최근접 간선 ``(E, 2)`` — **서로가 서로의 이웃 목록에 있고** 거리 ``≤ k`` 인 쌍만.

    상호성이 사슬을 끊는다. 촘촘한 덩어리 옆에 붙은 표본은 자기 쪽에서만 그 덩어리가 이웃이고
    덩어리 쪽에서는 자기들끼리가 더 가까우므로 간선이 안 생긴다 — 구 방식이 그 표본을 통해
    이웃 class 까지 통째로 흡수하던 자리다.

    Args:
        dist: :func:`knn` 의 거리 ``(n, m)``.
        idx: :func:`knn` 의 상대 ``(n, m)``.
        k: 거리 상한 (:func:`threshold_of`).

    Returns:
        ``(E, 2)`` int — ``u < v`` 로 정규화된 쌍(중복 없음).
    """
    _n, _m = idx.shape
    if _m == 0:
        return np.zeros((0, 2), int)
    _src = np.repeat(np.arange(_n), _m)
    _dst = idx.reshape(-1).astype(np.int64)
    _ok = dist.reshape(-1) <= k
    _u, _v = np.minimum(_src, _dst)[_ok], np.maximum(_src, _dst)[_ok]
    # 상호성 = 정규화한 쌍이 **두 번** 나온다 (i→j 와 j→i). 한 번뿐이면 한쪽만 이웃이다.
    _pair = _u.astype(np.int64) * _n + _v
    _uniq, _cnt = np.unique(_pair, return_counts=True)
    _both = _uniq[_cnt >= 2]
    return np.stack([_both // _n, _both % _n], 1).astype(int)


def components(n: int, edges: np.ndarray, min_members: int) -> np.ndarray:
    """간선으로 이어진 **연결 성분** → type 번호 ``(n,)``. ``min_members`` 미만은 :data:`POOL`.

    번호는 성분의 **크기 내림차순**이다 — type 0 이 늘 가장 큰 덩어리라 화면이 안정된다.
    """
    _parent = np.arange(n)

    def _find(_x: int) -> int:
        while _parent[_x] != _x:
            _parent[_x] = _parent[_parent[_x]]
            _x = int(_parent[_x])
        return _x

    for _u, _v in np.asarray(edges, int):
        _a, _b = _find(int(_u)), _find(int(_v))
        if _a != _b:
            _parent[_a] = _b
    _root = np.array([_find(_i) for _i in range(n)])
    _ids, _cnt = np.unique(_root, return_counts=True)
    _keep = _ids[_cnt >= max(int(min_members), 1)]
    _order = _keep[np.argsort(-_cnt[np.isin(_ids, _keep)], kind="stable")]
    _seat = {int(_r): _i for _i, _r in enumerate(_order)}
    return np.array([_seat.get(int(_r), POOL) for _r in _root], int)


def stats_of(X: np.ndarray, lab: np.ndarray) -> Stats:
    """배정 ``(n,)`` 에서 type 별 충분통계를 센다 — :data:`POOL` 은 뺀다."""
    _M = int(lab.max()) + 1 if (lab >= 0).any() else 0
    _st = Stats.Empty(X.shape[1])
    if not _M:
        return _st
    _Xd = np.asarray(X, np.float64)
    _st.n = np.array([float((lab == _t).sum()) for _t in range(_M)])
    _st.sum = np.stack([_Xd[lab == _t].sum(0) for _t in range(_M)])
    _st.sqsum = np.array([float((_Xd[lab == _t] ** 2).sum()) for _t in range(_M)])
    return _st


def fit(X: np.ndarray, k: float, min_members: int, *, neighbors: int = 5,
        block: int = 1024, progress=None,
        ) -> tuple[np.ndarray, np.ndarray, Stats, np.ndarray]:
    """한 도메인의 좌표 ``(n, D)`` → ``(배정, 중심까지 거리, 통계, 간선)``.

    이 함수가 **알고리즘 전체**다. store 도 트리도 모르므로 배열만으로 단독 호출·검증된다::

        ① knn           표본마다 최근접 neighbors 개
        ② mutual_edges  서로가 서로의 이웃이고 거리 ≤ k 인 쌍만 간선
        ③ components    연결 성분이 type (min_members 미만은 대기 풀)
        ④ stats_of      결과를 충분통계로 요약 (화면이 중심·퍼짐을 읽는다)

    안 붙은 표본을 최근접 type 에 억지로 넣지 않는다. 넣으면 구성표가 거짓이 된다 — 그 자리는
    :data:`POOL` 로 남고 **거리로** 읽힌다.

    Args:
        X: 표준화 좌표 ``(n, D)`` (:func:`equalize`). float32 로 줘도 된다.
        k: 거리 상한 (:func:`threshold_of`).
        min_members: type 승격 최소 표본.
        neighbors: 이웃 수 (:func:`neighbors_of`).
        block: 거리 블록 크기.
        progress: ``(라벨, 한 것, 전체)``.

    Returns:
        ``(배정 (n,), 거리 (n,), 통계, 간선 (E, 2))``. 배정이 :data:`POOL` 인 자리의 거리는
        **최근접 type 까지**다. type 이 하나도 안 서면 거리는 전부 ``inf``.

        **간선을 함께 낸다** — 묶기의 근거라 검증·진단이 이 값을 본다(어느 쌍이 이어졌나).
        종합(:func:`join`)은 이걸 안 쓴다 — 거기서는 label 만 읽는다.
        label 만으로는 그게 안 된다: label 이 같은지만 보면 "가깝지만 축 하나의 type 경계를 사이에
        둔" 쌍이 갈라져 조합이 1건인 그룹이 쏟아진다.
    """
    _n = len(X)
    if _n == 0:
        return (np.zeros(0, int), np.zeros(0),
                Stats.Empty(X.shape[1] if X.ndim > 1 else 1), np.zeros((0, 2), int))
    _d, _j = knn(X, neighbors, block=block, progress=progress)
    _edges = mutual_edges(_d, _j, k)
    if progress is not None:
        progress(f"간선 {len(_edges)}", _n, _n)
    _lab = components(_n, _edges, min_members)
    _stats = stats_of(X, _lab)
    if progress is not None:
        progress(f"성분 {_stats.count}", _n, _n)

    _dist = np.full(_n, np.inf)
    if _stats.count:
        _C = centers(_stats)
        for _s in range(0, _n, block):
            _x = np.asarray(X[_s:_s + block], np.float64)
            _D = _pairwise(_x, _C)
            _row = _lab[_s:_s + block]
            _dist[_s:_s + block] = np.where(_row >= 0,
                                            _D[np.arange(len(_x)), np.maximum(_row, 0)],
                                            _D.min(1))
    return _lab, _dist, _stats, _edges


# ── 기권을 메운다 — 다른 축이 후보를 좁힌다 ───────────────────────────────────
def impute(labels: dict[str, np.ndarray], coords: dict[str, np.ndarray],
           centers_by: dict[str, np.ndarray], bound: float,
           ) -> tuple[dict[str, np.ndarray], dict[str, list[int]]]:
    """기권한 축을 **다른 축을 참고해** 메운다 — 종합에서만 쓰는 값이다.

    표본이 한 축에서 :data:`POOL` 이면 그 조합은 남과 견줄 수 없다. 그렇다고 거부권으로 쓰면
    배정이 깎이고(76.2% → 89.7%), 통행증으로 쓰면 그 조합이 다리가 되어 다른 축의 분할을 도로
    붙인다(실측 순도 5.1% 로 붕괴). 그래서 **비워 두지 말고 메운다**::

        후보  다른 축에서 나와 같은 type 인 표본들이, 이 축에서 받은 type
        선택  그중 자기 축 중심까지 가장 가까운 것 (``bound`` 밖이면 안 고른다)

    다른 축이 후보를 좁히고 자기 축 거리가 그중 하나를 고르므로, 두 축이 각자 아는 것만 쓴다.
    실측(표본 10,000 · ``k=0.08`` · ``bound=0.3``) — 1건짜리 종합 type 이 85 → 10 으로 줄고 순도는
    88.4% 그대로다. ``bound`` 를 풀면(∞) 4까지 줄지만 순도가 88.1% 로 빠진다 — 멀리 있는 것까지
    억지로 붙인 대가라 경계를 둔다.

    **잣대의 답을 안 고친다.** 낸 값은 종합 전용이고, 축 화면은 여전히 "모른다"고 말한다 — 문턱을
    넘어 인정한 것과 추정으로 붙인 것을 한 자리에 두면 축이 자기가 모른다고 한 것을 아는 척한다.

    Args:
        labels: ``{도메인: 배정 (n,)}``.
        coords: ``{도메인: 표준화 좌표 (n, D)}`` — 거리를 재려면 필요하다.
        centers_by: ``{도메인: type 중심 (M, D)}``.
        bound: 중심까지 이 거리 안일 때만 메운다. 밖이면 기권으로 남는다(**진짜 고립**).

    Returns:
        ``(메운 배정, {도메인: [메운 표본 index]})``.
    """
    _names = sorted(labels)
    _out = {_d: np.asarray(_v, int).copy() for _d, _v in labels.items()}
    _filled: dict[str, list[int]] = {_d: [] for _d in _names}
    for _d in _names:
        _cen = centers_by.get(_d)
        _Z = coords.get(_d)
        if _cen is None or _Z is None or not len(_cen):
            continue
        _others = [_e for _e in _names if _e != _d]
        _peers = {_e: {} for _e in _others}                # 다른 축 type → 이 축 type 후보
        for _e in _others:
            for _t, _v in zip(labels[_e], labels[_d]):
                if _t >= 0 and _v >= 0:
                    _peers[_e].setdefault(int(_t), set()).add(int(_v))
        for _i in np.flatnonzero(np.asarray(labels[_d], int) < 0):
            _cand: set[int] | None = None
            for _e in _others:
                _t = int(labels[_e][_i])
                if _t < 0:
                    continue
                _here = _peers[_e].get(_t, set())
                _cand = set(_here) if _cand is None else (_cand & _here) or _cand
            if not _cand:
                continue
            _ids = sorted(_cand)
            _dist = np.linalg.norm(np.asarray(_cen, np.float64)[_ids] - _Z[_i], axis=1)
            _j = int(_dist.argmin())
            if _dist[_j] <= bound:
                _out[_d][_i] = _ids[_j]
                _filled[_d].append(int(_i))
    return _out, _filled


# ── 축을 합친다 — 쪼개고, 자의적인 경계는 도로 붙인다 ────────────────────────
def type_neighbors(centers: np.ndarray, k: float, neighbors: int) -> np.ndarray:
    """그 축의 **type 끼리** 상호 최근접 간선 ``(E, 2)`` — 표본에 쓴 규칙을 중심에 그대로.

    "두 type 의 경계가 자의적인가" 를 묻는 자리다. 표본을 묶을 때 구를 버린 이유가 여기서도
    성립하므로(type 마다 이웃까지의 거리가 다르다) 문턱 하나로 자르지 않는다.

    Args:
        centers: type 중심 ``(M, D)`` (:func:`centers`).
        k: 거리 상한 — 이보다 먼 쌍은 이웃이어도 안 잇는다.
        neighbors: 이웃 수.
    """
    _C = np.asarray(centers, np.float64)
    if len(_C) < 2:
        return np.zeros((0, 2), int)
    _d, _j = knn(_C, neighbors)
    return mutual_edges(_d, _j, k)


# ── 축을 합친다 — label 을 읽는다 ─────────────────────────────────────────────
def join(labels: dict[str, np.ndarray], type_edges: dict[str, np.ndarray] | None = None,
         ) -> tuple[np.ndarray, list[dict[str, list[int]]]]:
    """축별 배정을 합친다 — **표본 하나의 축 label 조합이 곧 종합 type** 이다.

    **종합에는 거리가 없다.** 잣대가 "같은 type" 이라고 한 순간 그 축의 답은 끝났고, 종합이 그 위에서
    다시 이웃을 재는 건 같은 데이터로 같은 질문을 두 번 하는 것이라 두 번째 답이 첫 번째를 덮는다.
    한때 type 중심끼리 상호 최근접을 재 봤더니 **축이 갈라 놓은 것이 도로 붙었다** — 종합 type 하나가
    outline type 17개를 삼켰고 그 17개의 최다 class 는 ``151`` 과 ``219`` 로 서로 달랐다.

    층마다 묻는 것이 다르다::

        잣대   이 표본들이 **이 좌표에서** 같은가   →  표본 상호 최근접 (fit)
        종합   축들이 **서로 어긋나는가**          →  축 label 을 그대로 읽는다

    그래서 여기엔 ``k`` 도 이웃 수도 안 들어온다. label 이 같으면 같고 다르면 다르다.

    **기권(:data:`POOL`)도 하나의 값이다.** ``(5, ⊥)`` 는 "outline 은 5번, signed 는 모르겠다" 인
    자리고, 같은 처지의 표본끼리 모인다. 거부권으로 쓰면(한 축이라도 기권이면 보류) 배정이 13.5pp
    깎이고(76.2% → 89.7%), 반대로 통행증으로 쓰면(할 말이 없으니 통과) **그 조합이 다리가 되어**
    signed 가 갈라 둔 것을 도로 붙인다(실측 전부가 한 덩어리로 무너져 순도 5.1%). 값으로 두면 둘 다
    안 일어난다.

    보류는 **전부 기권일 때뿐** — 어느 축도 할 말이 없으면 좌표가 아니라 부재다.

    **``min_members`` 를 여기서 다시 걸지 않는다 — 문턱은 잣대가 이미 지켰다.** 그래서 1건짜리 종합
    type 은 고립된 표본이 **아니다**. 그 표본은 label 을 받은 축마다 문턱을 넘고 왔고, 유일한 것은
    **조합**이다. 실측 554개 중 215개는 두 축 모두 크기 3+ 인 type 소속이었고, 그중 27개는 두 축의
    최다 class 가 아예 달랐다 — 오검출 후보 그 자체라 지우면 손해다.

    #### 쪼갠 뒤, **자의적인 경계는 도로 붙인다**

    조합을 그대로 두면 잘게 부서진다 — 실측 종합 type 1,749개 중 1,013개(58%)가 "outline 은 같은데
    signed 가 갈랐다" 였고, 그 조각의 상당수가 한두 건이었다. 문제는 signed 가 **틀린 게 아니라**
    그 둘의 경계가 자의적이었다는 것이다: signed type 841 과 427 이 서로 이웃이면 그 사이 선은
    데이터가 그은 게 아니라 연결이 한 번 끊긴 자리다.

    그래서 ``type_edges`` 를 주면 **모든 축에서 같거나 이웃**인 조합끼리 잇는다::

        (5, 841) 과 (5, 427)   outline 같음 · signed 가 이웃      →  붙인다
        (5, 841) 과 (6, 427)   outline 이웃 · signed 이웃         →  붙인다
        (5, 841) 과 (9, 427)   outline 이 멀다                    →  안 붙인다

    한 축이라도 "같지도 이웃도 아니다" 면 안 붙는다 — 그 축이 **실제로 갈랐다**는 뜻이라서다.

    연결 성분이므로 **전이적**이다. A-B 가 붙고 B-C 가 붙으면 셋이 한 덩어리고, 그 사슬이 축을
    건너뛸 수도 있다. 그게 약점이 아니라 강점이다 — 경계가 자의적인 자리를 따라 구조가 이어져 있다면
    그것이 하나의 덩어리인 게 맞다. 실측으로도 안 번진다(한 종합 type 이 품은 축 type 수 중앙 2)::

        조합 그대로            type 1,585  순도 88.5%  1건 53  최대 2,548
        모든 축 같거나 이웃      type   832  순도 88.1%  1건 22  최대 2,886

    한때 "**딱 한 축만** 다를 때만" 으로 조였다. 모든 축을 열었더니 전부 한 덩어리가 됐기
    때문인데(순도 5.1%), 그 원인은 축 수가 아니라 **기권이 다리가 된 것**이었다 — ``(5,⊥)`` 가
    ``(5,3)`` 과도 ``(5,7)`` 과도 이어졌다. :func:`impute` 가 그 구멍을 막으면서 브레이크를 뗄
    근거가 섰고, 실제로 떼도 순도가 0.1pp 만 움직인다.

    반대 방향(**더 촘촘히 쪼개기**)은 안 한다. 종합 type 안에서 ``k`` 를 0.7배로 줄여 다시 봤더니
    3건 이상 조각의 순도가 85.8% → 87.1% 로 1.3pp 오르는 동안 **4,042건이 1건짜리로 흩어졌다** —
    노이즈 바닥을 넘은 것이지 구조를 찾은 게 아니다. 쪼개는 일은 축이 이미 한다.

    Args:
        labels: ``{도메인: 배정 (n,)}``. 비면 전부 :data:`POOL`.
        type_edges: ``{도메인: (E, 2)}`` — 그 축의 :func:`type_neighbors`. 주면 위 병합을 한다.
            안 주면 조합이 곧 type 이다(병합 없음).

    Returns:
        ``(배정 (n,), 구성 목록)``. 구성 목록의 ``i`` 번째는 ``{축: [그 종합 type 이 품은 축 type들]}``
        — 병합했으면 축마다 여럿일 수 있다. 화면이 "어느 축의 무엇이 뭉쳤나" 를 그대로 읽는다.
    """
    _names = sorted(labels)
    if not _names:
        return np.zeros(0, int), []
    _cols = [np.asarray(labels[_d], int) for _d in _names]
    _n = len(_cols[0])
    _live = np.zeros(_n, bool)
    for _c in _cols:
        _live |= _c >= 0                       # 전부 기권이면 좌표가 없다 — 보류
    _tuples = [tuple(int(_c[_i]) for _c in _cols) for _i in range(_n)]
    _cnt = Counter(_t for _t, _o in zip(_tuples, _live) if _o)
    _cells = sorted(_cnt)
    _weld = _merge_cells(_cells, _names, type_edges or {})     # 셀 → 종합 type 자리
    _size: Counter = Counter()
    for _t, _n2 in _cnt.items():
        _size[_weld[_t]] += _n2
    _order = sorted(_size, key=lambda _g: (-_size[_g], _g))    # 큰 덩어리가 0번
    _seat = {_g: _i for _i, _g in enumerate(_order)}
    _lab = np.array([_seat[_weld[_t]] if _o else POOL
                     for _t, _o in zip(_tuples, _live)], int)
    _members: list[dict[str, list[int]]] = [{_d: [] for _d in _names} for _ in _order]
    for _t in _cells:
        _m = _members[_seat[_weld[_t]]]
        for _a, _d in enumerate(_names):
            if _t[_a] >= 0 and _t[_a] not in _m[_d]:
                _m[_d].append(int(_t[_a]))
    for _m in _members:
        for _d in _m:
            _m[_d].sort()
    return _lab, _members


def _merge_cells(cells: list[tuple], names: list[str],
                 type_edges: dict[str, np.ndarray]) -> dict[tuple, int]:
    """조합 → 종합 type 자리 — **모든 축에서 같거나 이웃**인 것끼리 잇는다.

    ``type_edges`` 가 비면 조합이 곧 자기 자리다(병합 없음).
    """
    _C = len(cells)
    if not _C:
        return {}
    _at = {_t: _i for _i, _t in enumerate(cells)}
    if not type_edges:
        return dict(_at)
    _arr = np.asarray(cells, int)
    _same = np.stack([_arr[:, _a][:, None] == _arr[:, _a][None] for _a in range(len(names))])
    _near = []
    for _a, _d in enumerate(names):
        _e = np.asarray(type_edges.get(_d, np.zeros((0, 2), int)), int)
        _lab = _arr[:, _a]
        _M = int(max(_lab.max(), _e.max() if len(_e) else 0)) + 1
        _adj = np.zeros((_M, _M), bool)
        if len(_e):
            _adj[_e[:, 0], _e[:, 1]] = True
            _adj[_e[:, 1], _e[:, 0]] = True
        _have = _lab >= 0
        _near.append(_adj[np.ix_(np.maximum(_lab, 0), np.maximum(_lab, 0))]
                     & _have[:, None] & _have[None, :])
    _near = np.stack(_near)
    # 한 축이라도 "같지도 이웃도 아니다" 면 안 붙는다 — 그 축이 실제로 가른 자리다.
    _ok = (_same | _near).all(0)
    _grp = components(_C, np.argwhere(np.triu(_ok, 1)), 1)
    return {_t: int(_grp[_i]) for _t, _i in _at.items()}
