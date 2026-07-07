"""process 패키지 기본 구조 — process 유닛 베이스와 flow(체인 엔진).

- **Base_Process** — 한 process 유닛의 베이스(``@dataclass`` config + ``__init_subclass__``
  계약: INPUTS 자동추출·OUTPUTS 주입·출력키 검증). 표시용 힌트 ``UI``(= ``core.typing.Arg_Info``)·
  타입 별칭 ``BBOX``/``GRAY_IMAGE`` 는 횡단 ``core.typing`` 에서 가져와 재노출한다. 등록은 각 모듈에서
  ``@PROCESS_REGISTRY.Register_module()`` 로 명시(``target_type=Base_Process`` 하위 클래스만 통과).
- **Flow** — process 들을 잇는 한 체인(callable). meta 위를 순회하며 chain을 실행하고
  결과를 핸들러로 ``Dataset_Meta`` 에 라우팅한다. process 인스턴스는 ``Build_process``
  (패키지 ``__init__`` 의 레지스트리 팩토리)로 만든다.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Iterator

import numpy as np
from python_toolbox.project.config import Base_Config

from ..typing import Arg_Info as UI, BBOX, GRAY_IMAGE
from ..data.handler import Data_Ref
from ..data.meta import Dataset_Meta
from ..data import handler


# flow 는 working set(= modified 버킷)만 가공한다. staged(검수 끝난 것)는 건드리지 않는다 —
# staged 인 stem 을 재가공하려면 먼저 modified 로 되돌린다(목록 우클릭 메뉴).
WORKING_STATE = "modified"


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
    # 출력 port → ctx slot 재배선 맵 (config `slots`, Flow._build_chain 이 per-instance 주입).
    # 기본 빈 맵(=identity). 센티넬을 in-place mutate 금지 — 항상 새 dict 로 rebind.
    output_slots: ClassVar[dict[str, str]] = {}
    # Run 파라미터 → ctx slot 별칭 맵 (config `inputs`, Flow._build_chain 이 per-instance 주입).
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


# ── flow: 입력 resolve / 출력 route 헬퍼 ──────────────────────────────────────

def _resolve(
    root: str, stem: str | None, data: dict[str, Data_Ref], *, obj_id: str | None = None
) -> dict:
    """``data`` (이름→``Data_Ref``)를 핸들러로 풀어 ctx dict로 만든다.

    각 값을 ``handler.Load`` 로 payload(이미지·배열·값·디코드된 마스크)로 해제한다. 대상이
    없으면(None) 건너뛴다 — process는 ``Data_Ref`` 가 아니라 ready-to-use 값만 본다. 컨테이너
    entry(``type="stem"`` = 하위 객체)는 payload 가 아니라 건너뛴다 (leaf 만 해제).
    """
    _out: dict = {}
    for _name, _ref in data.items():
        if _ref.Is_stem():                                 # 하위 객체(컨테이너)는 payload 아님
            continue
        _val = handler.Load(root, stem, _name, _ref, obj_id=obj_id)
        if _val is not None:
            _out[_name] = _val
    return _out


def _params_ref(spec: dict, val: Any) -> Data_Ref:
    """블록(dataset-wide) 출력 → ``params`` 용 ``Data_Ref`` 템플릿."""
    if spec.get("to", "meta") == "storage":
        _fmt = spec.get("format", "npy")
        return Data_Ref(type=spec.get("type") or handler.Infer_type(_fmt) or "array",
                        format=_fmt, info={"dir": spec.get("dir", "params")})
    if isinstance(val, np.ndarray) and val.ndim:           # 배열 → npy
        return Data_Ref(type="array", format="npy", info={"dir": "params"})
    return Data_Ref(type="attr", info={})                  # 스칼라/list/dict 인라인


def _data_ref(spec: dict, val: Any) -> Data_Ref:
    """frame/object 출력 → ``Data_Ref`` 템플릿 (meta 인라인=rle/attr / storage=image/array)."""
    if spec.get("to", "meta") == "storage":
        _fmt = spec.get("format", "png")
        return Data_Ref(type=spec.get("type") or handler.Infer_type(_fmt) or "image",
                        format=_fmt, info={"dir": spec.get("dir", "")})
    if isinstance(val, np.ndarray) and val.ndim >= 2:      # 마스크 → RLE 인라인
        return Data_Ref(type="rle", info={})
    return Data_Ref(type="attr", format=spec.get("format", ""), info={})  # bbox 등


# ── flow: 체인 엔진 ───────────────────────────────────────────────────────────

@dataclass
class Flow(Base_Config):
    """process 들을 잇는 한 체인 — dataset 위를 순회하며 실행하는 callable.

    각 step은 출력을 ``outputs`` 로 meta/storage 에 라우팅하고(미선언 키는 ctx 로만 흘러 다음 step
    입력), ``slots`` 로 출력 port 를 다른 ctx slot 에 재배선한다. finalize step 은 순회 후 1회 돌며
    carry 누산기를 params(dataset-wide)로 낸다. 저장/로드는 dataset 핸들러(``handler``)에 위임 —
    flow 는 위치(frame/object/params)와 타입만 정한다. flow 종류는 subclass 도 코드 preset 도 아니라
    **config 가 직접 기술**한다(``unit``/``processes``/``finalize_processes``/``shared``/``carry``).

    라우팅 규칙·outputs 스키마·스코프·slot 재배선은 ``README.md``, 복붙 템플릿은 ``presets.example.yaml``.
    """

    object_type: str                        = "flow"  # 진행 표시 라벨 (자유 명명)
    name:        str                        = ""      # 진행 표시용 이름 (없으면 object_type)
    # 순회 단위 — "frame": 프레임당 1회(첫 객체) / "object": 프레임의 객체마다.
    unit:        str                        = "frame"
    # 이 flow의 모든 step에 공통 주입할 config (예: chroma 색공간 `space`). `_build_chain` 이 각
    # step params 앞에 merge → step이 선언한 키만 골라 받는다(`Build_process` 필터). step이 같은
    # 키를 직접 주면 그 값이 이긴다. 흐름 전체가 공유하는 값을 한 곳에서 정하는 자리.
    shared:      dict[str, Any]             = field(
        default_factory=dict,
        metadata={"ui": {"label": "공유 config (shared)",
                         "tip": "모든 step에 주입할 공통 파라미터 (예: space)"}})
    processes:   list[str | dict[str, Any]] = field(default_factory=list)
    # 순회 종료 후 1회 도는 reduce 체인 — carry 최종값(누산기)을 받아 결과를 낸다.
    finalize_processes: list[str | dict[str, Any]] = field(default_factory=list)
    # 프레임 간 이월(되먹임)할 ctx 키. 누산기를 입력으로 받아 갱신본을 출력하는 process가
    # 이 키들로 cross-frame reduce를 구현한다 (런타임 수명 도구 — state도 영속도 아님).
    carry: list[str]                        = field(
        default_factory=list,
        metadata={"ui": {"label": "프레임 간 이월 키 (carry)",
                         "tip": "다음 프레임 ctx로 넘겨 누산할 키"}})
    # True면 이 flow의 params 출력 키(=finalize step들의 outputs)가 meta.params에 모두 있을 때
    # 순회를 건너뛴다 — "출력이 이미 dataset_meta에 있으면 다시 만들지 않는다"는 일반 규칙.
    cacheable: bool                         = field(
        default=False,
        metadata={"ui": {"label": "재실행 캐시 (cacheable)",
                         "tip": "flow의 params 출력이 meta 에 모두 있으면 순회 건너뜀"}})

    __exclude_serialize__: ClassVar[set[str]] = {"config_type"}

    def __post_init__(self) -> None:
        # per-frame 체인과 finalize(순회 후 1회) 체인을 같은 규칙으로 빌드한다.
        self._inners,     self._outputs     = self._build_chain(self.processes, self.shared)
        self._fin_inners, self._fin_outputs = self._build_chain(self.finalize_processes, self.shared)
        # 이 flow가 params(dataset-wide)로 내보내는 키 = finalize step들의 outputs 합집합.
        # (per-frame step은 frame/object 위치로 가므로 params 키가 아니다.) cacheable 판정에 쓴다.
        self._param_keys = [_k for _outs in self._fin_outputs for _k in _outs]

    @staticmethod
    def _build_chain(process_list: list, shared: dict | None = None) -> tuple[list, list[dict]]:
        """process 설정 목록 → ``(inner 인스턴스 리스트, step별 outputs 라우팅 spec 리스트)``.

        ``shared`` (flow-공유 config)를 각 step params 앞에 merge한다 — step이 선언한 키만
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

    def _build_frame_context(
        self, meta: Dataset_Meta, stem: str, frame: Data_Ref, **params_ctx: dict
    ) -> dict:
        """프레임 단위 ctx — frame.info(leaf) + params. 객체 루프와 무관하게 프레임당 1회 만든다."""
        ctx: dict = {"meta": meta, "stem": stem, **params_ctx}
        ctx.update(_resolve(meta.Category_root(WORKING_STATE), stem, frame.info))
        return ctx

    def _build_object_context(
        self, meta: Dataset_Meta, stem: str, obj_id: str | None, obj: Data_Ref | None
    ) -> dict:
        """객체 단위 ctx — obj.info(핸들러로 해제). obj가 없으면 빈 dict."""
        if obj is None:
            return {}
        return _resolve(meta.Category_root(WORKING_STATE), stem, obj.info, obj_id=obj_id)

    def _iter_units(self, frame: Data_Ref) -> Iterator[tuple[str | None, Data_Ref | None]]:
        """chain 을 돌릴 처리 단위를 ``(obj_id, 객체 Data_Ref)`` 로 내준다 (``unit`` 으로 분기).

        객체는 frame ``info`` 중 컨테이너(``type="stem"``) entry — obj_id 는 별도 필드가 아니라 그 **key**.

        - ``unit="frame"`` (기본): 프레임당 1회 — 첫 객체(없으면 ``(None, None)``).
        - ``unit="object"``: 프레임의 객체마다 (0개면 프레임 스킵).
        """
        _objs = {_k: _v for _k, _v in frame.info.items() if _v.Is_stem()}
        if self.unit == "object":
            yield from _objs.items()
        elif _objs:
            _k = next(iter(_objs))
            yield _k, _objs[_k]
        else:
            yield None, None

    def _apply_chain(self, ctx: dict, on_step=None, chain: list | None = None) -> dict:
        """``chain`` (기본 per-frame ``self._inners``) 을 순차 실행하며 ctx를 누적한다.

        step이 빈 dict를 내면 "이 프레임/finalize 스킵" 관례로 즉시 멈춘다.
        """
        for idx, inner in enumerate(self._inners if chain is None else chain):
            out = inner(**ctx)
            if not out:
                break
            ctx = {**ctx, **out}
            if on_step is not None:
                on_step(idx, out)
        return ctx

    def _route(
        self, meta: Dataset_Meta, stem: str, frame: Data_Ref | None,
        obj_id: str | None, obj: Data_Ref | None, outputs: dict, source: dict,
    ) -> None:
        """``outputs`` (출력키→spec) 의 각 키를 ``source`` 에서 꺼내 핸들러로 저장한다.

        ``to`` 는 보관 방식(meta 인라인 / storage 파일), ``level`` 은 위치(frame/object)를 가른다.
        저장은 전부 ``handler.Save`` 가 하고, flow는 ``Data_Ref`` 템플릿(타입·dir·format)과
        ``obj_id`` 만 구성한다. 미선언 키는 ctx로만 흐른다. ``object`` 리스트만은 구조적 교체라
        spec과 무관하게 frame ``info`` 의 컨테이너 entry(obj_id = 리스트 순번)로 반영한다(leaf 는 보존).
        frame/obj가 없는 호출(finalize)에선 위치가 없어 ``params``(root leaf, dataset-wide)로만 나간다.
        """
        _root = meta.Category_root(WORKING_STATE)         # 프레임/객체 파일은 modified 버킷에
        for _key, _spec in outputs.items():
            _val = source.get(_key)
            if _val is None:
                continue

            if frame is None and obj is None:            # 블록 레벨(finalize 등) — params(root leaf)
                meta.params[_key] = handler.Save(
                    meta.root, None, _key, _params_ref(_spec, _val), _val)
                continue

            _is_obj = _spec.get("level", "object") == "object"
            if _is_obj and obj is None:                  # 객체 위치 없음 (frame 단위 호출 등)
                continue
            _target = obj.info if _is_obj else frame.info
            _oid    = obj_id if _is_obj else None
            _target[_key] = handler.Save(
                _root, stem, _key, _data_ref(_spec, _val), _val, obj_id=_oid)

        _objs = source.get("object")
        if isinstance(_objs, list) and frame is not None:  # 구조 교체 — 리스트 순번 = obj_id; leaf 는 보존
            _leaves = {_k: _v for _k, _v in frame.info.items() if not _v.Is_stem()}
            frame.info = {**_leaves, **{str(_i): _n for _i, _n in enumerate(_objs)}}

    def _cache_hit(self, meta: Dataset_Meta) -> bool:
        """재실행 캐시 적중 — cacheable이고 이 flow의 params 출력 키가 meta.params 에 모두 있으면 True."""
        return (self.cacheable
                and bool(self._param_keys)
                and all(_k in meta.params for _k in self._param_keys))

    def __call__(self, meta: Dataset_Meta, progress: Callable[[str, int, int], None] | None = None) -> None:
        _label = self.name or self.object_type     # 진행 표시 이름 (없으면 타입명)
        if self._cache_hit(meta):                  # 이전 실행 결과가 params에 그대로 → 건너뜀
            if progress is not None:
                _n = len(meta.Bucket(WORKING_STATE))
                progress(_label, _n, _n)
            return

        # params(root leaf)는 전 프레임 공통 → 루프 전 한 번만 로드 (root 직속, 상태 무관)
        _params_ctx = _resolve(meta.root, None, meta.params)

        # carry 누산 상태는 이 __call__ 호출에만 사는 transient — 인스턴스에 안 남기고 _finalize로 넘긴다.
        _carry: dict = {}
        _total = len(meta.Bucket(WORKING_STATE))   # flow가 순차 처리할 입력 = working set(modified)
        for _i, (_stem, _frame) in enumerate(meta.Iter_category(WORKING_STATE), start=1):
            # 프레임 ctx는 객체 루프와 무관하게 1회만 구성 (프레임 디코드 중복 방지)
            _frame_ctx = self._build_frame_context(meta, _stem, _frame, **_params_ctx)
            _frame_ctx.update(_carry)               # 직전 프레임 누산 상태 되먹임

            _last_ctx = _frame_ctx
            for _oid, _obj in self._iter_units(_frame):   # unit="frame"이면 1회, "object"면 객체마다
                ctx = {**_frame_ctx, **self._build_object_context(meta, _stem, _oid, _obj)}
                ctx = self._apply_chain(
                    ctx,
                    on_step=lambda idx, out, _oi=_oid, _o=_obj, _s=_stem, _f=_frame:
                        self._route(meta, _s, _f, _oi, _o, self._outputs[idx], out),
                )
                _last_ctx = ctx

            # carry로 선언된 키만 다음 프레임 ctx로 이월 (단일-unit flow에서만 의미)
            _carry = {_k: _last_ctx[_k] for _k in self.carry if _k in _last_ctx}
            if progress is not None:                # {name|object_type} : {this_iter} / {total_iter}
                progress(_label, _i, _total)
        self._finalize(meta, _carry)

    def _finalize(self, meta: Dataset_Meta, carry: dict) -> None:
        """순회 종료 후 1회 도는 reduce 체인 — carry 누산기(scope-1)를 params(scope-2)로 잇는 다리.

        ``carry`` (마지막 프레임의 최종 누산 상태)를 ctx로 돌리며, 각 finalize step이 자기 인라인
        ``outputs`` 로 결과를 라우팅한다 — per-frame step과 **완전히 같은 규칙**이고, frame/obj가
        없어 ``_route`` 가 params(dataset-wide)로 보낸다. 누산기 자체는 어느 step의 출력도 아니면
        영속되지 않는다(필요하면 passthrough finalize step이 자기 outputs로 내보낸다).
        """
        if not self._fin_inners:
            return
        self._apply_chain(
            {"meta": meta, **carry}, chain=self._fin_inners,
            on_step=lambda idx, out:
                self._route(meta, "", None, None, None, self._fin_outputs[idx], out))
