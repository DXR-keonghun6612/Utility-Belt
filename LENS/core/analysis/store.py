"""분석 산출물 store — 범주 = 상태, item = 표본 ``(stem, obj)``, leaf = feature.

class·type 은 트리에 없다. 표본별 기록은 ``params/index``, 충분통계는 ``params/stats__{도메인}``
한 장이다 — 재분류가 파일을 안 건드리게.

**키가 class 가 아니라 도메인이다.** 옛 구조는 ``stats__{상태}__{class}`` 로 class 마다 한 장이었고,
가르기가 class 안에서만 돌았다. 지금은 표본이 그냥 들어와 type 이 데이터에서 나오고, 도메인끼리
직교라 도메인마다 자기 type 집합을 갖는다. 그래서 표본 하나의 배정은 **도메인 수만큼**이다::

    index[key] = {sign, class, state,
                  types: {도메인: type 번호},     # -1 = 어디에도 안 붙음
                  dists: {도메인: 중심까지 거리}}   # outlier 를 이 값으로 읽는다

class 는 obj 에 붙은 정보라 배정에 안 들어간다. 여기서 class 가 나오는 곳은 :meth:`Composition`
하나뿐이고, 그것도 **읽기**다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from ..constant import MODIFIED, STAGED, TO_STORAGE
from ..port import Structure
from ..schema import Data_Ref
from ..store import Bucket_Store
from .cluster import (
    JOINT, POOL, Stats, centers, neighbors_of, radii, threshold_of, type_neighbors, welds_of)
from .extract import Fold

#: 정본 root 아래 산출물 서브트리 — ``.`` 로 숨긴다(사람이 만든 것이 아니다).
#:
#: **정본 하나에 산출물도 하나다.** 한때 config 내용의 해시로 하위 폴더를 갈라 여러 설정의 산출물을
#: 나란히 뒀는데, 실제로는 설정을 고치면 옛 산출물을 다시 볼 일이 없었고 대신 폴더가 소리 없이 쌓여
#: (계약이 바뀐 죽은 산출물 포함) 어느 것이 지금 것인지 사람이 해시로 판별해야 했다. 설정이 바뀌면
#: 계약이 바뀌고, 계약이 바뀌면 다시 뽑는다 — 그게 한 자리로 충분한 이유다.
ANALYSIS_DIR = ".analysis"

#: 표본 주소 — 분석이 보는 것은 프레임이 아니라 그 프레임의 객체 하나다.
Address = tuple[str, int]

#: params 이름.
INDEX    = "index"      # {key: {sign, class, state, types, dists}}
NORM     = "norm"       # {도메인: {mean, std}} — ① 적재가 정한다
CONTRACT = "contract"   # 추출기 계약
CLUSTER  = "cluster"    # 묶기 설정 + {도메인: 서명}
STATS    = "stats"      # stats__{도메인} — 마지막 clustering 시점
JOINT_P  = "joint"      # 종합 — 배정·구성·메운 자리를 **자기 장부**에 든다 (index 와 별도)
RECIPE   = "recipe"     # 화면 설정 사본 — 이 산출물을 **무엇으로 만들었나** (정본에도 있다)

# **화면 레시피는 여기 없다.** 한때 ``recipe`` params 로 산출물 옆에 뒀는데, 그러면 산출물을 지우는
# 순간(``[feature 삭제]``) 사용자의 설정까지 사라진다. "어떻게 만드는가"(레시피)와 "만들어진
# 것"(산출물)은 수명이 다르므로 레시피는 **정본**이 든다 (`gui/meta_page/analysis/_dialog`).

#: 캐시 전용 key — 파일이 아니라 index 를 묶어 둔 것 (params 이름과 안 겹치게).
_GROUPED = "\x00grouped"
_BY_CLASS = "\x00by_class"

_JSON  = {"to": TO_STORAGE, "format": "json"}
_NPZ   = {"to": TO_STORAGE, "type": "arrays", "format": "npz"}

#: type 축 자리 수 경고 상한의 **기본값** — 실제 값은 묶기 설정 ``max_axis_types`` 가 든다.
_MAX_TYPES = 5000


class Type_explosion(RuntimeError):
    """type 수가 경고 상한을 넘었다 — 중심끼리 재기 전에 사람에게 되묻는 자리.

    "틀렸다"가 아니라 "이만큼 들 텐데 의도한 것이냐"다. `k` 를 낮춰 잘게 가르는 것 자체는 비용이
    아니지만(막아야 할 것은 1개짜리가 무한정 느는 것뿐이고 승격 조건이 그걸 막는다), 중심끼리의
    거리 행렬은 자리 수의 **제곱**이라 여기서만 걸린다.
    """

    def __init__(self, domain: str, n_type: int, limit: int) -> None:
        self.domain, self.n_type, self.limit = str(domain), int(n_type), int(limit)
        super().__init__(
            f"'{domain}' 의 type 이 {n_type:,}개다 (경고 상한 {limit:,}). 중심끼리 재려면 "
            f"{n_type ** 2 * 8 / 1e9:.1f} GB 가 든다 — 의도한 것이면 [type 축 경고 상한]을 올리고, "
            f"아니면 [type 반경]을 키워라.")


@dataclass
class Cluster_Bucket(Bucket_Store):
    """cluster bucket — 상태 범주에 표본이 들어가고, 그 위 값은 전부 params.

    자리·영속(``Restore``/``Save``/``Move``/``Delete``)은 ``Bucket_Store`` 가 든다.
    """

    CATEGORIES:       ClassVar[tuple[str, ...]] = (STAGED, MODIFIED)
    DEFAULT_CATEGORY: ClassVar[str]             = MODIFIED
    __exclude_serialize__: ClassVar[set[str]]   = {"root", "_memo"}

    #: params 캐시 — **읽기가 디스크를 다시 안 타게**.
    #:
    #: params 는 `Param` 이 부를 때마다 파일을 연다(index 5 MB JSON 파싱 42 ms). 조회가 중첩되는
    #: 경로가 있어 캐시가 없으면 화면 한 장이 초 단위가 된다. 쓰기(``_put``)가 그 자리를 지우므로
    #: 값이 낡을 자리는 없다.
    _memo: dict = field(default_factory=dict, repr=False)

    # ── 자리 ────────────────────────────────────────────────────────────────────
    @staticmethod
    def Root(dataset_root: str | Path) -> Path:
        """산출물 루트 (경로만 — 만들지 않는다) — 정본 하나에 **한 자리**다."""
        return Path(dataset_root) / ANALYSIS_DIR

    @classmethod
    def Open(cls, dataset_root: str | Path, *, params_only: bool = False) -> "Cluster_Bucket":
        """그 정본의 산출물 store 를 연다.

        Args:
            dataset_root: 정본 루트.
            params_only: params 만 복원한다 — 표본을 안 물을 때(계약·index 조회). 전체 복원은
                6만 사이드카라 초 단위인데 params 는 밀리초다.
        """
        return cls.Restore(cls.Root(dataset_root), only=(cls.PARAMS,) if params_only else None)

    @staticmethod
    def Key(address: Address) -> str:
        """표본 주소 → item key ``{stem}_{obj}``."""
        return f"{address[0]}_{int(address[1])}"

    @staticmethod
    def Address(key: str) -> Address:
        """item key → 표본 주소. stem 에 ``_`` 가 있어도 마지막 하나로만 가른다."""
        _stem, _, _obj = key.rpartition("_")
        return (_stem, int(_obj)) if _stem and _obj.isdigit() else (key, 0)

    # ── 표본 — leaf 는 feature 뿐 ────────────────────────────────────────────────
    def Put_features(self, address: Address, values: dict[str, Any], specs: dict[str, dict],
                     state: str) -> None:
        """표본 하나의 도메인 값을 앉히고 그 item 사이드카만 쓴다.

        ``specs`` 가 그릇을 정한다 — ``{to: meta}`` 면 인라인, ``{to: storage}`` 면 kind-major 파일.
        """
        _key = self.Key(address)
        if self.tree.Get(state).Get(_key) is None:
            self.Set(_key, Data_Ref(info={}), category=state)
        _item = self.tree.Get(state).Get(_key)
        for _name, _spec in specs.items():
            if values.get(_name) is not None:
                _item.Push(_name, self.Route((state, _key), _name, _spec, values[_name]))
        self.Save(_key, self._order(_key, state))

    def Features(self, address: Address, names: list[str] | None = None) -> dict[str, np.ndarray]:
        """그 표본의 **저장된 feature 그대로** (없으면 ``{}``). ``names`` 를 주면 그것만.

        가르기는 이걸 안 쓴다 — 거리는 잣대 좌표에서 잰다(:meth:`Measure`). 이건 **사람이 볼 때**
        쓰는 자리다: 잣대는 ``radial_rle`` 를 한 겹으로 접으므로 구멍이 여럿인 객체는 그림에서
        뭉개진다. 원본을 그려야 실제 형상이 보인다.
        """
        _feats = self._resolved(address)
        return {_f: np.asarray(_v) for _f, _v in _feats.items()
                if names is None or _f in names}

    def _resolved(self, address: Address) -> dict:
        """그 표본의 ``{feature: 값}`` — **그 표본이 든 묶음 캐시 한 장**에서 꺼낸다.

        표본은 자기 사이드카를 안 든다(값은 정본이 소유하고 여기는 묶음별 캐시 사본이다). 그래서
        주소 → class → 캐시 npz → 그 안에서 행 찾기다. 같은 묶음을 반복해 물으면 캐시가 받아
        디스크를 두 번 안 탄다.
        """
        from . import cache
        _key = self.Key(address)
        _cls = str(self.Index().get(_key, {}).get("class", ""))
        _feat = self._feature_name()
        if not _feat:
            return {}
        _got = self._derived(("cache", _cls), lambda: cache.Load(self, cache.CLASS, _cls))
        if _got is None:
            return {}
        _keys, _rows = _got
        _at = {_k: _i for _i, _k in enumerate(_keys)}
        return {} if _key not in _at else {_feat: _rows[_at[_key]]}

    def _feature_name(self) -> str:
        """계약이 든 저장 feature 이름 (하나뿐 — 정본이 드는 그 배열). 없으면 빈 문자열."""
        _names = sorted((self.Contract().get("features") or {}))
        return _names[0] if _names else ""

    def Measure(self, address: Address, domains: list[str] | None = None) -> dict[str, np.ndarray]:
        """그 표본을 **잣대로 잰 값** ``{도메인: 값}`` (없으면 ``{}``). ``domains`` 를 주면 그것만.

        트리에 그 item 이 없으면 **그 사이드카 하나만** 읽어 온다 — params 만 열고도 고른 표본을
        그릴 수 있게(전체 복원 없이). 읽은 것은 트리에 앉혀 두 번 안 읽는다.

        디스크에 있는 것은 feature 고 여기서 나가는 것은 잣대 값이다 — 접기는 이 메서드 안에서
        닫힌다. 부르는 쪽은 도메인 이름만 알면 되고, 그 값이 파일 그대로인지 접은 것인지는 안다고
        해서 할 일이 달라지지 않는다.
        """
        _feats, _gauges = self._resolved(address), self.Gauges()
        _use = domains if domains is not None else list(_gauges)
        return {_d: Fold(_gauges[_d][1], np.asarray(_feats[_gauges[_d][0]]))
                for _d in _use
                if _d in _gauges and _feats.get(_gauges[_d][0]) is not None}

    def _restore_item(self, key: str) -> tuple[str, str] | None:
        """그 표본 사이드카 하나를 읽어 트리에 앉힌다 (없으면 None) — 상태는 index 가 안다."""
        _state = str(self.Index().get(key, {}).get("state", "")) or None
        for _s in ([_state] if _state else list(self.CATEGORIES)):
            _doc = Structure.Read(self.root, (_s, key))
            if _doc is not None:
                self.Set(key, Data_Ref(**_doc), category=_s)
                return (_s, key)
        return None

    def _order(self, key: str, state: str) -> int:
        """그 상태가 이 key 를 든 몇 번째 범주인가 (없으면 1)."""
        _cats = self.Categories_of(key)
        return _cats.index(state) + 1 if state in _cats else 1

    # ── params — 전역 값 ────────────────────────────────────────────────────────
    def Index(self) -> dict[str, dict]:
        """표본별 기록 ``{key: {sign, class, state, types, dists}}`` — **지금**의 배정이다."""
        return dict(self._param(INDEX) or {})

    def Set_index(self, index: dict[str, dict]) -> None:
        self._put(INDEX, _JSON, index)

    def Norm(self) -> dict[str, dict[str, float]]:
        """도메인별 정규화 상수 — ① 적재가 수치로 정한 확정 값."""
        return dict(self._param(NORM) or {})

    def Set_norm(self, norm: dict) -> None:
        self._put(NORM, _JSON, dict(norm or {}))

    def Contract(self) -> dict:
        """추출기 계약 — ``features``(저장) 와 ``gauges``(도메인별 잣대)."""
        return dict(self._param(CONTRACT) or {})

    def Set_contract(self, contract: dict) -> None:
        self._put(CONTRACT, _JSON, dict(contract or {}))

    def Set_gauges(self, gauges: dict) -> bool:
        """계약의 **잣대 절반만** 갈아 끼운다 (``features`` 는 안 건드린다). 바뀌었으면 ``True``.

        수명이 다르니 쓰는 자리도 다르다 — ``features`` 는 디스크에 있는 것이라 추출만이 쓰지만,
        잣대는 **config 소유**라 고쳐도 재추출이 없다(저장된 원본을 다시 접기만 하면 된다). 그래서
        이쪽은 config 를 읽을 때마다 따라온다. 둘을 한 번에 쓰면 config 에 잣대를 더해도 6만 표본을
        다시 뽑기 전엔 화면에 안 뜬다.

        Args:
            gauges: ``{도메인: {kind, shape, feature, folds}}``.

        Returns:
            실제로 디스크를 고쳤나 (같으면 안 쓴다 — 열 때마다 params 를 건드릴 이유가 없다).
        """
        _c = self.Contract()
        if dict(_c.get("gauges") or {}) == dict(gauges or {}):
            return False
        _c["gauges"] = dict(gauges or {})
        self.Set_contract(_c)
        return True

    def Cluster_cfg(self) -> dict:
        """묶기 설정 + ``{도메인: 서명}`` — 낡음 판별이 이 한 장으로 끝난다."""
        return dict(self._param(CLUSTER) or {})

    def Set_cluster_cfg(self, cfg: dict) -> None:
        self._put(CLUSTER, _JSON, dict(cfg or {}))

    def Recipe(self) -> dict:
        """이 산출물을 만든 **화면 설정** (없으면 빈 dict).

        :meth:`Cluster_cfg` 와 다르다 — 저건 묶기가 실제로 쓴 인자고, 이건 순회 축·보기·켠 축까지
        포함한 화면 상태다. 산출물 폴더가 자기 설정을 들고 다녀야 **결과마다 다른 조건**으로 돌린
        것이 뒤섞이지 않는다.

        정본에도 같은 것이 있다(그쪽이 원본 — ``[feature 삭제]`` 가 이 폴더를 지워도 남는다).
        읽는 쪽은 **여기 있으면 여기를 쓴다**.
        """
        return dict(self._param(RECIPE) or {})

    def Set_recipe(self, recipe: dict) -> None:
        self._put(RECIPE, _JSON, dict(recipe or {}))

    def _param(self, name: str):
        """params 하나를 **캐시를 거쳐** 읽는다 — 같은 값을 두 번 파싱하지 않게."""
        if name not in self._memo:
            self._memo[name] = self.Param(name)
        return self._memo[name]

    def _put(self, name: str, spec: dict, value: Any) -> None:
        """params leaf 하나를 앉히고 그것만 쓴다 (캐시도 갱신)."""
        self.Put_param(name, spec, value)
        self._memo[name] = value
        for _k in [_k for _k in self._memo if isinstance(_k, tuple)]:
            del self._memo[_k]                      # 파생값(중심·반경·구성)은 다시 센다
        if name == INDEX:
            self._memo.pop(_GROUPED, None)          # 배정이 바뀌면 묶음도 다시 만든다
            self._memo.pop(_BY_CLASS, None)

    # ── stats — 도메인당 한 장 ──────────────────────────────────────────────────
    @staticmethod
    def Stats_name(domain: str) -> str:
        """params leaf 이름. ``/`` 를 쓰면 사이드카가 한 겹 더 깊어져 ``Restore`` 가 거부한다."""
        return f"{STATS}__{domain}"

    def Type_stats(self, domain: str) -> Stats:
        """그 도메인의 충분통계 ``(n, sum, sqsum)`` — 없으면 type 0개짜리 빈 통계.

        **읽기 전용이다** — 캐시된 배열을 그대로 준다(복사 안 함). 고칠 것이면
        :meth:`Set_stats` 로 새 값을 넣는다.
        """
        def _make() -> Stats:
            _raw = self._param(self.Stats_name(domain)) or {}
            if "sum" not in _raw:
                return Stats.Empty(self.Dims().get(domain, 1))
            return Stats(np.asarray(_raw["n"], np.float64),
                         np.asarray(_raw["sum"], np.float64),
                         np.asarray(_raw["sqsum"], np.float64))
        return self._derived(("stats", domain), _make)

    def Set_stats(self, domain: str, stats: Stats) -> None:
        """그 도메인의 통계를 npz 한 장으로 쓴다."""
        self._put(self.Stats_name(domain), _NPZ,
                  {"n": stats.n, "sum": stats.sum, "sqsum": stats.sqsum})

    def Drop_stats(self, domain: str) -> None:
        """그 도메인의 통계를 걷는다 (없으면 no-op)."""
        _name = self.Stats_name(domain)
        self._memo.pop(_name, None)
        for _k in [_k for _k in self._memo if isinstance(_k, tuple)]:
            del self._memo[_k]
        self.Delete_param(_name)

    def _derived(self, key: tuple, make):
        """파생값 캐시 — 같은 것을 반복해 묻는 경로가 매번 다시 세지 않게."""
        if key not in self._memo:
            self._memo[key] = make()
        return self._memo[key]

    # ── 계약이 답하는 것 ────────────────────────────────────────────────────────
    def _gauge_specs(self) -> dict[str, dict]:
        """계약의 잣대 블록 ``{도메인: {kind, shape, feature, folds}}``."""
        return dict(self.Contract().get("gauges") or {})

    def Domains(self) -> list[str]:
        """계약이 답하는 도메인(= 잣대) 이름 (정렬). **종합은 안 든다** — 계약의 것이 아니다."""
        return sorted(self._gauge_specs())

    def View_domains(self, enabled: list[str] | None = None) -> list[str]:
        """화면이 고를 자리 — **종합이 맨 앞**, 그 뒤로 축들.

        묶기(:func:`~.group.build`)는 :meth:`Domains` 를 쓰고 화면은 이것을 쓴다. 종합은 축이
        아니라 축들의 곱이므로 가를 대상 목록에 끼면 자기를 자기로 가르려 든다.

        Args:
            enabled: 켠 축만 (``None`` 이면 전부). 종합은 켠 축들의 곱이라 **끄지 않는다** —
                종합을 못 보게 하려면 축을 꺼야 한다.
        """
        _use = [_d for _d in self.Domains() if enabled is None or _d in set(enabled)]
        return ([JOINT] if self.Types(JOINT) else []) + _use

    def Kinds(self) -> dict[str, str]:
        """``{도메인: feature|token}`` — 화면이 표현을 고르는 근거."""
        return {_d: str(_o.get("kind", "")) for _d, _o in self._gauge_specs().items()}

    def Dims(self) -> dict[str, int]:
        """``{도메인: 채널 수}`` — 계약의 ``shape`` 이 답한다(표본을 안 연다)."""
        return {_d: max(int(np.prod(_o.get("shape") or [1])), 1)
                for _d, _o in self._gauge_specs().items()}

    def Gauges(self) -> dict[str, tuple[str, tuple[str, ...]]]:
        """``{도메인: (원본 feature, 접기들)}`` — :meth:`Measure` 가 접을 근거."""
        return {_d: (str(_o.get("feature") or _d), tuple(_o.get("folds") or ()))
                for _d, _o in self._gauge_specs().items()}

    def Declared(self) -> list[str]:
        """config ``gauges:`` 에 **사람이 적은** 잣대만 (정렬). 없으면 빈 목록.

        안 적은 feature 가 자동으로 받는 항등 잣대와 가른다. 계산은 같지만 **기본으로 켤지**가
        다르다 — config 에 적은 것이 곧 "이걸로 보겠다" 는 선언이다. 옛 계약(이 표시가 없는 것)은
        빈 목록을 내므로 화면이 "구분 근거가 없다" 로 읽고 전부 켠다.
        """
        return sorted(_d for _d, _o in self._gauge_specs().items() if _o.get("declared"))

    def Threshold_of(self, domain: str) -> tuple[float, bool]:
        """그 도메인에 적용된 **거리 상한** ``(k, 도메인별 지정인가)``.

        화면이 "이 값이 공통값인지 이 도메인만의 값인지" 를 보여야 사용자가 무엇을 고치는지 안다.
        """
        _cfg = self.Cluster_cfg()
        return threshold_of(_cfg, domain), str(domain) in (_cfg.get("thresholds") or {})

    def Neighbors_of(self, domain: str) -> tuple[int, bool]:
        """그 도메인에 적용된 **이웃 수** ``(m, 도메인별 지정인가)`` — :meth:`Threshold_of` 와 같다."""
        _cfg = self.Cluster_cfg()
        return neighbors_of(_cfg, domain), str(domain) in (_cfg.get("neighbor_counts") or {})

    def Suggest_k(self, domain: str) -> tuple[float, float, float] | None:
        """이 축의 **최근접거리 분위수** ``(10%, 50%, 90%)`` — 없으면 None.

        좌표를 만들 때 함께 잰 값이다(:func:`~.group._scaled`). ``k`` 가 자기 최근접거리를 넘어야
        그 표본이 이웃 하나라도 갖게 되므로 **``k = 90%`` 면 표본의 90% 가 최소한 하나와 이어진다** —
        배정률의 하한이 그 값이다. 순도는 별개라 사람이 올려 보며 정한다.

        단위가 **정규화 방법을 탄다** — 방법을 바꾸면 다시 재야 한다(``norm`` 에서 ``nn`` 을 지운다).
        """
        _nn = (self.Norm().get(str(domain)) or {}).get("nn")
        return (float(_nn[0]), float(_nn[1]), float(_nn[2])) if _nn and len(_nn) == 3 else None

    def Welds_of(self, domain: str) -> tuple[bool, bool]:
        """그 축의 **병합 허용** ``(켰나, 도메인별 지정인가)`` — :meth:`Threshold_of` 와 같다."""
        _cfg = self.Cluster_cfg()
        return welds_of(_cfg, domain), str(domain) in (_cfg.get("weld_axes") or {})

    # ── 묻기 — 저장된 index·stats 위에서. 전수를 안 읽는다 ────────────────────────
    def _grouped(self) -> dict[str, dict[int, list[str]]]:
        """``{도메인: {type: [key, …]}}`` — index 를 **한 번** 묶어 둔다.

        조회마다 6만을 훑으면 O(n) 이 반복돼 화면 한 장이 초 단위가 된다. 묶음은 ``Set_index``
        가 지운다. 안 붙은 표본(:data:`~.cluster.POOL`)도 자기 자리에 들어간다 — 그것도 읽을 대상이다.
        """
        if _GROUPED not in self._memo:
            _out: dict[str, dict[int, list[str]]] = {}
            for _k, _rec in self.Index().items():
                for _d, _t in (_rec.get("types") or {}).items():
                    _out.setdefault(str(_d), {}).setdefault(int(_t), []).append(_k)
            _joint = self.Joint().get("assign")
            if _joint is not None:                      # 종합은 자기 장부에서
                for _k, _t in _joint.items():
                    _out.setdefault(JOINT, {}).setdefault(int(_t), []).append(str(_k))
                # **장부에 없는 것이 곧 보류다.** 축은 `index.types` 에 `POOL` 을 적어 두지만 종합
                # 장부는 배정된 것만 든다 — 여기서 채우지 않으면 `Composition` 은 8,934건이라 하고
                # `Keys` 는 0건이 되어, 화면이 "수는 있는데 열면 비었다" 가 된다.
                _out.setdefault(JOINT, {})[POOL] = [_k for _k in self.Index()
                                                    if _k not in _joint]
            self._memo[_GROUPED] = _out
        return self._memo[_GROUPED]

    def Types(self, domain: str) -> int:
        """그 도메인의 type 수 (통계가 진실이다). 종합은 좌표표가 진실이다."""
        if str(domain) == JOINT:
            return len(self.Joint_coords()[1])
        return self.Type_stats(domain).count

    # ── 종합 — **자기 장부**를 든다 (index 와 별도) ──────────────────────────────
    def Set_joint(self, axes: list[str], members: list[dict[str, list[int]]],
                  assign: dict[str, int], imputed: dict[str, dict[str, int]]) -> None:
        """종합 판정을 한 장으로 앉힌다 — 배정·구성·**메운 자리**.

        ``index.types`` 에 안 섞는다. 거기 있는 것은 잣대가 **문턱을 넘어 인정한** 값이라, 다른 축을
        참고해 추정한 값(``imputed``)을 같이 두면 축 화면이 자기가 모른다고 한 것을 아는 척하게 된다.
        수명도 다르다 — 축을 다시 가르면 종합은 통째로 다시 나온다.

        Args:
            axes: 곱한 축 이름 (순서 고정).
            members: 종합 type 별 ``{축: [그 type 의 축 type]}``.
            assign: ``{key: 종합 type}`` — 보류는 담지 않는다(없으면 보류).
            imputed: ``{key: {축: 메워 넣은 type}}`` — 측정이 아니라 **추정**인 자리만.
        """
        self._put(JOINT_P, _JSON, {"axes": list(axes),
                                   "members": [dict(_m) for _m in members],
                                   "assign": {str(_k): int(_v) for _k, _v in assign.items()},
                                   "imputed": {str(_k): dict(_v) for _k, _v in imputed.items()}})

    def Joint(self) -> dict:
        """종합 장부 그대로 (없으면 빈 dict)."""
        return dict(self._param(JOINT_P) or {})

    def Joint_coords(self) -> tuple[list[str], list[dict[str, list[int]]]]:
        """``(축 이름, [종합 type 별 {축: 품은 type 들}])`` — 종합 type 이 **무엇으로 이뤄졌나**.

        번호만 보면 "이 둘이 왜 다른가" 를 못 읽는다. 구성을 나란히 놓으면 보인다 —
        ``{outline: [3], signed: [7]}`` 과 ``{outline: [3], signed: [9]}`` 는 signed 만 다르다.
        """
        _raw = self.Joint()
        _axes = list(_raw.get("axes") or [])
        return _axes, [{_d: [int(_v) for _v in _m.get(_d, [])] for _d in _axes}
                       for _m in (_raw.get("members") or [])]

    def Joint_axis_of(self, type_id: int) -> dict[str, list[int]]:
        """종합 type 하나의 ``{축: 축 type}`` (범위 밖이면 ``{}``)."""
        _axes, _members = self.Joint_coords()
        _i = int(type_id)
        return _members[_i] if 0 <= _i < len(_members) else {}

    def Joint_imputed(self, key: str) -> dict[str, int]:
        """그 표본이 종합에서 **메워 넣은** 축 label ``{축: type}`` (없으면 ``{}``).

        잣대는 그 축에 대해 기권했는데 다른 축을 참고해 추정한 자리다. 화면이 측정값과 갈라 보여야
        사람이 그 판정을 얼마나 믿을지 정한다.
        """
        return dict((self.Joint().get("imputed") or {}).get(str(key)) or {})

    def Keys(self, domain: str, type_id: int | None = None) -> list[str]:
        """그 ``(도메인[, type])`` 의 item key — 멤버십은 index 가 든다(명단을 안 든다).

        ``type_id`` 를 :data:`~.cluster.POOL` 로 주면 **안 붙은 표본**이 나온다.
        """
        _by_type = self._grouped().get(str(domain), {})
        if type_id is not None:
            return sorted(_by_type.get(int(type_id), []))
        return sorted(_k for _t, _v in _by_type.items() if _t >= 0 for _k in _v)

    def Keys_of_class(self, class_name: str) -> list[str]:
        """그 class 의 item key — **배정과 무관하다**(보류도 든다).

        :meth:`Keys` 의 class 판 이다. 축이 아니라 라벨로 묶는 물음("이 번호가 원래 어떻게 생겼나")
        이 있고, 그 답은 어느 type 에 앉았는지와 상관이 없다 — 안 앉은 표본도 그 class 의 모습이다.

        :meth:`_grouped` 와 같은 이유로 **한 번 묶어 둔다** — 6만을 조회마다 훑으면 화면이 멈춘다.
        """
        if _BY_CLASS not in self._memo:
            _out: dict[str, list[str]] = {}
            for _k, _rec in self.Index().items():
                _out.setdefault(str(_rec.get("class", "")), []).append(_k)
            self._memo[_BY_CLASS] = _out
        return sorted(self._memo[_BY_CLASS].get(str(class_name), []))

    def Counts(self, domain: str) -> np.ndarray:
        """type 별 구성원 수 ``(M,)`` — 통계의 ``n`` 그대로 (index 와 어긋나면 통계가 진실).

        종합은 통계가 없으므로 index 를 센다.
        """
        if str(domain) == JOINT:
            _by = self._grouped().get(JOINT, {})
            return np.asarray([len(_by.get(_t, [])) for _t in range(self.Types(JOINT))], np.int64)
        return self.Type_stats(domain).n.astype(np.int64)

    def Classes(self, state: str | None = None) -> list[str]:
        """index 에 있는 class (이름 오름차순). ``state`` 를 주면 그 상태만."""
        return sorted({str(_r.get("class", "")) for _r in self.Index().values()
                       if state is None or str(_r.get("state", "")) == str(state)})

    # ── 구성 — 두 축이 이 표 하나에서 읽힌다 ─────────────────────────────────────
    def Composition(self, domain: str, state: str | None = None) -> dict[int, Counter]:
        """``{type: {class: 개수}}`` — **저장하지 않는다**. index 를 접으면 나온다.

        읽는 방향이 셋이고 전부 이 표에서 나온다:

        - 한 type 에 여러 class → 그 class 들은 이 데이터로 안 갈린다
        - 한 class 가 여러 type → 그 class 안에 다른 모양이 있다
        - 자기 class 가 소수인 type 의 표본 → 옮길 후보

        **"여러 class" 를 그대로 "안 갈림" 으로 읽으면 안 된다.** 작은 class 가 큰 class 안에
        들어앉은 형태는 구(球)로 못 가르므로 같은 type 에 들어오는데, 국소로는 갈린다(실측
        ``c151+c153`` 은 어느 ``k`` 에서도 한 type 인데 쌍별 1-NN 은 85%). type **안에서** 한 번
        더 재야 "정말 안 갈림" 과 "블롭이 굵어서" 가 구분된다.

        Args:
            domain: 도메인.
            state: 그 상태의 표본만 (``None`` 이면 전부).

        Returns:
            ``{type: Counter({class: 개수}})`` — 안 붙은 표본은 :data:`~.cluster.POOL` 자리에.
        """
        def _make() -> dict[int, Counter]:
            _joint = (self.Joint().get("assign") or {}) if str(domain) == JOINT else None
            _out: dict[int, Counter] = {}
            for _k, _rec in self.Index().items():
                if state is not None and str(_rec.get("state", "")) != str(state):
                    continue
                _t = (int(_joint.get(_k, POOL)) if _joint is not None
                      else int((_rec.get("types") or {}).get(str(domain), POOL)))
                _out.setdefault(_t, Counter())[str(_rec.get("class", ""))] += 1
            return _out
        return self._derived(("comp", domain, state), _make)

    def Distances(self, domain: str) -> dict[str, float]:
        """``{key: 중심까지 거리}`` — **outlier 를 이 값으로 읽는다**(플래그가 없다).

        큰 값 = 억지로 가까운 type 에 놓였을 뿐 제자리가 아니다. 안 붙은 표본은 ``inf``.
        """
        if str(domain) == JOINT:                 # 종합엔 좌표가 없어 중심까지 거리라는 게 없다
            return dict.fromkeys(self.Index(), float("inf"))
        return {_k: float((_r.get("dists") or {}).get(str(domain), np.inf))
                for _k, _r in self.Index().items()}

    # ── 중심끼리 — 해상도는 조회 시점에 계산한다 ────────────────────────────────
    def Centers(self, domain: str) -> np.ndarray:
        """type 별 중심 ``(M, D)`` — **읽기 전용**(캐시된 배열이다)."""
        return self._derived(("centers", domain), lambda: centers(self.Type_stats(domain)))

    def Radii(self, domain: str) -> np.ndarray:
        """type 별 RMS 반경 ``(M,)`` — 거리와 같은 축척."""
        return self._derived(("radii", domain), lambda: radii(self.Type_stats(domain)))

    def Resolution(self, domain: str, k: float) -> np.ndarray:
        """``k`` 해상도에서의 type 묶음 ``(M,)`` — 같은 번호면 그 해상도에서 안 갈린다.

        **저장하지 않는다.** 중심이 이미 있으니 조회 시점에 센다 — 그래서 ``k`` 를 키워 가며
        훑는 것이 재군집 없이 즉시 된다.

        **묶는 규칙이 가르는 규칙과 같다** (:func:`~.cluster.type_neighbors` — 상호 최근접 + ``k``).
        이 값이 답하는 물음이 "더 거친 ``k`` 로 **다시 가르면** 뭐가 나오나" 라서다. 한때 여기만
        ``d ≤ k`` 전체 쌍으로 묶었는데, 그건 어떤 ``k`` 로도 안 나오는 묶음이었다 — 실측
        ``radial_signed`` 에서 화면이 그리는 쌍의 84%가 판정이 안 쓴 쌍이었다.

        **포화한다** — 상호성이 걸려 있어 ``k`` 를 키워도 새 이웃이 안 생기는 지점이 온다(실측
        ``radial_signed`` 는 10그룹에서 멈춘다). 그게 고장이 아니라 답이다: 그 이상은 이 데이터가
        붙여 주지 않는다. 더 붙이려면 ``k`` 가 아니라 **이웃 수**를 키워야 한다.

        **단방향이다** — 가른 ``k`` 보다 거친 쪽만 나온다. 더 잘게 보려면 재군집해야 한다.

        **종합에는 해상도가 없다** — 좌표가 없으니 중심끼리 잴 것이 없고, 종합 type 을 묶으려면
        축들을 각자의 해상도로 되묶어 다시 곱해야 한다(그건 재군집이다). 그래서 항등을 낸다.

        Raises:
            Type_explosion: type 수가 묶기 설정 ``max_axis_types`` 를 넘을 때.
        """
        if str(domain) == JOINT:
            return np.arange(self.Types(JOINT))
        _C = self.Centers(domain)
        _M = len(_C)
        _limit = int(self.Cluster_cfg().get("max_axis_types") or _MAX_TYPES)
        if _M > _limit:
            raise Type_explosion(domain, _M, _limit)
        if _M < 2:
            return np.arange(_M)
        _parent = np.arange(_M)

        def _find(_x: int) -> int:
            while _parent[_x] != _x:
                _parent[_x] = _parent[_parent[_x]]
                _x = int(_parent[_x])
            return _x

        # 간선이 **성기다**(상호 최근접이라 ``M·m`` 이 상한) — 그래서 실체화해도 안전하다.
        for _u, _v in type_neighbors(_C, float(k), self.Neighbors_of(domain)[0]):
            _a, _b = _find(int(_u)), _find(int(_v))
            if _a != _b:
                _parent[max(_a, _b)] = min(_a, _b)     # 대표는 가장 작은 번호
        _root = [_find(_i) for _i in range(_M)]
        # 번호는 **자리 순서**다 — 슬라이더 왼쪽 끝에서 갈래 번호가 type 번호와 같아야 트리의
        # ``#12`` 와 그래프 라벨 ``12`` 를 눈으로 잇는다.
        _seat = {_r: _i for _i, _r in enumerate(sorted(set(_root)))}
        return np.asarray([_seat[_r] for _r in _root], int)

    # ── 쓰기 — class 이동은 index 한 줄이다 ──────────────────────────────────────
    def Set_assignment(self, domain: str, types: dict[str, int], dists: dict[str, float]) -> None:
        """그 도메인의 배정을 index 에 쓴다 — ``{key: type}`` · ``{key: 거리}``.

        도메인마다 따로 쓴다. 다른 도메인의 배정은 안 건드린다(직교라 함께 움직일 이유가 없다).
        """
        _index = self.Index()
        for _k, _t in types.items():
            if _k not in _index:
                continue
            _index[_k].setdefault("types", {})[str(domain)] = int(_t)
            _index[_k].setdefault("dists", {})[str(domain)] = float(dists.get(_k, np.inf))
        self.Set_index(_index)
