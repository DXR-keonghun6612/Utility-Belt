"""잣대 — **정본이 든 표본 벡터를 무엇으로 접어 비교하나.**

이 층이 답하는 물음은 하나다: **무엇을 읽어 무엇으로 재는가.** 그 답을 산문이 아니라
:class:`Extract_Spec` 값으로 든다 — 그래서 소비처가 "도메인이 뭐가 있나"를 알려고 저장 파일을 열
필요가 없다(옛 구현은 첫 표본 npz 를 열어 도메인을 배웠다).

## 여기는 계산하지 않는다

표본 하나의 값은 **flow 가 만들어 정본에 넣는다**(``process/stream/mask/profile.py``). 한때 이 모듈이
마스크를 태워 뽑았는데(``Mask_Geometry``), 그러면 같은 계산이 flow 와 분석 두 곳에 있고 **분석을
돌려야만 값이 생겼다.** 지금 만들기는 flow 한 곳이고 여기는 그것을 **재는 자**다.

**저장하는 것과 재는 것은 수명이 다르다.** ``radial_signed``·``radial_outline`` 은 ``radial_rle`` 를
접은 것이라 저장하면 같은 정보가 표본마다 파일 셋이 된다. 계약은 둘을 갈라 든다 — feature 를 고치면
**flow 를 다시 돌려야** 하고, 잣대를 고치면 **다시 접기만** 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from python_toolbox.file import Read_from
from torch_toolbox.modules.transform.mask.geometry import RADIAL_FOLDS

from ..constant import TO_STORAGE
from .cluster import JOINT

#: 도메인의 **성질** — 소비처가 거리 방식을 고른다 (torch_toolbox 와 같은 어휘).
FEATURE = "feature"      # 순서 없음 — 유클리드
TOKEN   = "token"        # 순서 있음 — 회전 정합

#: 정본이 그 값을 무엇으로 드는가 — stem 당 npy 한 장. 계약이 적어 두는 그릇이다(여기가 쓰지는 않는다).
ARRAY_SPEC: dict[str, Any] = {"to": TO_STORAGE, "type": "array", "format": "npy"}

@dataclass(frozen=True)
class Feature_Spec:
    """**저장하는 것** 하나의 계약 — 정본에서 뽑아 디스크에 남는다.

    Attributes:
        shape: 표본 하나치 native shape (scalar ``(dim,)`` · sequence ``(NT, K)``).
        spec: 그 값이 정본에 앉은 그릇 (:data:`ARRAY_SPEC`).
    """

    shape: tuple[int, ...]
    spec:  dict = field(default_factory=lambda: dict(ARRAY_SPEC))


@dataclass(frozen=True)
class Gauge_Spec:
    """도메인 하나의 **잣대** — 그 도메인을 무엇으로 재나. 디스크에 안 남는다.

    표본끼리의 거리를 여기서 재고 type 을 여기서 가른다. 반경 ``k`` 는 이 잣대의 눈금이다.
    **도메인마다 하나**라 잣대 이름이 곧 도메인 이름이다.

    Attributes:
        kind: :data:`FEATURE` | :data:`TOKEN`.
        shape: 접은 뒤 표본 하나치 shape.
        feature: 접을 원본 feature 이름.
        folds: ``RADIAL_FOLDS`` 의 key 들 — **마지막 축으로 쌓인다**. 비면 feature 그대로.
        declared: config ``gauges:`` 에 **사람이 적은** 잣대인가. 안 적은 feature 가 자동으로 받는
            항등 잣대와 가른다 — 계산은 같지만 **기본으로 켤지**가 다르다. config 에 적었다는 것이
            곧 "이걸로 보겠다" 는 선언이고, 항등 잣대는 그런 선언 없이 딸려 온 것이다.
    """

    kind:     str
    shape:    tuple[int, ...]
    feature:  str
    folds:    tuple[str, ...] = ()
    declared: bool = False


def Fold(folds, base: np.ndarray, *, batched: bool = False) -> np.ndarray:
    """feature 값을 접어 **잣대** 값을 낸다.

    접기가 여럿이면 **마지막 축으로 쌓는다** — 그것이 잣대의 채널이 된다. ``radial_rle`` ``(NT, 8)``
    을 ``["signed", "outline"]`` 로 접으면 ``(NT, 2)`` 다. 둘 다 px 반경이라 한 도메인의 채널로
    성립하고(도메인 = scale 공유 채널 묶음), 슬롯 배치가 사라져 광선이 구멍을 스칠 때 밴드가 하나
    늘며 값이 계단으로 뛰는 자리도 없다.

    접는 식은 ``torch_toolbox`` 의 ``RADIAL_FOLDS`` 가 소유한다 — 여기서 다시 적으면 추출이 쓰는
    식과 되읽기가 쓰는 식이 갈라져 **같은 이름의 잣대가 두 값을 갖는다**.

    Args:
        folds: 접기 이름들 (:attr:`Gauge_Spec.folds`). 비면 입력 그대로.
        base: 원본 feature 값. ``batched`` 면 첫 축이 배치, 아니면 표본 하나치.
        batched: 첫 축이 배치인가. 전수 적재가 **표본마다 torch 를 왕복하지 않게** 여는 문이다
            (6만 표본이면 그 왕복이 적재보다 비싸진다). 값은 어느 쪽이든 같다.

    Returns:
        접힌 값 — 입력과 같은 배치 여부.

    Raises:
        KeyError: 모르는 접기 이름.
    """
    _a = np.asarray(base)
    if not folds:
        return _a
    _t = torch.as_tensor(_a.astype(np.float32))
    _vals = [RADIAL_FOLDS[_f](_t if batched else _t[None]).numpy() for _f in folds]
    _out = _vals[0] if len(_vals) == 1 else np.stack(_vals, -1)
    return _out if batched else _out[0]


@dataclass(frozen=True)
class Extract_Spec:
    """추출기의 계약 — **저장하는 것**(feature)과 **재는 것**(잣대)을 갈라서 든다.

    둘은 수명이 다르다. feature 는 정본에서 뽑은 것이라 고치면 **재추출**이고, 잣대는 그 feature 를
    접은 것이라 바꿔도 추출이 안 돈다 — 그래서 한 목록에 담으면 안 된다. 옛 구현은 둘을 ``outputs``
    하나에 담아 "이 추출기가 무엇을 저장하나" 와 "무엇으로 가를 수 있나" 가 같은 물음처럼 보였다.

    **잣대는 도메인마다 하나**라 :meth:`Domains` 가 곧 잣대 목록이다 — 위 계층(store·화면)은 잣대를
    도메인 이름으로만 만나고, 그것이 접어서 나온 값이라는 사실은 여기서 닫힌다.

    Attributes:
        inputs: ``Extract`` 가 요구하는 이름들 (= ``INPUTS``). 정본 leaf 이름과 어떻게 잇는지는
            ``input_slots`` 가 정한다 — 계약은 **무엇이 필요한가**만 말한다.
        features: ``{feature: Feature_Spec}`` — 디스크에 남는 것.
        gauges: ``{도메인: Gauge_Spec}`` — 가르기가 도는 단위.
    """

    inputs:   tuple[str, ...]
    features: dict[str, Feature_Spec]
    gauges:   dict[str, Gauge_Spec]

    def Feature_names(self) -> list[str]:
        """저장 feature 이름 (정렬)."""
        return sorted(self.features)

    def Domains(self) -> list[str]:
        """도메인(= 잣대) 이름 (정렬) — 소비처가 저장 파일을 열지 않고 아는 목록."""
        return sorted(self.gauges)

    def Measure(self, features: dict[str, Any]) -> dict[str, np.ndarray]:
        """저장 feature 값들 → **잣대로 잰 값들** ``{도메인: 값}``. 원본이 없는 잣대는 뺀다.

        적재(정규화 상수)와 되읽기가 같은 식을 타게 하는 자리다.
        """
        return {_d: Fold(_o.folds, np.asarray(features[_o.feature]))
                for _d, _o in self.gauges.items() if features.get(_o.feature) is not None}

    def Measure_batch(self, rows: np.ndarray, feature: str = "") -> dict[str, np.ndarray]:
        """표본 **여럿** ``(N, …)`` → 잣대 값들 ``{도메인: (N, …)}``.

        묶음 하나를 통째로 접는 자리다 — 표본마다 접으면 6만 번 torch 를 왕복해 접기가 적재보다
        비싸진다(:func:`Fold` 의 ``batched``).

        Args:
            rows: 그 feature 의 표본 배치 ``(N, …)``.
            feature: 이 배치가 어느 feature 인지. 비면 **feature 가 하나뿐일 때만** 그것으로 본다.

        Raises:
            ValueError: ``feature`` 를 안 줬는데 feature 가 여럿일 때 (어느 것인지 추측하지 않는다).
        """
        _f = feature
        if not _f:
            if len(self.features) != 1:
                raise ValueError(
                    f"feature 가 여럿이라 어느 배치인지 알 수 없다: {self.Feature_names()}")
            _f = next(iter(self.features))
        _a = np.asarray(rows)
        return {_d: Fold(_o.folds, _a, batched=True)
                for _d, _o in self.gauges.items() if _o.feature == _f}




def Read_config(config_path: str | Path) -> dict:
    """분석 config yaml → ``{modules, gauges}``.

    Raises:
        FileNotFoundError: 못 읽을 때.
    """
    _ok, _meta = Read_from(Path(config_path))
    if not _ok or not isinstance(_meta, dict):
        raise FileNotFoundError(f"분석 config 읽기 실패: {config_path}")
    return _meta if "modules" in _meta or "gauges" in _meta else {"modules": _meta}


def Contract(config_path: str | Path, feature: str, shape: tuple[int, ...]) -> Extract_Spec:
    """config 의 ``gauges:`` + 정본이 든 feature 모양 → 계약. **마스크를 안 태운다.**

    옛 구현은 8×8 더미 마스크를 사슬에 흘려 shape 을 쟀다 — 계산이 여기 있었기 때문이다. 지금은
    정본이 그 배열을 이미 들고 있으므로 모양을 **읽어서** 안다(``params/profile_spec`` 또는 배열
    자체). 그래서 계약을 세우는 데 torch 가 필요 없다.

    잣대를 안 적은 feature 는 **자기 이름의 항등 잣대**를 갖는다 — 접을 것이 없는 값(스칼라 도메인)에
    config 줄을 쓰게 하지 않는다.

    Args:
        config_path: 분석 config(yaml) — ``gauges:`` 블록을 읽는다.
        feature: 정본이 든 feature 이름 (``radial_rle``).
        shape: 표본 하나치 모양 ``(NT, K)``.

    Returns:
        :class:`Extract_Spec` — ``features`` 는 정본이 든 것, ``gauges`` 는 config 가 고른 것.

    Raises:
        KeyError: 잣대가 없는 feature 를 가리키거나, 모르는 접기를 적었거나, 예약 이름을 썼을 때.
    """
    _meta = Read_config(config_path)
    _feats = {feature: Feature_Spec(shape=tuple(shape), spec=dict(ARRAY_SPEC))}
    _gauges, _folded = {}, set()
    for _name, _g in (_meta.get("gauges") or {}).items():
        _name = str(_name)
        if _name == JOINT:
            raise KeyError(f"잣대 이름 '{JOINT}' 는 **종합 판정**의 자리라 못 쓴다 "
                           f"(축들의 곱집합 — `cluster.JOINT`)")
        if not isinstance(_g, dict) or "feature" not in _g:
            raise KeyError(f"잣대 '{_name}' 에 'feature' 가 없다 (config: gauges)")
        _src = str(_g["feature"])
        if _src not in _feats:
            raise KeyError(f"잣대 '{_name}' 의 feature '{_src}' 가 없다 "
                           f"(정본이 든 것: {sorted(_feats)})")
        _folds = tuple(_g.get("folds") or ())
        _bad = [_f for _f in _folds if _f not in RADIAL_FOLDS]
        if _bad:
            raise KeyError(f"잣대 '{_name}' 의 모르는 접기 {_bad} "
                           f"(가능: {sorted(RADIAL_FOLDS)})")
        # 접은 뒤 모양은 **한 표본을 실제로 접어** 잰다 — 접기마다 축이 어떻게 줄어드는지는
        # ``RADIAL_FOLDS`` 가 아는 것이라 여기서 규칙을 다시 적으면 갈린다.
        _gauges[_name] = Gauge_Spec(kind=TOKEN, feature=_src, folds=_folds, declared=True,
                                    shape=tuple(Fold(_folds, np.zeros(shape, np.float32)).shape))
        _folded.add(_src)
    for _f, _o in _feats.items():                          # 안 적힌 feature — 항등 잣대
        if _f not in _folded and _f not in _gauges:
            _gauges[_f] = Gauge_Spec(kind=TOKEN, shape=_o.shape, feature=_f)
    return Extract_Spec(inputs=(feature,), features=_feats, gauges=_gauges)
