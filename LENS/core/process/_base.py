"""process 패키지 기본 구조 — process 유닛 베이스 + Stage(체인 엔진).

- **Base_Process** — 한 process 유닛의 베이스(``@dataclass`` config + ``__init_subclass__`` 계약:
  INPUTS 자동추출·OUTPUTS 주입·출력키 검증). 표시용 힌트 ``UI``(= ``core.typing.Arg_Info``)·타입 별칭
  ``BBOX``/``GRAY_IMAGE`` 는 횡단 ``core.typing`` 에서 재노출. 등록은 각 모듈에서
  ``@PROCESS_REGISTRY.Register_module()`` 로 명시(``target_type=Base_Process`` 하위만 통과).
- **Stage** — ``source → Base_Process 체인 → sink`` 엔진(callable). source(무엇을 순회·resolve)와
  sink(출력을 어디로)를 갈아끼워 Convert/Run/Sample 을 한 엔진으로 표현한다. ``Flow`` 는 그중 Run 구성
  (``Frame_source`` + ``Meta_sink``)을 config 로 여는 서브클래스 — 기존 flow config 와 호환된다.

source/sink 계약은 [`source.py`](source.py)·[`sink.py`](sink.py), 라우팅 규칙은 [`README.md`](README.md).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar

from python_toolbox.project.config import Base_Config

from ..typing import Arg_Info as UI, BBOX, GRAY_IMAGE
from .source import Base_Source, Frame_source
from .sink import Base_Sink, Meta_sink


# ── process 유닛: 베이스 ───────────────────────────────────────────────────────


@dataclass
class Base_Process:
    """process 유닛 베이스 — config는 dataclass 필드, 작업 state는 ctx(stateless).

    서브클래스는 ``class X(Base_Process, outputs=(...))`` 로 OUTPUTS(=산출 port)를 선언하고
    ``Run`` 을 구현한다. ``__call__`` 은 베이스가 소유하는 계약 프레임 — ``Run`` 실행 → OUTPUTS
    검증 → port→slot 재배선(``output_slots``). 등록은 각 모듈에서
    ``@PROCESS_REGISTRY.Register_module()`` 로 명시한다.

    설계 개념(계약·ctx 스코프·slot 재배선·모델 주입)은 ``README.md`` 참조.
    """

    INPUTS:   ClassVar[tuple[str, ...]] = ()
    OUTPUTS:  ClassVar[tuple[str, ...]] = ()
    # GUI 계층 탐색용 분류 경로 ("대분류/중분류"). 표시 메타데이터.
    CATEGORY: ClassVar[str]             = ""
    # 출력 port → ctx slot 재배선 맵 (config `slots`, Stage._build_chain 이 per-instance 주입).
    # 기본 빈 맵(=identity). 센티넬을 in-place mutate 금지 — 항상 새 dict 로 rebind.
    output_slots: ClassVar[dict[str, str]] = {}
    # Run 파라미터 → ctx slot 별칭 맵 (config `inputs`, Stage._build_chain 이 per-instance 주입).
    # output_slots(출력 재배선)의 입력쪽 대칭 — ctx 키 이름이 Run 파라미터명과 달라도 읽게 한다
    # (예: ctx `roi` 를 combine_mask 의 `mask` 로). 기본 빈 맵(=이름 그대로 ctx 에서 읽음).
    input_slots: ClassVar[dict[str, str]] = {}

    def __init_subclass__(cls, outputs: tuple[str, ...] = (),
                          category: str = "", **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls.OUTPUTS  = outputs
        cls.CATEGORY = category
        cls.INPUTS   = _extract_inputs(cls.Run)

    def __call__(self, **kwargs) -> dict:
        """계약 프레임 — 입력 별칭 remap → Run → OUTPUTS 검증 → port→slot 재배선. 빈 dict("스킵")는 그대로 통과."""
        # print(type(self).__name__)  # debug — 실행 중인 process 확인
        if self.input_slots:  # ctx 키 → Run 파라미터명 별칭 (output_slots 의 입력쪽 대칭)
            kwargs = {**kwargs, **{_p: kwargs.get(_k) for _p, _k in self.input_slots.items()}}
        _out = self.Run(**kwargs)
        if not _out:
            return _out
        _missing = [_p for _p in self.OUTPUTS if _p not in _out]
        if _missing:
            raise KeyError(f"{type(self).__name__}: OUTPUTS 미출력 port {_missing}")
        _slots = self.output_slots
        if not _slots:
            return _out
        return {_slots.get(_p, _p): _v for _p, _v in _out.items()}

    def Run(self, *args, **kwargs) -> dict:  # 계약 — 서브클래스가 구현
        raise NotImplementedError


def _extract_inputs(call_fn) -> tuple[str, ...]:
    return tuple(
        _name for _name, _p in inspect.signature(call_fn).parameters.items()
        if _name != "self"
        and _p.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    )


# ── Stage: 체인 엔진 (source → Base_Process 체인 → sink) ────────────────────────

@dataclass
class Stage(Base_Config):
    """``source → 체인 → sink`` 엔진 — Convert/Run/Sample 공통 골격.

    per-unit ``processes`` 체인과 순회 후 1회 ``finalize_processes`` 체인을 같은 규칙으로 빌드하고,
    ``source`` 가 낸 각 unit ctx 에 체인을 태워 step 출력을 ``sink`` 로 route 한다. carry 는 프레임 간
    이월(cross-frame reduce), cacheable 은 재실행 캐시(finalize 출력이 이미 있으면 순회 skip). source/
    sink 는 서브클래스가 ``_make_source``/``_make_sink`` 로 준다(Run=Frame_source/Meta_sink).

    라우팅 규칙·outputs 스키마·slot 재배선은 ``README.md``, 복붙 템플릿은 ``presets.example.yaml``.
    """

    name:   str             = ""      # 진행 표시용 이름 (없으면 서브클래스 라벨)
    # 이 stage 의 모든 step 에 공통 주입할 config (예: chroma 색공간 `space`). `_build_chain` 이 각
    # step params 앞에 merge → step 이 선언한 키만 받는다(`Build_process` 필터). step 이 같은 키를
    # 직접 주면 그 값이 이긴다. 흐름 전체가 공유하는 값을 한 곳에서 정하는 자리.
    shared: dict[str, Any]  = field(
        default_factory=dict,
        metadata={"ui": {"label": "공유 config (shared)",
                         "tip": "모든 step에 주입할 공통 파라미터 (예: space)"}})
    processes: list[str | dict[str, Any]] = field(default_factory=list)
    # 순회 종료 후 1회 도는 reduce 체인 — carry 최종값(누산기)을 받아 결과를 낸다.
    finalize_processes: list[str | dict[str, Any]] = field(default_factory=list)
    # 프레임 간 이월(되먹임)할 ctx 키. 누산기를 입력으로 받아 갱신본을 출력하는 process가
    # 이 키들로 cross-frame reduce를 구현한다 (런타임 수명 도구 — state도 영속도 아님).
    carry: list[str]        = field(
        default_factory=list,
        metadata={"ui": {"label": "프레임 간 이월 키 (carry)",
                         "tip": "다음 프레임 ctx로 넘겨 누산할 키"}})
    # True면 이 stage의 params 출력 키(=finalize step들의 outputs)가 sink 에 모두 있을 때 순회를
    # 건너뛴다 — "출력이 이미 있으면 다시 만들지 않는다"는 일반 규칙.
    cacheable: bool         = field(
        default=False,
        metadata={"ui": {"label": "재실행 캐시 (cacheable)",
                         "tip": "stage의 출력이 이미 있으면 순회 건너뜀"}})

    __exclude_serialize__: ClassVar[set[str]] = {"config_type"}

    def __post_init__(self) -> None:
        self._inners,     self._outputs     = self._build_chain(self.processes, self.shared)
        self._fin_inners, self._fin_outputs = self._build_chain(self.finalize_processes, self.shared)
        # 이 stage가 params(dataset-wide)로 내보내는 키 = finalize step들의 outputs 합집합.
        self._param_keys = [_k for _outs in self._fin_outputs for _k in _outs]

    # ── source/sink (서브클래스 제공) ─────────────────────────────────────────
    def _make_source(self) -> Base_Source:
        raise NotImplementedError

    def _make_sink(self) -> Base_Sink:
        raise NotImplementedError

    def _label(self) -> str:
        return self.name or "stage"

    @staticmethod
    def _build_chain(process_list: list, shared: dict | None = None) -> tuple[list, list[dict]]:
        """process 설정 목록 → ``(inner 인스턴스 리스트, step별 outputs 라우팅 spec 리스트)``.

        ``shared`` (stage-공유 config)를 각 step params 앞에 merge한다 — step이 선언한 키만
        받고(``Build_process`` 필터), step 고유 값이 있으면 그쪽이 이긴다. step config 의
        ``slots`` ({출력 port: ctx slot})는 인스턴스에 주입해 출력을 재배선한다(미선언 port=identity).
        """
        from . import Build_process   # 패키지 조립(__init__) — 지연 import로 순환 회피
        _shared:  dict       = shared or {}
        _inners:  list       = []
        _outputs: list[dict] = []  # step별 {출력키: 라우팅 spec}
        for _m in process_list:
            if isinstance(_m, dict):
                _outs   = _m.get("outputs", {}) or {}
                _slots  = _m.get("slots", {}) or {}
                _ins    = _m.get("inputs", {}) or {}
                _params = {
                    **{k: v for k, v in _m.items()
                       if k not in ("object_type", "outputs", "slots", "inputs")},
                    **_shared}
                _inner  = Build_process(_m["object_type"], _params)
            else:
                _outs, _slots, _ins, _inner = {}, {}, {}, Build_process(_m, dict(_shared))
            _bad = [_p for _p in _slots if _p not in _inner.OUTPUTS]
            if _bad:
                raise KeyError(f"{type(_inner).__name__}: slots 미선언 port {_bad} "
                               f"(OUTPUTS={_inner.OUTPUTS})")
            _bad_in = [_p for _p in _ins if _p not in _inner.INPUTS]
            if _bad_in:
                raise KeyError(f"{type(_inner).__name__}: inputs 미선언 파라미터 {_bad_in} "
                               f"(INPUTS={_inner.INPUTS})")
            _inner.output_slots = dict(_slots)
            _inner.input_slots  = dict(_ins)
            _inners.append(_inner)
            _outputs.append(_outs)
        return _inners, _outputs

    def _cache_hit(self, store, sink: Base_Sink) -> bool:
        """재실행 캐시 적중 — cacheable이고 이 stage의 출력 키가 sink 에 모두 있으면 True."""
        return (self.cacheable
                and bool(self._param_keys)
                and sink.cached(store, self._param_keys))

    def __call__(self, store, progress: Callable[[str, int, int], None] | None = None) -> None:
        _source, _sink = self._make_source(), self._make_sink()
        _label = self._label()
        if self._cache_hit(store, _sink):          # 이전 실행 결과가 그대로 → 건너뜀
            if progress is not None:
                _n = _source.count(store)
                progress(_label, _n, _n)
            return

        _params_ctx = _source.prelude(store)       # 순회 전 1회 (params 등)
        _carry: dict = {}                          # cross-block reduce (이 호출에만 사는 transient)
        _blocks = list(_source.blocks(store))
        _total = len(_blocks)
        for _i, _block in enumerate(_blocks, start=1):
            _bctx = _block.context(store, _params_ctx)   # 배치 ctx (unit 루프와 무관하게 1회)
            _bctx.update(_carry)                          # 직전 배치 누산 상태 되먹임
            _last = _bctx
            for _unit in _block.units(store, _bctx):
                _ctx, _gated = _unit.ctx, False
                for _idx, _inner in enumerate(self._inners):
                    _out = _inner(**_ctx)
                    if not _out:                          # 빈 dict = gate "이 unit 스킵"
                        _gated = True
                        break
                    _ctx = {**_ctx, **_out}
                    _sink.route(store, _unit, self._outputs[_idx], _out)   # per-step leaf 라우팅(Run)
                if not _gated:                            # gate 로 걸러진 unit 은 구조 생성도 스킵
                    _sink.emit(store, _unit, _ctx)        # per-unit 구조 생성(Convert/Sample; Run=no-op)
                _last = _ctx
            _carry = {_k: _last[_k] for _k in self.carry if _k in _last}
            if progress is not None:
                progress(_label, _i, _total)
        self._finalize(store, _sink, _carry)
        _sink.close(store)

    def _finalize(self, store, sink: Base_Sink, carry: dict) -> None:
        """순회 종료 후 1회 도는 reduce 체인 — carry 누산기를 sink 의 params 단위로 낸다.

        per-frame step 과 **완전히 같은 규칙**이고, params 단위(위치 없음)라 sink 가 dataset-wide 로
        보낸다. 누산기 자체는 어느 step 의 출력도 아니면 영속되지 않는다.
        """
        if not self._fin_inners:
            return
        _unit = sink.params_unit()
        _ctx = {**sink.finalize_ctx(store), **carry}
        for _idx, _inner in enumerate(self._fin_inners):
            _out = _inner(**_ctx)
            if not _out:
                break
            _ctx = {**_ctx, **_out}
            sink.route(store, _unit, self._fin_outputs[_idx], _out)


# ── Flow: Run 구성 (Frame_source + Meta_sink) ─────────────────────────────────

@dataclass
class Flow(Stage):
    """Run stage — modified 프레임/객체를 순회하며 process 체인을 meta 로 route 한다.

    ``Stage`` 엔진에 ``Frame_source``(unit=frame/object) + ``Meta_sink`` 를 끼운 구성. flow 종류는
    subclass도 코드 preset도 아니라 **config가 직접 기술**한다(``unit``/``processes``/``finalize_processes``/
    ``shared``/``carry``/``cacheable``). ``object_type`` 은 진행 표시 라벨.
    """

    object_type: str = "flow"                     # 진행 표시 라벨 (자유 명명)
    # 순회 단위 — "frame": 프레임당 1회(첫 객체) / "object": 프레임의 객체마다.
    unit:        str = "frame"

    def _make_source(self) -> Base_Source:
        return Frame_source(unit=self.unit)

    def _make_sink(self) -> Base_Sink:
        return Meta_sink()

    def _label(self) -> str:
        return self.name or self.object_type
