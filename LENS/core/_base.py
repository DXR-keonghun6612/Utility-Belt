"""core 기본 구조 — Pipeline(계산 오케스트레이션 binder) + 모델 풀.

``Pipeline`` 은 정본(``Dataset_Meta``)을 중심으로 **계산 단계**(Convert → Run)를 조율하고 결과를
``meta.Scatter()`` 로 영속한다. flow 시퀀스를 조립·실행하며, 무거운 prediction 모델을 **클래스 dict
풀**(``Pipeline._RESOURCE_POOL``)로 공유한다(프로세스 수명, 인스턴스 간 공유 — GUI 가 실행마다 새
바인더를 만들어도 재사용).

staging 전이·병합·내보내기(Move/Delete/Merge/Gather) 같은 **데이터 라이프사이클**은 바인더가 아니라
``data`` 계층(``store``)이 소유한다 — 호출 측(GUI 등)이 ``store.*(meta, …)`` 를 직접 부른다. Verify
(품질 검수)는 Sampling 이후로 미룬다.

진입점·경로 resolve 는 [`__init__.py`](__init__.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar

from python_toolbox.project.config import Base_Config

from .data.meta import Dataset_Meta
from .data.sample import SAMPLE_DIR, SAMPLERS, Base_Sampler, Sample_Set
from .data.converter import Base_Converter, Glob_Discover
from .process import Build_flow
from .process.model._sam3 import Sam3_runner


# ── 모델 풀 ───────────────────────────────────────────────────────────────────

# prediction 모델 빌더 — type → 빌더 클래스. registry 가 아니라 그냥 작은 dict(단순 데이터).
MODEL_BUILDERS: dict[str, Any] = {
    "sam3": Sam3_runner,
}


def _is_model_spec(value: Any) -> bool:
    """값이 ``{type: <빌더에 있는 종류>, …}`` 모델 스펙인지 — 구조만으로 판별."""
    return isinstance(value, dict) and value.get("type") in MODEL_BUILDERS


def _model_key(spec: dict) -> tuple:
    """공유 key — canonical 스펙 ``(type, 정렬 params)``. 같은 스펙이면 한 번만 빌드."""
    return (spec["type"], tuple(sorted((_k, repr(_v)) for _k, _v in spec.items() if _k != "type")))


# ── converter factory ─────────────────────────────────────────────────────────

_CONVERTERS: dict[str, type[Base_Converter]] = {
    "glob": Glob_Discover,
}


def _build_converter(cfg: dict) -> Base_Converter:
    _name   = cfg.get("object_type", "glob")
    _kwargs = {_k: _v for _k, _v in cfg.items() if _k != "object_type"}
    _cls    = _CONVERTERS.get(_name)
    if _cls is None:
        raise ValueError(f"알 수 없는 converter type: {_name!r}")
    return _cls(**_kwargs)


# ── sampler factory ─────────────────────────────────────────────────────────

def _build_sampler(cfg: dict) -> Base_Sampler:
    """sample config → task sampler 인스턴스 (converter factory 와 대칭).

    ``object_type`` 이 task(classification/detection)를 고르고, 나머지 키(``ratios``/``salt``/``unit``)는
    sampler dataclass 필드로 넘어간다.
    """
    _name   = cfg.get("object_type", "classification")
    _kwargs = {_k: _v for _k, _v in cfg.items() if _k != "object_type"}
    _cls    = SAMPLERS.get(_name)
    if _cls is None:
        raise ValueError(f"알 수 없는 sampler type: {_name!r}")
    return _cls(**_kwargs)


# ── config ────────────────────────────────────────────────────────────────────

@dataclass
class Pipeline_config(Base_Config):
    dataset_root: str  = ""
    converter:    dict = field(default_factory=dict)
    flows:        list = field(default_factory=list)   # flow 엔트리 시퀀스
    sample:       dict = field(default_factory=dict)   # 파생(Sample) 설정 — task·split ratio 등
    verify:       dict = field(default_factory=dict)


# ── Pipeline (최상위 binder) ───────────────────────────────────────────────────

class Pipeline:
    """정본(meta)을 중심으로 계산 단계(Convert → Run)를 조율하는 binder.

    생성 시 dataset_root 의 meta 를 로드(없으면 빈 meta). flow·모델은 ``Run`` 에서 lazy 조립한다.
    데이터 라이프사이클(전이·병합·내보내기)은 여기 없다 — ``data`` 계층 ``store`` 가 소유한다.
    """

    # 모델 인스턴스 풀 — 클래스 var(프로세스 수명, 인스턴스 공유). 같은 스펙은 세션당 1회만 빌드.
    _RESOURCE_POOL: ClassVar[dict[tuple, Any]] = {}

    def __init__(self, cfg: Pipeline_config) -> None:
        self.root            = Path(cfg.dataset_root)
        self._converter_cfg  = cfg.converter
        self._flow_cfgs      = cfg.flows
        self._sample_cfg     = cfg.sample
        self._verify_cfg     = cfg.verify
        self.meta            = Dataset_Meta.Load(self.root)   # 정본 (Dataset_Meta)
        self.sample          = Sample_Set.Load(self.root / SAMPLE_DIR)   # 파생 (Sample_Set)

    # ── config 섹션 갱신 (단일 Pipeline 에 섹션별 주입) ─────────────────────────
    def set_converter(self, cfg: dict) -> None:
        """converter 섹션을 갱신한다 (meta 재로드 없이 — ``Convert`` 가 이 값을 읽는다)."""
        self._converter_cfg = cfg

    # ── 모델 풀 ───────────────────────────────────────────────────────────────
    def _model(self, spec: dict) -> Any:
        """모델 스펙 → 객체. 클래스 풀에 같은 스펙이 있으면 공유, 없으면 빌드해 캐싱."""
        _key = _model_key(spec)
        if _key not in self._RESOURCE_POOL:
            _params = {_k: _v for _k, _v in spec.items() if _k != "type"}
            self._RESOURCE_POOL[_key] = MODEL_BUILDERS[spec["type"]](**_params)
        return self._RESOURCE_POOL[_key]

    def _resolve_step(self, step: dict | str) -> dict | str:
        """process step config 의 모델 스펙 필드를 빌린 객체로 치환한다 (나머지는 그대로)."""
        if not isinstance(step, dict):
            return step
        return {_k: (self._model(_v) if _is_model_spec(_v) else _v)
                for _k, _v in step.items()}

    def _resolve_models(self, flow_cfg: dict) -> dict:
        """flow config 의 process/finalize 스펙 안 모델 스펙을 객체로 치환한 새 config."""
        _out = dict(flow_cfg)
        for _key in ("processes", "finalize_processes"):
            if _key in _out:
                _out[_key] = [self._resolve_step(_s) for _s in _out[_key]]
        return _out

    # ── 단계 ──────────────────────────────────────────────────────────────────
    def Convert(self) -> int:
        """raw 파일을 탐색해 modified 버킷에 컨테이너 ``Data_Ref`` 를 등록하고 저장한다.

        Returns:
            등록된 stem 수. 0이면 sources/globs 가 어떤 파일도 매칭하지 못한 것.
        """
        _converter      = _build_converter(self._converter_cfg)
        # 새 항목은 modified 버킷({root}/modified), params 는 상태 무관하게 root 직속.
        _nodes, _params = _converter.Convert(self.meta.Category_root("modified"), self.meta.root)
        for _stem, _node in _nodes:
            self.meta.Bucket("modified")[_stem] = _node
        self.meta.params.update(_params)
        # class→id 매핑(Load_id_map)은 파생(sample) 소유 — 정본은 class 이름만 든다(TODO: sample).
        self.meta.Scatter()
        return len(_nodes)

    def Run(self, progress: Callable[[str, int, int], None] | None = None,
            flows: list | None = None) -> None:
        """flow 시퀀스를 meta 위에서 실행하고 저장한다 (flow 간 데이터는 meta 경유).

        Args:
            progress: flow별 진행 콜백 ``(label, i, total)``.
            flows: 실행할 flow config (None 이면 생성 시 ``self._flow_cfgs``).
        """
        _cfgs = self._flow_cfgs if flows is None else flows
        _flows = [Build_flow(self._resolve_models(_cfg)) for _cfg in _cfgs]
        for _flow in _flows:
            _flow(self.meta, progress=progress)
        self.meta.Scatter()

    def Sample(self) -> int:
        """staged 정본을 소비해 파생(Sample_Set)을 재생성하고 저장한다 (A+ 순수 재생성).

        ``sample`` config 의 ``object_type`` 이 task(classification/detection)를 고른다. 매 호출이
        staged 에서 트리를 새로 지어 ``self.sample`` 을 교체하므로, 이전 파생은 흩기로 덮인다.

        Returns:
            파생된 sample(=범주 직속 항목) 수 합계.
        """
        _sampler = _build_sampler(self._sample_cfg)
        self.sample = _sampler.Build(self.meta)
        self.sample.Scatter()
        return sum(len(self.sample.Bucket(_s)) for _s in self.sample.CATEGORIES)

    def Verify(self) -> None:
        """생성 결과의 품질 검수 — Sampling 이후로 미룸(또는 Run 결과에서 대상 선택). 미구현."""
        raise NotImplementedError
