"""process 기본 구조 — process 유닛 베이스 + Stage(순회·체인·라우팅 엔진).

- **Base_Process** — 한 process 유닛의 베이스(``@dataclass`` config + ``__init_subclass__`` 계약:
  INPUTS 자동추출·OUTPUTS 주입·출력키 검증). 표시용 힌트 ``UI``(= ``core.typing.Arg_Info``)·타입 별칭
  ``BBOX``/``GRAY_IMAGE`` 는 횡단 ``core.typing`` 에서 재노출.
- **Stage** — ``store 범주 순회 → Base_Process 체인 → 라우팅`` 엔진(callable). 서브클래스는 **양 끝**
  (무엇을 ctx 로 풀고, 출력을 어디에 앉히나)만 override 한다: Run=``Flow``, Sample=``Sample_stage``.

**source/sink 계약은 없다** — 순회는 ``store.Bucket(범주)`` 한 줄, resolve 는 자유함수(:func:`resolve`),
route 는 ``store`` 창구 직접 호출이라 클래스로 세울 것이 없었다. 세 stage 의 진짜 변주는 traversal 기계가
아니라 양 끝이고, 그건 **파라미터와 두어 개의 훅**이다. Convert 는 체인을 아예 안 써서 엔진을 떠났다
(→ ``store.Import``). 설계 근거는 [`README.md`](README.md).

라우팅 규칙(``outputs`` spec 스키마)은 :meth:`Stage._route`, 설계는 [`README.md`](README.md).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Iterator

from python_toolbox.project.config import Base_Config

from ..constant import MODIFIED, TO_TRACE
from ..schema import PYTHON_TYPES, Data_Ref
from ..typing import Arg_Info as UI, BBOX, IMAGE, GRAY_IMAGE


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


# ── 순회 단위 + resolve (계약이 아니라 레코드·자유함수) ─────────────────────────

@dataclass
class Unit:
    """한 처리 단위 — process 체인 입력 ctx + 출력을 꽂을 **주소**.

    ``category``/``stem``/``obj_id`` 가 트리 주소이고 ``frame``/``obj`` 가 그 자리의 노드다
    (frame·obj 가 모두 ``None`` = 위치 없음 → dataset-wide params).

    **범주가 unit 에 사는 이유** — 한 stage 가 여러 범주를 순회할 수 있어(예: 학습셋 전 split 을 한 번에)
    "어느 범주에서 왔나"는 stage 의 설정이 아니라 **이 unit 의 사실**이다. 라우팅 경로가 여기서 나온다.
    """

    stem:     str
    ctx:      dict[str, Any]
    category: str            = ""
    frame:    Data_Ref | None = None
    obj_id:   str | None      = None
    obj:      Data_Ref | None = None


def inline_ctx(ref: Data_Ref) -> dict:
    """ref 의 **인라인 값 leaf** 만 ctx dict 로 (파일 payload 는 건너뜀 — 경량 역참조).

    gate·select process 가 정본에 기록된 값(``class_id``·``center_dist``·``bbox`` 등)으로 거를 수 있게
    한다 — payload(image/array/rle)는 로드하지 않으므로 파일 I/O 가 없다.

    **detail 이 파이썬 타입인 것**이 인라인 값이다(``("", "str")``·``("bbox", "list")``). 압축이지만
    파일 격인 ``rle``(detail=``"rle"``)이나 파일 leaf(detail=확장자)는 그래서 자연히 빠진다.
    """
    return {_k: _v.info.get("value")
            for _k, _v in ref.Leaves().items()
            if _v.format[1:2] and _v.format[1] in PYTHON_TYPES}


# ── Stage: 순회·체인·라우팅 엔진 ───────────────────────────────────────────────

@dataclass
class Stage(Base_Config):
    """``store 범주 순회 → 체인 → 라우팅`` 엔진 — Run/Sample 공통 골격.

    per-unit ``processes`` 체인과 순회 후 1회 ``finalize_processes`` 체인을 같은 규칙으로 빌드하고,
    ``category`` 버킷의 각 unit ctx 에 체인을 태워 step 출력을 라우팅한다. carry 는 프레임 간 이월
    (cross-frame reduce), cacheable 은 재실행 캐시(finalize 출력이 이미 있으면 순회 skip).

    **서브클래스가 바꾸는 건 양 끝뿐이다** — ``_block_ctx``/``_unit_ctx``(무엇을 ctx 로 푸나) ·
    ``_route``/``_emit``(출력을 어디에 앉히나). 순회 기계는 여기 하나뿐이다.

    엔진은 순회 상태를 인스턴스에 남기지 않는다. 누산조차 ``__call__`` 지역 변수라, 같은 ``Stage`` 를
    두 번 돌려도 서로를 오염시키지 않는다.
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
    # True면 이 stage의 params 출력 키(=finalize step들의 outputs)가 store 에 모두 있을 때 순회를
    # 건너뛴다 — "출력이 이미 있으면 다시 만들지 않는다"는 일반 규칙.
    cacheable: bool         = field(
        default=False,
        metadata={"ui": {"label": "재실행 캐시 (cacheable)",
                         "tip": "stage의 출력이 이미 있으면 순회 건너뜀"}})
    # 순회할 store 범주 — Run=modified, Sample=staged. "무엇을 순회하나"는 클래스가 아니라 값이다.
    # **여럿을 줄 수 있다** (예: 학습셋 전 split `[train, val, test]`) — 그러면 carry 가 범주 경계에서
    # 안 끊겨 finalize 가 전체를 한 덩어리로 본다(split 별로 따로 돌면 군집 id 가 서로 무의미해진다).
    category: str | list[str] = MODIFIED
    # 순회 단위 — "frame": 프레임당 1회 / "object": 프레임의 객체마다.
    unit:     str             = "frame"

    __exclude_serialize__: ClassVar[set[str]] = {"config_type"}

    def __post_init__(self) -> None:
        self._inners,     self._outputs     = self._build_chain(self.processes, self.shared)
        self._fin_inners, self._fin_outputs = self._build_chain(self.finalize_processes, self.shared)
        # 이 stage가 params(dataset-wide)로 내보내는 키 = finalize step들의 outputs 합집합.
        self._param_keys = [_k for _outs in self._fin_outputs for _k in _outs]

    # ── 양 끝 훅 (서브클래스가 구현) ──────────────────────────────────────────
    def _prelude(self, store) -> dict:
        """순회 전 1회 resolve 하는 공통 ctx (예: params). 없으면 ``{}``."""
        return {}

    def _block_ctx(self, store, category: str, stem: str, frame: Data_Ref) -> dict:
        """배치(=stem 하나) ctx — unit 루프와 무관하게 1회. 여기서 푼 값은 객체마다 다시 안 읽는다."""
        return {}

    def _unit_ctx(self, store, category: str, stem: str, bctx: dict,
                  obj_id: str | None, obj: Data_Ref | None) -> dict:
        """한 unit(객체 / frame-단위의 프레임)의 ctx — 배치 ctx 위에 unit 고유 값을 얹는다."""
        return dict(bctx)

    def _route(self, store, unit: Unit, spec_map: dict, out: dict) -> None:
        """step 출력 중 **선언된 키만** 영속한다 (per-step; 기본 no-op = ctx 로만 흐르다 소멸).

        ``spec_map`` = ``{출력키: spec}``. 미선언 키는 저장되지 않는다 — 그래서 "이 값이 저장되나?"는
        값이 아니라 config 를 봐야 안다(의도된 성질). spec 스키마::

            {to: "meta"|"storage", level?: "frame"|"object", type?: str, format?: str, as?: str}

        ``to`` = 보관 방식(인라인 / 파일), ``level`` = 위치(기본 ``"object"``), ``format`` = 확장자
        override. **파일 경로는 spec 이 안 정한다** — 트리 위치(범주·stem·obj_id)와 출력키에서 ``port`` 가
        파생한다(kind-major). 값 → ``Data_Ref`` 타입 결정도 spec 이 아니라
        :func:`core.port.Template` 가 값·맥락으로 정한다.

        **``as`` = 저장 leaf 별칭** (기본 = 출력키). ctx wire 이름은 그대로 두고 **디스크에 앉는
        leaf 이름만** 바꾼다 — 폴더가 곧 leaf 이름이라(kind-major) 별칭이 곧 저장 폴더고, leaf 이름에서
        경로가 파생되므로 복원도 일관된다. 원본을 안 덮고 변종·디버그 산출물을 딴 폴더에 남기는 자리
        (예: ``norm_frame`` 을 ``as: norm_clahe`` 로). **정본 leaf 이름(``segment`` 등)에는 쓰지 마라**
        — 그 이름을 읽는 소비처(sample·export·gui)가 못 찾는다. 별칭은 아무도 안 읽는 출력에만.

        Example:
            체인의 mask 출력을 객체 info 에 rle 인라인으로, score 를 png 파일로::

                outputs:
                  mask:  {to: meta,    level: object}
                  score: {to: storage, level: object, format: png}   # → modified/score/{stem}_{obj}.png
        """

    def _emit(self, store, unit: Unit, ctx: dict) -> None:
        """체인 후 unit 당 1회 — 구조 생성/배치 (기본 no-op). gate 로 걸러진 unit 은 호출되지 않는다."""

    # ── 출력 분배 — 진단(trace)은 트리 밖, 나머지는 서브클래스 훅(_route) ───────────
    def _dispatch(self, store, unit: Unit, spec_map: dict, out: dict) -> None:
        """step 출력을 목적지별로 가른다 — ``to: trace`` 는 트리 밖 sink, 나머지는 ``_route``.

        trace 를 서브클래스가 아니라 여기서 처리하는 이유: 진단물의 자리는 Run 이든 Sample 이든 **같다**
        (트리 밖). 양 끝이 다른 건 정본을 어디에 앉히느냐지 진단을 어디 두느냐가 아니다.
        """
        _trace = {_k: _s for _k, _s in spec_map.items() if _s.get("to") == TO_TRACE}
        if _trace:
            self._route_trace(store, unit, _trace, out)
        _rest = {_k: _s for _k, _s in spec_map.items() if _s.get("to") != TO_TRACE}
        if _rest:
            self._route(store, unit, _rest, out)

    def _route_trace(self, store, unit: Unit, spec_map: dict, out: dict) -> None:
        """진단 출력을 ``store.Trace`` 로 — leaf 를 안 만든다(트리에 안 앉는다).

        실행 폴더는 이 stage 의 ``_label()`` — UI 가 flow 이름으로 곧장 ``.trace/{label}/`` 을 가리킬 수
        있고, 같은 flow 를 다시 돌리면 그 폴더를 덮어써 **항상 최신 중간결과**가 같은 자리에 있다.
        """
        _path = tuple(_p for _p in (unit.stem, unit.obj_id) if _p)   # 비면 위치 없음(finalize)
        for _key, _spec in spec_map.items():
            _val = out.get(_key)
            if _val is not None:
                _as = _spec.get("as", _key)                          # 저장 종류(폴더) 별칭 — storage 와 동일
                store.Trace(self._label(), _path, _as, _spec, _val, params=not _path)

    def _cached(self, store) -> bool:
        """재실행 캐시 적중 — 이 stage 의 params 출력 키가 store 에 모두 있으면 True."""
        _params = store.Bucket(store.PARAMS)
        return all(_k in _params for _k in self._param_keys)

    def _label(self) -> str:
        return self.name or "stage"

    # ── 체인 조립 ─────────────────────────────────────────────────────────────
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

    # ── 순회 골격 ─────────────────────────────────────────────────────────────
    def _categories(self) -> tuple[str, ...]:
        """순회할 범주들 — 문자열 하나든 목록이든 한 모양으로."""
        return ((self.category,) if isinstance(self.category, str)
                else tuple(self.category))

    def _units(self, store, category: str, stem: str, frame: Data_Ref,
               bctx: dict) -> Iterator[Unit]:
        """이 배치의 처리 단위들 — object=자식 obj 마다, frame=``_frame_unit``.

        **resolve 는 불변인 가장 넓은 스코프에서 1회** — 프레임 leaf 를 ``_block_ctx`` 에서 한 번 풀고
        객체마다 다시 읽지 않는다. block→unit 2단이 존재하는 이유가 이것이다.
        """
        if self.unit == "object":
            for _oid, _obj in frame.Branches().items():
                yield Unit(stem=stem, category=category,
                           ctx=self._unit_ctx(store, category, stem, bctx, _oid, _obj),
                           frame=frame, obj_id=_oid, obj=_obj)
        else:
            yield from self._frame_unit(store, category, stem, frame, bctx)

    def _frame_unit(self, store, category: str, stem: str, frame: Data_Ref,
                    bctx: dict) -> Iterator[Unit]:
        """frame-단위 기본 — 프레임 자신을 한 unit 으로 (obj = frame)."""
        yield Unit(stem=stem, category=category,
                   ctx=self._unit_ctx(store, category, stem, bctx, None, frame),
                   frame=frame, obj_id=None, obj=frame)

    def __call__(self, store, progress: Callable[[str, int, int], None] | None = None) -> None:
        _label = self._label()
        _blocks = [(_c, _s, _it) for _c in self._categories()
                   for _s, _it in store.Bucket(_c).items()]
        if self.cacheable and self._param_keys and self._cached(store):
            if progress is not None:                       # 이전 실행 결과가 그대로 → 건너뜀
                progress(_label, len(_blocks), len(_blocks))
            return

        _params_ctx = self._prelude(store)                 # 순회 전 1회 (params 등)
        _carry: dict = {}                                  # cross-block reduce (이 호출에만 사는 transient)
        _total = len(_blocks)                              # carry 는 범주 경계에서도 안 끊긴다
        for _i, (_cat, _stem, _frame) in enumerate(_blocks, start=1):
            _bctx = {**_params_ctx, **self._block_ctx(store, _cat, _stem, _frame)}
            _bctx.update(_carry)                           # 직전 배치 누산 상태 되먹임
            _last = _bctx
            for _unit in self._units(store, _cat, _stem, _frame, _bctx):
                _ctx, _gated = _unit.ctx, False
                for _idx, _inner in enumerate(self._inners):
                    _out = _inner(**_ctx)
                    if not _out:                           # 빈 dict = gate "이 unit 스킵"
                        _gated = True
                        break
                    _ctx = {**_ctx, **_out}
                    self._dispatch(store, _unit, self._outputs[_idx], _out)
                if not _gated:                             # gate 로 걸러진 unit 은 구조 생성도 스킵
                    self._emit(store, _unit, _ctx)
                _last = _ctx
            _carry = {_k: _last[_k] for _k in self.carry if _k in _last}
            if progress is not None:
                progress(_label, _i, _total)
        self._finalize(store, _carry)

    def _finalize(self, store, carry: dict) -> None:
        """순회 종료 후 1회 도는 reduce 체인 — carry 누산기를 params 단위로 낸다.

        per-frame step 과 **완전히 같은 규칙**이고, 차이는 도는 시점뿐이다. frame/obj 위치가 없으므로
        출력은 자동으로 dataset-wide(params)로 간다. 누산기 자체는 어느 step 의 출력도 아니면 영속되지
        않는다 — 라우팅 게이트 규칙 그대로다.
        """
        if not self._fin_inners:
            return
        _unit = Unit(stem="", ctx={})                      # 위치 없음 → params
        _ctx: dict = dict(carry)
        for _idx, _inner in enumerate(self._fin_inners):
            _out = _inner(**_ctx)
            if not _out:
                break
            _ctx = {**_ctx, **_out}
            self._dispatch(store, _unit, self._fin_outputs[_idx], _out)


