"""① 추출 — **정본 데이터 하나 → 도메인별 feature dict.** (진입점 아님 — `pipeline` 이 부른다)

이 층이 답하는 물음은 하나다: **무엇을 넣으면 무엇이 나오는가.** 그 답을 산문이 아니라
:class:`Extract_Spec` 값으로 든다 — 그래서 소비처가 "도메인이 뭐가 있나"를 알려고 저장 파일을 열
필요가 없다(옛 구현은 첫 표본 npz 를 열어 도메인을 배웠다).

계약 모양은 [`../process/_base.py`](../process/_base.py) 의 ``Base_Process`` 를 그대로 따른다 —
``Extract`` 시그니처가 곧 입력 선언(``INPUTS`` 자동추출), ``input_slots`` 가 ctx 키 → 파라미터 별칭,
출력은 라우팅 spec 을 든다. 언젠가 둘을 한 계약으로 합칠 때 재설계가 아니라 개명이 되게 하려는 것이다.

**다른 점 하나** — ``OUTPUTS`` 가 ClassVar 가 아니라 인스턴스가 답한다(:meth:`Base_Extractor.Spec`).
어떤 도메인이 나오는가가 **config 에 달렸기 때문이다**(descriptor 목록이 바뀌면 도메인이 바뀐다).
클래스에 못박으면 config 를 바꿀 때마다 클래스를 고쳐야 한다.

**도메인은 저장과 파생으로 갈린다.** ``radial_signed`` · ``radial_outline`` 은 ``radial_rle`` 를 접은
것이라 저장하면 같은 정보가 표본마다 파일 셋이 된다. 계약은 셋을 다 선언하고(쓰는 쪽에는 똑같이
"그 표본의 도메인 값"이다) 그릇은 원본에만 준다 — :meth:`Extract_Spec.Route_specs` 와
:meth:`Extract_Spec.Derived` 가 그 경계다. 되읽기가 접을 때는 :func:`Fold` 를 부른다.

지금 구현체는 :class:`Mask_Geometry` 하나뿐이다. **ABC 도 레지스트리도 안 만든다** — 구현이 하나인데
추상 기반을 깔면 0줄짜리 층이 남는다(전에 `cohort/centroid` 가 그랬다). 둘째 구현이 생기면 그때 세운다.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import torch

from python_toolbox.file import Read_from
from torch_toolbox import CFGS
from torch_toolbox.modules import MODELS
from torch_toolbox.modules.build import Build_from_registry
# 등록 부작용 — crop/resize/geometry 및 그 descriptor 를 CFGS/MODELS 에 올린다.
import torch_toolbox.modules.transform.mask.silhouette   # noqa: F401
from torch_toolbox.modules.transform.mask.geometry import RADIAL_FOLDS

from ..constant import TO_META, TO_STORAGE
from .cluster import JOINT

#: 도메인의 **성질** — 소비처가 거리 방식을 고른다 (torch_toolbox 와 같은 어휘).
FEATURE = "feature"      # 순서 없음 — 유클리드
TOKEN   = "token"        # 순서 있음 — 회전 정합

#: 인라인으로 담을 원소 수 상한. 실측: scalar 도메인 다섯이 합쳐 23 개(size 7·ratio 6·moment 6·
#: position 2·area 2), ``radial_rle`` 하나가 4096 개다. 앞의 다섯을 파일로 내면 표본마다 파일이 여섯이라
#: 6만 표본에 30만 파일이 되고, 뒤의 하나를 인라인으로 넣으면 사이드카가 표본당 40 KB 가 된다.
#: 그 사이 어디를 갈라도 결과가 같은 만큼 간격이 크다.
_INLINE_MAX = 64

#: 그릇 둘 — 사이드카 인라인 / kind-major npy 파일.
INLINE_SPEC: dict[str, Any] = {"to": TO_META}
ARRAY_SPEC:  dict[str, Any] = {"to": TO_STORAGE, "type": "array", "format": "npy"}

@dataclass(frozen=True)
class Feature_Spec:
    """**저장하는 것** 하나의 계약 — 정본에서 뽑아 디스크에 남는다.

    Attributes:
        shape: 표본 하나치 native shape (scalar ``(dim,)`` · sequence ``(NT, K)``).
        spec: 라우팅 spec — :data:`INLINE_SPEC` 또는 :data:`ARRAY_SPEC`.
    """

    shape: tuple[int, ...]
    spec:  dict = field(default_factory=lambda: dict(ARRAY_SPEC))

    @property
    def inline(self) -> bool:
        """사이드카 인라인인가 (아니면 파일)."""
        return self.spec.get("to", TO_META) == TO_META


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


def Fold(folds, base: np.ndarray) -> np.ndarray:
    """feature 값 하나를 접어 **잣대** 값을 낸다 (배치축 없음).

    접기가 여럿이면 **마지막 축으로 쌓는다** — 그것이 잣대의 채널이 된다. ``radial_rle`` ``(NT, 8)``
    을 ``["signed", "outline"]`` 로 접으면 ``(NT, 2)`` 다. 둘 다 px 반경이라 한 도메인의 채널로
    성립하고(도메인 = scale 공유 채널 묶음), 슬롯 배치가 사라져 광선이 구멍을 스칠 때 밴드가 하나
    늘며 값이 계단으로 뛰는 자리도 없다.

    접는 식은 ``torch_toolbox`` 의 ``RADIAL_FOLDS`` 가 소유한다 — 여기서 다시 적으면 추출이 쓰는
    식과 되읽기가 쓰는 식이 갈라져 **같은 이름의 잣대가 두 값을 갖는다**.

    Args:
        folds: 접기 이름들 (:attr:`Gauge_Spec.folds`). 비면 입력 그대로.
        base: 원본 feature 값 — 표본 하나치.

    Returns:
        접힌 값 (표본 하나치).

    Raises:
        KeyError: 모르는 접기 이름.
    """
    _a = np.asarray(base)
    if not folds:
        return _a
    _t = torch.as_tensor(_a.astype(np.float32))[None]
    _vals = [RADIAL_FOLDS[_f](_t)[0].numpy() for _f in folds]
    return _vals[0] if len(_vals) == 1 else np.stack(_vals, -1)


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

    def Route_specs(self) -> dict[str, dict]:
        """``{feature: 라우팅 spec}`` — ``Put_features`` 에 그대로 넘어간다."""
        return {_f: dict(_o.spec) for _f, _o in self.features.items()}

    def Measure(self, features: dict[str, Any]) -> dict[str, np.ndarray]:
        """저장 feature 값들 → **잣대로 잰 값들** ``{도메인: 값}``. 원본이 없는 잣대는 뺀다.

        적재(정규화 상수)와 되읽기가 같은 식을 타게 하는 자리다.
        """
        return {_d: Fold(_o.folds, np.asarray(features[_o.feature]))
                for _d, _o in self.gauges.items() if features.get(_o.feature) is not None}


def _extract_inputs(call_fn) -> tuple[str, ...]:
    """``Extract`` 시그니처 → 입력 이름들 (``Base_Process._extract_inputs`` 와 같은 규칙)."""
    return tuple(
        _name for _name, _p in inspect.signature(call_fn).parameters.items()
        if _name != "self"
        and _p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD))


class Base_Extractor:
    """추출기 베이스 — 계약 프레임만 든다 (계산은 ``Extract``).

    서브클래스는 ``Extract`` 를 구현하고 :meth:`Spec` 이 낼 ``features``·``gauges`` 를 채운다.
    ``__call__`` 이 베이스가 소유하는 계약 프레임이다 — 입력 별칭 remap → ``Extract`` → 선언된
    feature 검증 → 인라인 그릇 맞추기.
    """

    INPUTS: ClassVar[tuple[str, ...]] = ()
    #: ctx 키 → ``Extract`` 파라미터 별칭 (``Base_Process.input_slots`` 의 대칭). 기본 = 이름 그대로.
    input_slots: ClassVar[dict[str, str]] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls.INPUTS = _extract_inputs(cls.Extract)

    def Spec(self) -> Extract_Spec:            # 계약 — 서브클래스가 구현
        raise NotImplementedError

    def Extract(self, *args, **kwargs) -> dict:  # 계산 — 서브클래스가 구현
        raise NotImplementedError

    def __call__(self, **kwargs) -> dict[str, Any]:
        """계약 프레임 — remap → ``Extract`` → feature 검증 → 인라인 그릇 맞추기.

        **빈 dict = 이 표본 스킵** (``Base_Process`` 와 같은 관례) — 대상이 아닌 입력(빈 mask 등)을
        추출기가 그렇게 말한다. 그 외에는 선언되지 않은 feature 가 나오거나 선언된 feature 가 빠지면
        **실패한다** — 계약이 값과 어긋나면 소비처가 조용히 빈 값을 보게 되고, 그러면 군집이 말없이
        다른 좌표계에서 돈다.

        Returns:
            ``{feature: 값}`` — **잣대가 아니라 feature 다.** 재는 것은 :meth:`Extract_Spec.Measure`
            가 따로 한다. 여기서 미리 접으면 저장할 것과 잴 것이 한 dict 에 섞인다.

        Raises:
            KeyError: ``Extract`` 출력이 계약과 다를 때.
        """
        if self.input_slots:
            kwargs = {**kwargs, **{_p: kwargs.get(_k) for _p, _k in self.input_slots.items()}}
        _out = self.Extract(**{_k: kwargs[_k] for _k in self.INPUTS})
        if not _out:                                        # 대상 아님 — 스킵
            return {}
        _spec = self.Spec()
        _diff = set(_spec.features) ^ set(_out)
        if _diff:
            raise KeyError(f"{type(self).__name__}: 계약과 다른 출력 {sorted(_diff)} "
                           f"(계약 {_spec.Feature_names()} / 실제 {sorted(_out)})")
        return {_f: (np.asarray(_v).tolist() if _spec.features[_f].inline else np.asarray(_v))
                for _f, _v in _out.items()}


class Mask_Geometry(Base_Extractor):
    """**이진 mask 하나 → geometry 도메인별 feature.** 지금 유일한 구현체.

    조립(crop → resize → geometry)을 여기가 소유한다 — transform 은 재사용 가능한 등록 모듈의 저장소일
    뿐이고 순서 잇기는 쓰는 쪽 일이다. 옛 ``Transform_Bundle`` 이 그 배선을 들고 있었는데, 배선 말고도
    학습 헤더용 표면(``Tokens``·``token_dim``·``token_groups``·``Occupancy_grid``)을 함께 노출하느라
    용접 클래스가 됐다 — 그 넷은 레포 전체에 소비처가 없어 걷었다.

    config 스키마 (top-level 용접 모듈 없음)::

        modules:
          crop:     {config_type: center_crop_Config, object_type: center_crop, crop_size: 280}
          resize:   {config_type: resize_binarize_Config, object_type: resize_binarize, ...}
          geometry: {config_type: geometry_embedding_Config, object_type: geometry_embedding, ...}

    학습·평가가 같은 파일을 읽어 조립하므로 전처리가 단일 출처다.
    """

    #: 조립 순서 — config 가 나열해야 하는 모듈. 다른 추출기는 다른 목록을 든다.
    MODULES: ClassVar[tuple[str, ...]] = ("crop", "resize", "geometry")

    def __init__(self, config_path: str | Path, device: str = "cpu") -> None:
        """Args:
            config_path: 공유 transform config(yaml).
            device: 모델을 올릴 device. 입력도 여기서 만들므로 불일치가 생길 자리가 없다.

        Raises:
            FileNotFoundError: config 를 못 읽을 때.
            KeyError: config 에 :attr:`MODULES` 중 빠진 것이 있을 때.
        """
        _meta = self._read_config(config_path)
        self._config     = dict(_meta.get("modules") or {})
        self._gauges_raw = dict(_meta.get("gauges") or {})
        self.device = device
        _built = {}
        for _key in self.MODULES:
            if _key not in self._config:
                raise KeyError(f"transform config 에 '{_key}' 모듈이 없다: {config_path}")
            _m = self._config[_key]
            _built[_key] = Build_from_registry(CFGS.Get(_m["config_type"])(**_m), MODELS)
        self.crop     = _built["crop"].to(device).eval()
        self.resize   = _built["resize"].to(device).eval()
        self.geometry = _built["geometry"].to(device).eval()
        self._spec: Extract_Spec | None = None

    # ── 계약 ────────────────────────────────────────────────────────────────────
    def Spec(self) -> Extract_Spec:
        """이 config 가 내는 계약 — **저장 feature + 도메인별 잣대** (첫 호출에 한 번 재본다).

        이름·성질은 geometry 가 알지만 **shape 은 실제로 통과시켜야 안다**. 그래서 8×8 더미 마스크
        하나를 흘려 shape 을 잰다 — 두 줄짜리 forward 한 번이고, 그 대가로 소비처가 목록을 배우려고
        저장 파일을 여는 일이 사라진다. 잣대 shape 도 같은 값을 접어 잰다.

        잣대를 안 적은 feature 는 **자기 이름의 항등 잣대**를 갖는다 — 스칼라 도메인(size·ratio…)은
        접을 것이 없으므로 config 에 여섯 줄을 적게 하지 않는다.
        """
        if self._spec is None:
            _kinds = self.geometry.domain_kinds
            _probe = np.zeros((8, 8), np.uint8)
            _probe[2:6, 2:6] = 1
            _vals = self._forward(_probe, (4, 4))
            _feats = {}
            for _f, _v in _vals.items():
                _sh = tuple(np.shape(_v))
                _inline = int(np.prod(_sh or (1,))) <= _INLINE_MAX
                _feats[_f] = Feature_Spec(shape=_sh,
                                          spec=dict(INLINE_SPEC if _inline else ARRAY_SPEC))
            _gauges, _folded = {}, set()
            for _name, _g in self._gauge_config().items():
                _src = str(_g["feature"])
                if _src not in _feats:
                    raise KeyError(f"잣대 '{_name}' 의 feature '{_src}' 가 없다 "
                                   f"(있는 것: {sorted(_feats)})")
                _folds = tuple(_g.get("folds") or ())
                _gauges[_name] = Gauge_Spec(kind=_kinds.get(_src, FEATURE),
                                            shape=tuple(Fold(_folds, _vals[_src]).shape),
                                            feature=_src, folds=_folds, declared=True)
                _folded.add(_src)
            for _f, _o in _feats.items():                  # 안 적힌 feature — 항등 잣대
                if _f not in _folded and _f not in _gauges:
                    _gauges[_f] = Gauge_Spec(kind=_kinds.get(_f, FEATURE), shape=_o.shape,
                                             feature=_f)
            self._spec = Extract_Spec(inputs=self.INPUTS, features=_feats, gauges=_gauges)
        return self._spec

    def _gauge_config(self) -> dict[str, dict]:
        """config 의 ``gauges:`` 블록 (없으면 빈 dict — 전부 항등 잣대).

        Raises:
            KeyError: 항목에 ``feature`` 가 없거나 모르는 접기를 적었을 때.
        """
        _out = {}
        for _name, _g in (self._gauges_raw or {}).items():
            if str(_name) == JOINT:
                raise KeyError(f"잣대 이름 '{JOINT}' 는 **종합 판정**의 자리라 못 쓴다 "
                               f"(축들의 곱집합 — `cluster.JOINT`)")
            if not isinstance(_g, dict) or "feature" not in _g:
                raise KeyError(f"잣대 '{_name}' 에 'feature' 가 없다 (config: gauges)")
            _bad = [_f for _f in (_g.get("folds") or ()) if _f not in RADIAL_FOLDS]
            if _bad:
                raise KeyError(f"잣대 '{_name}' 의 모르는 접기 {_bad} "
                               f"(가능: {sorted(RADIAL_FOLDS)})")
            _out[str(_name)] = _g
        return _out

    @staticmethod
    def _read_config(config_path: str | Path) -> dict:
        """config yaml → ``{modules, gauges}``.

        Raises:
            FileNotFoundError: 못 읽을 때.
        """
        _ok, _meta = Read_from(Path(config_path))
        if not _ok or not isinstance(_meta, dict):
            raise FileNotFoundError(f"transform config 읽기 실패: {config_path}")
        return _meta if "modules" in _meta else {"modules": _meta}

    # ── 계산 ────────────────────────────────────────────────────────────────────
    def Extract(self, mask: np.ndarray) -> dict[str, np.ndarray]:
        """프레임-스케일 이진 mask → 도메인별 native feature (배치축 없음).

        중심은 **이 추출기가 정한다** — mask bbox 중심이고, 이것이 학습 ``_prepare_binary`` 의 중심과
        같다. 밖에서 받지 않는 이유는 그게 mask 추출의 내부 사정이기 때문이다(다른 입력을 받는 추출기는
        중심이라는 개념 자체가 없을 수 있다).

        Args:
            mask: ``(H, W)`` 이진 배열. 비어 있으면(전부 0) ``{}``.

        Returns:
            ``{도메인: (dim,) | (NT, K)}``. 빈 mask 면 ``{}`` — 대상이 아니라는 뜻이다.
        """
        _m = np.asarray(mask)
        if not _m.any():
            return {}
        return self._forward(_m, _bbox_center(_m))

    def _forward(self, mask: np.ndarray, center: tuple[int, int]) -> dict[str, np.ndarray]:
        """crop → resize → geometry.Features, 배치축을 떼어 표본 하나치로."""
        _t = torch.from_numpy((mask > 0).astype(np.float32))[None, None].to(self.device)
        _c = torch.tensor([center], dtype=torch.long, device=self.device)
        with torch.no_grad():
            _feats = self.geometry.Features(self.resize(self.crop(_t, _c)))
        return {_d: _v[0].cpu().numpy() for _d, _v in _feats.items()}

    def Silhouette(self, mask: np.ndarray) -> np.ndarray:
        """정렬 전 정준 실루엣 (crop → resize) — 사람이 보는 중간 산출물. 판정은 안 쓴다."""
        _m = np.asarray(mask)
        _t = torch.from_numpy((_m > 0).astype(np.float32))[None, None].to(self.device)
        _c = torch.tensor([_bbox_center(_m)], dtype=torch.long, device=self.device)
        with torch.no_grad():
            return self.resize(self.crop(_t, _c))[0, 0].cpu().numpy()


def _bbox_center(mask: np.ndarray) -> tuple[int, int]:
    """이진 mask 의 bbox 중심 ``(col, row)`` — 학습 bbox 중심과 같다.

    ``Centroid_Frame`` 이 mask centroid 로 재중심하므로 이 중심의 1px 오차는 실루엣을 바꾸지 않는다
    (객체가 crop 창 안에 다 들어오는 한). 그래서 저장 bbox 대신 mask 에서 뽑아도 정합이 유지된다.
    """
    _ys, _xs = np.nonzero(mask)
    return (int((_xs.min() + _xs.max()) // 2), int((_ys.min() + _ys.max()) // 2))
