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

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar

from python_toolbox.project.config import Base_Config

from .data.meta import Dataset_Meta
from .data.sample import SAMPLE_DIR, Sample_Set
from .converter import Convert_stage
from .sampler import Load_taskers, Sample_stage, Save_taskers
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
        self.meta            = Dataset_Meta.Restore(self.root)   # 정본 (Dataset_Meta)
        self._sample_root    = self.root / SAMPLE_DIR            # 파생 root ({root}/sample/{tasker})

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

        ``Convert_stage``(``Raw_source`` → ``Register_sink``)를 meta 위에서 구동한다 — Run 과 같은
        Stage 엔진(source→sink). config ``sources``/``globs``/``params`` 는 ``Raw_source`` 로 넘어간다.

        Returns:
            modified 버킷의 총 frame 수. 0이면 sources/globs 가 어떤 파일도 매칭하지 못한 것.
        """
        _cfg = self._converter_cfg
        _stage = Convert_stage(
            sources=_cfg.get("sources", []),
            globs=_cfg.get("globs", {}),
            params=_cfg.get("params", {}),
            processes=_cfg.get("processes", []),   # raw→정본 변환 체인 (보통 빔)
        )
        _stage(self.meta)
        # class→id 매핑(id_map)은 파생(sample) 소유 — 정본은 class 이름만 든다.
        self.meta.Scatter()
        return len(self.meta.Bucket("modified"))

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

    # ── 파생(Sample) — 이름 붙은 tasker ({root}/sample/{name} + taskers.yaml) ────
    def Taskers(self) -> dict[str, dict]:
        """등록된 tasker 목록 (``{name: sample config}``) — ``{root}/sample/taskers.yaml``."""
        return Load_taskers(self._sample_root)

    def Load_sample(self, name: str) -> Sample_Set:
        """이름 붙은 tasker 의 ``Sample_Set`` 을 복원한다 (``{root}/sample/{name}``)."""
        return Sample_Set.Restore(self._sample_root / name)

    def Sample(self, name: str, cfg: dict | None = None) -> int:
        """staged 정본을 소비해 이름 붙은 tasker 를 (재)빌드·영속하고 ``taskers.yaml`` 에 등록한다.

        ``Sample_stage``(``Staged_source`` → ``Sample_sink[task]``)를 meta 위에서 구동한다 — Run/Convert 와
        같은 Stage 엔진(source=staged meta, sink=새 ``Sample_Set``). 매 호출이 그 tasker 트리를 새로 지어
        ``{root}/sample/{name}`` 에 흩고(A+ 순수 재생성), 레시피(``cfg``)를 ``taskers.yaml`` 에 등록한다.

        Args:
            name: tasker 이름 (폴더·레지스트리 key).
            cfg:  sample 설정(``task``/``ratios``/``unit``/``salt``). None 이면 등록된 레시피(없으면
                  생성 시 ``sample`` 섹션).

        Returns:
            파생된 sample(=범주 직속 항목) 수 합계.
        """
        _cfg = cfg if cfg is not None else self.Taskers().get(name, self._sample_cfg)
        _sset = Sample_Set(root=str(self._sample_root / name))
        _kw = dict(
            task=_cfg.get("task", _cfg.get("object_type", "classification")),
            salt=_cfg.get("salt", ""),
            unit=_cfg.get("unit", "object"),
            target=_sset,
            processes=_cfg.get("processes", []),   # crop 실체화 체인 (Phase B)
        )
        if _cfg.get("ratios"):                     # 없으면 Sample_stage 기본(DEFAULT_RATIOS)
            _kw["ratios"] = _cfg["ratios"]
        _stage = Sample_stage(**_kw)
        _stage(self.meta)
        _sset.Scatter()
        _taskers = self.Taskers()                  # 레시피 등록 (name ↔ 폴더 매칭)
        _taskers[name] = _cfg
        Save_taskers(self._sample_root, _taskers)
        return sum(len(_sset.Bucket(_s)) for _s in _sset.CATEGORIES)

    def Delete_tasker(self, name: str) -> None:
        """tasker 를 제거한다 — 폴더(``{root}/sample/{name}``)와 ``taskers.yaml`` 항목 (없으면 no-op)."""
        _dir = self._sample_root / name
        if _dir.exists():
            shutil.rmtree(_dir)
        _taskers = self.Taskers()
        if _taskers.pop(name, None) is not None:
            Save_taskers(self._sample_root, _taskers)

    def Verify(self) -> None:
        """생성 결과의 품질 검수 — Sampling 이후로 미룸(또는 Run 결과에서 대상 선택). 미구현."""
        raise NotImplementedError