# ── Flow: Run 구성 (modified 순회 → meta 로 route) ─────────────────────────────

@dataclass
class Flow(Stage):
    """Run stage — modified 프레임/객체를 순회하며 process 체인을 meta 로 route 한다.

    flow 종류는 subclass도 코드 preset도 아니라 **config가 직접 기술**한다(``unit``/``processes``/
    ``finalize_processes``/``shared``/``carry``/``cacheable``). ``object_type`` 은 진행 표시 라벨.

    staged(검수 끝)는 안 건드린다 — 재가공하려면 먼저 modified 로 되돌린다.
    """

    object_type: str = "flow"                     # 진행 표시 라벨 (자유 명명)

    def _label(self) -> str:
        return self.name or self.object_type

    # ── 입력: params 1회 + 프레임 leaf 1회 + 객체 leaf ──────────────────────────
    def _prelude(self, store) -> dict:
        return store.Resolve((store.PARAMS,), store.tree.Get(store.PARAMS))

    def _block_ctx(self, store, category: str, stem: str, frame: Data_Ref) -> dict:
        """프레임 leaf resolve + **객체 목록**을 ctx 로.

        ``object`` 는 store 에서 seed 하고, 체인의 ``split_objects`` 등이 같은 키로 덮어쓴다 — 입력과
        출력이 같은 이름이라 대칭이다. 유닛이 store 핸들을 받아 직접 뒤지지 않게 하는 자리.
        """
        _ctx: dict = {"stem": stem, "object": list(frame.Branches().values())}
        _ctx.update(store.Resolve((category, stem), frame))
        return _ctx

    def _unit_ctx(self, store, category: str, stem: str, bctx: dict,
                  obj_id: str | None, obj: Data_Ref | None) -> dict:
        _ctx = dict(bctx)
        _ctx["obj_id"] = obj_id                             # gate·select 가 obj_id 로 거를 수 있게
        if obj is not None:
            _path = ((category, stem, obj_id) if obj_id is not None else
                     (category, stem))                      # frame-단위: 프레임 자신이 obj
            _ctx.update(store.Resolve(_path, obj))
        return _ctx

    def _frame_unit(self, store, category: str, stem: str, frame: Data_Ref,
                    bctx: dict) -> Iterator[Unit]:
        """unit=frame: 첫 객체 1회(obj_id 바인딩). 객체가 없으면 프레임만."""
        _objs = frame.Branches()
        _k = next(iter(_objs)) if _objs else None
        _obj = _objs[_k] if _k is not None else None
        yield Unit(stem=stem, category=category,
                   ctx=self._unit_ctx(store, category, stem, bctx, _k, _obj),
                   frame=frame, obj_id=_k, obj=_obj)

    # ── 출력: store 에 앉혀달라고 요청한다 (port 는 store 가 부른다) ──────────────
    def _route(self, store, unit: Unit, spec_map: dict, out: dict) -> None:
        _frame, _obj, _stem, _obj_id = unit.frame, unit.obj, unit.stem, unit.obj_id
        _cat = unit.category                               # 범주는 stage 설정이 아니라 unit 의 주소다
        for _key, _spec in spec_map.items():
            if _key == "object":                           # leaf 가 아니라 **구조** — 아래에서 교체한다
                continue
            _val = out.get(_key)
            if _val is None:
                continue
            _as = _spec.get("as", _key)                    # 저장 leaf 별칭 (= 폴더). ctx wire 는 _key 그대로
            if _frame is None and _obj is None:            # 위치 없음(finalize) — params
                store.Set_param(_as, store.Route(
                    (store.PARAMS,), _as, _spec, _val, params=True))
                continue
            _is_obj = _spec.get("level", "object") == "object"
            if _is_obj and _obj is None:                   # 객체 위치 없음
                continue
            _target = _obj if _is_obj else _frame
            _path = ((_cat, _stem, _obj_id) if _is_obj and _obj_id is not None else
                     (_cat, _stem))
            _target.Push(_as, store.Route(_path, _as, _spec, _val))

        _objs = out.get("object")
        if "object" in spec_map and isinstance(_objs, list) and _frame is not None:
            _frame.Replace_branches(_objs)                  # 구조 교체 — 순번=obj_id; leaf 보존
