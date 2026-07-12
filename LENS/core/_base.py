"""core 기본 구조 — Pipeline(계산 오케스트레이션 binder) + 모델 풀.

``Pipeline`` 은 정본(``Dataset_Meta``)을 중심으로 **계산 단계**(Convert → Run)를 조율하고 결과를
``meta.Save()`` 로 영속한다. flow 시퀀스를 조립·실행하며, 무거운 prediction 모델을 **클래스
dict 풀**(``Pipeline._RESOURCE_POOL``)로 공유한다(프로세스 수명, 인스턴스 간 공유 — GUI 가 실행마다 새
바인더를 만들어도 재사용).

전이·삭제·병합·들이기·내보내기 같은 **데이터 라이프사이클**은 바인더가 아니라 [`store`](store) 의
``Bucket_Store`` **메서드**가 소유한다 — 호출 측(GUI 등)이 ``meta.Move(…)`` 를 직접 부른다.
바인더는 계산 단계만 잇는다. Verify(품질 검수)는 미구현.

진입점·경로 resolve 는 [`__init__.py`](__init__.py).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar

from python_toolbox.project.config import Base_Config

from .constant import MODIFIED
from .process import Build_flow, Sample_stage
from .process.stream.mask.order import Order_objects
from .store import SAMPLE_DIR, Dataset_Meta, Sample_Set
from .tasker import Load_taskers, Save_taskers
from .process.stream.model._sam3 import Sam3_runner


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
    def Convert(self, progress: Callable[[str, int, int], None] | None = None) -> int:
        """raw 파일을 탐색해 modified 버킷에 컨테이너 ``Data_Ref`` 를 등록하고 저장한다.

        Convert 는 **stage 가 아니다** — 체인이 비어 엔진을 안 쓴다. 들이는 일은 라이프사이클이라
        **store 가 소유한다**(``meta.Import``) — 바인더는 config 를 넘길 뿐이다.

        Returns:
            modified 버킷의 총 frame 수. 0이면 sources/globs 가 어떤 파일도 매칭하지 못한 것.
        """
        _cfg = self._converter_cfg
        self.meta.Import(sources=_cfg.get("sources", []),
                         globs=_cfg.get("globs", {}),
                         params=_cfg.get("params", {}),
                         progress=progress)
        # class→id 매핑(id_map)은 파생(sample) 소유 — 정본은 class 이름만 든다.
        self.meta.Save()
        return len(self.meta.Bucket(MODIFIED))

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
        self.meta.Save()

    def Order(self, stems: list[str] | None = None,
              progress: Callable[[str, int, int], None] | None = None) -> None:
        """지정 stem 들의 객체를 중심-거리 순으로 재정렬 — obj_id 재부여 + segment 재라벨 + 저장.

        편집(객체 삭제 등)이 남긴 obj_id **구멍을 압축**하는 자리다. 삭제(``meta.Remove_object``)는
        정합만 지키고 순번을 안 매기므로(store 는 process 를 모른다), 압축은 여기(binder)가
        ``Order_objects``(process)를 돌려 한다 — 저장·병합 직후 호출한다. ``stems=None`` 이면 전 범주.

        Args:
            stems: 재정렬할 item key 들 (None 이면 모든 범주의 전 stem).
            progress: 진행 콜백 ``(label, i, total)``.
        """
        _keys = (list(stems) if stems is not None
                 else [_k for _c in self.meta.CATEGORIES for _k in self.meta.Bucket(_c)])
        for _i, _stem in enumerate(_keys, start=1):
            self._order_stem(_stem)
            if progress is not None:
                progress("order", _i, len(_keys))

    def _order_stem(self, stem: str) -> None:
        """한 stem 의 segment + 객체를 ``Order_objects`` 로 재정렬해 되꽂고 저장한다 (대상 없으면 no-op)."""
        _item = self.meta.Find(stem)
        if _item is None:
            return
        _name, _ref = next(((_n, _r) for _n, _r in _item.Leaves().items()
                            if _r.format[:1] == ("segmap",)), (None, None))
        _objs = list(_item.Branches().values())
        if _ref is None or not _objs:
            return
        _seg = self.meta.Load(stem, _name)
        if _seg is None:
            return
        _out = Order_objects().Run(segment=_seg, object=_objs)
        if not _out:
            return
        _path = self.meta.Item_path(stem)
        _spec = {"to": "storage", "type": _ref.format[0]}
        if len(_ref.format) > 1 and _ref.format[1]:
            _spec["format"] = _ref.format[1]
        _item.Push(_name, self.meta.Route(_path, _name, _spec, _out["segment"]))
        _item.Replace_branches(_out["object"])
        self.meta.Save(stem)

    # ── 파생(Sample) — 이름 붙은 tasker ({root}/sample/{name} + taskers.yaml) ────
    def Taskers(self) -> dict[str, dict]:
        """등록된 tasker 목록 (``{name: sample config}``) — ``{root}/sample/taskers.yaml``."""
        return Load_taskers(self._sample_root)

    def List_taskers(self) -> list[str]:
        """GUI 목록용 tasker 이름 — 등록 레시피(taskers.yaml) ∪ 실제 빌드 폴더(``{root}/sample/*``).

        레시피와 산출물 폴더가 어긋나도(한쪽만 존재) 둘 다 보이게 합쳐 돌려준다 — 레시피 없이
        폴더만 남은 orphan 도 목록에 떠 ``Delete_tasker`` 로 폴더째 지울 수 있다.
        """
        _names = set(self.Taskers())
        if self._sample_root.exists():
            _names |= {_p.name for _p in self._sample_root.iterdir()
                       if _p.is_dir() and not _p.name.startswith(".")}
        return sorted(_names)

    def Load_sample(self, name: str) -> Sample_Set:
        """이름 붙은 tasker 의 학습셋 store 를 복원한다 (``{root}/sample/{name}``).

        파생 store 는 타입이 하나뿐이다 — task(classification/detection)는 빌드가 아니라 **내보내기**의
        축이라 store 모양을 가르지 않는다.
        """
        return Sample_Set.Restore(self._sample_root / name)

    def Tasker_root(self, name: str) -> Path:
        """빌드된 tasker 의 store 루트 ``{root}/sample/{name}`` (payload 는 ``{split}/crop/*.png``)."""
        return self._sample_root / name

    def Sample(self, name: str, cfg: dict | None = None) -> int:
        """staged 정본을 소비해 이름 붙은 tasker 를 (재)빌드·영속하고 ``taskers.yaml`` 에 등록한다.

        ``Sample_stage`` 를 meta 위에서 구동한다 — Run 과 **같은 엔진**이고 양 끝만 다르다(순회=staged
        정본, 배치=새 ``Sample_Set``). 매 호출이 그 tasker 를 새로 지어 ``{root}/sample/{name}`` 에
        흩고(A+ 순수 재생성), 레시피(``cfg``)를 ``taskers.yaml`` 에 등록한다.

        **split 은 빌드가 배정한다** — split 이 곧 store 범주라 배치 시점에 정해져야 한다. 레시피의
        ``ratios``/``salt`` 가 그래서 여기로 온다(옛 모델은 내보내기가 갈랐다).

        Args:
            name: tasker 이름 (폴더·레지스트리 key).
            cfg:  sample 설정(``unit``/``ratios``/``salt``/``processes``, 내보내기용 ``task``). None 이면
                  등록된 레시피(없으면 생성 시 ``sample`` 섹션).

        Returns:
            파생된 sample 수 합계 (전 split).
        """
        _cfg = cfg if cfg is not None else self.Taskers().get(name, self._sample_cfg)
        _sset = Sample_Set(root=str(self._sample_root / name))
        _stage = Sample_stage(
            unit=_cfg.get("unit", "object"),
            ratios=_cfg.get("ratios") or {},       # 빈 dict → 균등 배분 (Sample_stage._norm_ratios)
            salt=_cfg.get("salt", ""),
            target=_sset,
            processes=_cfg.get("processes", []),   # crop 실체화 체인
        )
        _stage(self.meta)
        _sset.Save()
        _taskers = self.Taskers()                  # 레시피 등록 (name ↔ 폴더 매칭)
        _taskers[name] = _cfg
        Save_taskers(self._sample_root, _taskers)
        return sum(len(_sset.Bucket(_s)) for _s in _sset.CATEGORIES)

    def Export_tasker(self, name: str, dest: str | Path) -> Path:
        """빌드된 tasker 를 학습 프레임워크 레이아웃으로 외부 경로에 실체화한다.

        **내보내기는 store 가 한다** (``Sample_Set.Export`` — 라이프사이클은 store 소유). 바인더가 여기서
        하는 일은 **레시피에서 task 를 읽어 넘기는 것**뿐이다: 어떤 tasker 인지 아는 건 레시피이고,
        그 레시피는 바인더가 든다.

        Args:
            name: 내보낼 tasker 이름.
            dest: 대상 상위 디렉터리 — 이 아래 ``{name}`` 폴더로 실체화된다.

        Returns:
            산출물 경로 (``dest/{name}``).

        Raises:
            FileNotFoundError: tasker 폴더가 없으면 (아직 빌드 안 됨).
            ValueError: 레시피의 task 에 맞는 exporter 가 없으면 (store 가 판정).
        """
        if not (self._sample_root / name).exists():
            raise FileNotFoundError(f"빌드된 tasker 가 없습니다: {name!r} (먼저 Sample 실행)")
        _cfg = self.Taskers().get(name, {})
        return self.Load_sample(name).Export(
            Path(dest) / name,
            task=_cfg.get("task", _cfg.get("object_type", "classification")),
            meta=self.meta,
            id_map=self._meta_id_map())

    def Id_map(self) -> dict:
        """정본 ``meta.params`` 의 id_map 을 원본 dict 로 돌려준다 (없으면 ``{}``).

        params leaf 는 인라인(attr)일 수도 파일(doc yaml/json)일 수도 있는데, ``meta.Param`` 이 그걸
        통합해 푼다 — 바인더는 포맷을 모른다. 값 구조(``{class:{class_id,category_id}}`` 등)는 그대로:
        재배정 class 후보(키 = class 이름) 소스로 GUI 가 쓴다. index 로 평탄화한 건 ``_meta_id_map``.
        """
        _val = self.meta.Param("id_map") if self.meta is not None else None
        return _val if isinstance(_val, dict) else {}

    def _meta_id_map(self) -> dict[str, int] | None:
        """정본 id_map 을 flat ``{class:int}`` 로 (없으면 None → sink 가 class 정렬로 자동 생성).

        정본이 class→index 매핑을 이미 갖고 있으면 산출물에 그대로 써 재빌드·재분할해도 index 가 안
        흔들린다. 값이 ``{class:{class_id:int,…}}`` 중첩이면 ``class_id``(없으면 첫 정수)를 골라 평탄화한다.
        """
        _flat: dict[str, int] = {}
        for _cls, _v in self.Id_map().items():
            if isinstance(_v, dict):
                _v = _v.get("class_id", next(iter(_v.values()), None))
            if isinstance(_v, (int, float)):
                _flat[str(_cls)] = int(_v)
        return _flat or None

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
