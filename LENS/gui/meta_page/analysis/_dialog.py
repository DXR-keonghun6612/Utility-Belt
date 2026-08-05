"""Analysis_dialog — 형상 적합성 검증 창 (비모달). **좌우 2분할**이 이 창의 전부다::

    ┌ 제어판 (좁게) ────────┬ 결과 (넓게) ───────────────────────────────┐
    │ transform config       │ 도메인 ▾  해상도 k′ ──●────                 │
    │ 분석 대상 (순회 축)    │ type 목록 │ class 구성 │ 형상                │
    │ 도메인별 반경 k        │ 표본 (거리 순) — 우클릭으로 옮긴다           │
    │ [feature 생성/삭제]    │                                             │
    │ [clustering]           │                                             │
    │ 상태 · 진행바          │                                             │
    └────────────────────────┴─────────────────────────────────────────────┘

**정하는 곳과 보는 곳을 가른다** — 설정은 한 번 맞추고 오래 두는 것이고 결과는 계속 갈아 끼우는 것이라,
세로로 쌓으면 결과를 볼 때마다 설정이 화면을 먹는다.

**정본을 고치는 자리는 [적용] 하나다.** 트리에서 고른 이동은 대기에 모이기만 하고, [적용] 이 stem 당
사이드카 1회로 쓴다. 범주 전이(검수 승격)는 여기 없다 — 라이프사이클은 store 가 소유한다.

**세 국면 중 둘만 버튼이다.** ①(feature 생성)은 가장 비싸고 가장 안 바뀌어 따로 두지만, ②만 돌리면
볼 것이 없으므로 [clustering] 이 ②③을 이어서 한다.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QMessageBox, QSplitter, QWidget

from core.analysis import (
    Cluster_Bucket, Contract, build, inject, propagate, reclass, regroup)
from core.analysis.store import Type_explosion
from core.process.stream.mask import profile
from core.constant import CLASS_SRC, SRC_HUMAN, STAGED, UNCLASSIFIED_ID
from core.store import Dataset_Meta
from gui._worker import Pipeline_worker
from gui.widgets import Class_picker, Pop_dialog
from ._panel import Control_panel
from ._view import Result_view

#: 기본 전처리 config — **이 레포의 `config/` 안**이다. 학습(413 `conf/transform/`)과 같은 사슬을
#: 태우되 `radial_domains` 만 다르므로(학습은 `rle` 하나) 파일을 갈라 뒀다. 편집 가능하게 노출한다.
_DEFAULT_CFG = str(Path(__file__).resolve().parents[3] / "config/gauge/mask_shape.yaml")


def _feature_of(contract: dict) -> tuple[str, tuple[int, ...]]:
    """계약에 적힌 ``(feature 이름, 모양)`` — 없으면 ``("", ())``.

    계약을 다시 세울 때(잣대 갱신) 정본을 열지 않으려고 여기서 읽는다 — 모양은 적재 때 이미 쟀다.
    """
    _feats = (contract.get("features") or {})
    for _name in sorted(_feats):
        return _name, tuple(_feats[_name].get("shape") or ())
    return "", ()


def _profile_shape(store, leaf: str) -> tuple[int, ...] | None:
    """정본이 든 표본 하나치 모양 ``(NT, K)`` — 그 leaf 를 든 **첫 stem** 에서 잰다.

    눈금(``params/profile_spec``)이 있으면 그것으로 답하고, 없으면 배열을 한 장 열어 잰다. 배열의
    첫 축은 객체 수라 떼고 본다. 어느 stem 도 그 leaf 를 안 들면 None — flow 를 안 돌렸다는 뜻이다.
    """
    _spec = store.Param(profile.SPEC_PARAM)
    if isinstance(_spec, dict) and "num_angular" in _spec:
        return (int(_spec["num_angular"]), int(_spec["max_transitions"]))
    for _cat in store.CATEGORIES:
        for _stem, _frame in store.Bucket(_cat).items():
            if _frame.Get(leaf) is None:
                continue
            _arr = store.Load(_stem, leaf)
            if _arr is not None and np.ndim(_arr) >= 2:
                return tuple(np.shape(_arr)[1:])
    return None


def _gauges_of(spec) -> dict:
    """``Extract_Spec`` 의 잣대를 계약에 적을 dict 로 — 쓰는 자리가 둘(추출·갱신)이라 여기 하나."""
    return {_d: {"kind": _o.kind, "shape": list(_o.shape), "feature": _o.feature,
                 "folds": list(_o.folds), "declared": bool(_o.declared)}
            for _d, _o in spec.gauges.items()}


def _write_classes(store, items: list, progress, src: str = SRC_HUMAN) -> int:
    """``[(주소, 새 class), …]`` 를 정본에 쓴다 — **stem 당 사이드카 1회**.

    ``class_id`` 는 객체의 인라인 attr 이라 쓰기 단위가 item 사이드카(``.meta/{범주}/{stem}.json``)다.
    그래서 같은 stem 의 여러 객체를 묶어 한 번만 저장한다. 범주(버킷)는 안 건드린다 — class 이동은
    검수 상태와 무관하다.

    **출처(:data:`~core.constant.CLASS_SRC`)를 함께 쓴다** — 이 창을 거친 것은 전부
    :data:`~core.constant.SRC_HUMAN` 이다. 표본을 봤든 구성표를 봤든 **사람이 결정해** 대기에 올리고
    [적용]을 눌렀기 때문이다. ``src`` 를 인자로 열어 둔 건 나중에 사람 결정 없이 쓰는 경로(모델 예측
    write-back)가 생길 자리라서다.

    Args:
        store: **살아있는 정본** ``Dataset_Meta`` (사본에 쓰면 메인 창이 낡는다).
        items: ``[((stem, obj_index), class_id), …]``.
        progress: ``(라벨, 한 것, 전체)`` 진행 콜백.
        src: 이 batch 의 라벨 출처.

    Returns:
        못 쓴 건수 (정본에 stem 이 없거나 그 번호의 객체가 없을 때) — 조용히 넘기지 않게 센다.
    """
    _by_stem: dict[str, list] = {}
    for (_stem, _obj), _cid in items:
        _by_stem.setdefault(str(_stem), []).append((int(_obj), str(_cid)))
    _missed, _total = 0, len(_by_stem)
    for _i, (_stem, _edits) in enumerate(sorted(_by_stem.items()), 1):
        _item = store.Find(_stem)
        _objs = list(_item.Branches().items()) if _item is not None else []
        _touched = False
        for _obj, _cid in _edits:
            if _obj < len(_objs):
                _objs[_obj][1].Set_attr("class_id", _cid)
                _objs[_obj][1].Set_attr(CLASS_SRC, str(src))
                _touched = True
            else:
                _missed += 1
        if _touched:
            store.Save(_stem)
        progress("적용", _i, _total)
    return _missed


class Analysis_dialog(Pop_dialog):
    """형상 적합성 검증 창 — 좌: 제어판(`Control_panel`) / 우: 결과(`Result_view`).

    Attributes:
        meta_changed: [적용] 으로 정본 class 를 고쳤을 때 emit — 고친 것이 **GUI 가 든 그 store** 라
            값은 이미 맞고 화면만 낡았다. 메인 창은 목록만 다시 그리면 된다.
        stem_focus_requested: 표본 더블클릭 ``(stem, obj)`` — 메인 본문을 그 표본으로 옮겨 달라.
            이 창은 판정만 하고 정본을 안 보므로 **요청만** 올린다.
    """

    meta_changed = Signal()
    stem_focus_requested = Signal(str, int)

    def __init__(self, get_pipeline, parent: QWidget | None = None) -> None:
        """Args:
            get_pipeline: 보유 ``Pipeline`` 을 돌려주는 콜백 (없으면 None — Sampler 와 동일 패턴).
            parent: 부모 위젯.
        """
        super().__init__("형상 적합성 검증", size=(1180, 780), parent=parent)
        self._get_pipeline = get_pipeline
        self._thread: QThread | None = None
        self._worker: Pipeline_worker | None = None
        self._done_cb = None                     # 워커 완료 시 메인 스레드에서 부를 콜백
        self._injected: dict | None = None       # ① 산출 (상태별 표본 수)
        self._propagated: dict | None = None      # [메움 전파] 산출 (도메인별 건수)
        self._opened: Cluster_Bucket | None = None   # 워커가 열어 둔 bucket — 화면이 이걸 묻는다
        #: 아직 정본에 안 쓴 이동 ``{(stem, obj): 새 class}`` — [적용] 이 한 번에 쓴다.
        self._pending: dict[tuple, str] = {}

        self._panel = Control_panel(_DEFAULT_CFG)
        self._panel.inject_requested.connect(self._on_inject)
        self._panel.drop_requested.connect(self._on_drop)
        self._panel.cluster_requested.connect(self._on_cluster)
        self._panel.config_changed.connect(self._on_config)
        self._panel.apply_requested.connect(self._on_apply)
        self._panel.discard_requested.connect(self._on_discard)
        self._view = Result_view()
        self._view.move_requested.connect(self._on_move)
        self._view.unlabel_requested.connect(self._on_unlabel)
        self._view.stage_requested.connect(self._on_stage)
        self._view.unify_requested.connect(self._on_unify)
        self._view.threshold_requested.connect(self._on_threshold)
        self._view.propagate_requested.connect(self._on_propagate)
        self._view.focus_requested.connect(self.stem_focus_requested)   # 그대로 상위로
        self._panel.views_changed.connect(self._on_views)

        _split = QSplitter(Qt.Orientation.Horizontal)
        _split.addWidget(self._panel)
        _split.addWidget(self._view)
        _split.setStretchFactor(0, 0)            # 결과가 넓어진다 — 제어판은 제 폭만 든다
        _split.setStretchFactor(1, 1)
        _split.setSizes([330, 850])
        self._set_body(_split)
        self._bottom_bar(on_reject=self.accept)
        self._restore()

    def _restore(self) -> None:
        """지난 세션 이어가기 — 산출물이 든 설정으로 config 경로까지 되돌린다.

        **정본은 안 건드린다.** 설정은 그 결과를 만든 폴더(``.analysis/``)가 든다 — 같은 정본을
        다른 조건으로 여러 번 돌려도 서로 안 섞인다. ``[feature 삭제]`` 로 그 폴더를 지우면 설정도
        함께 사라지고 :data:`_DEFAULT_CFG` 씨앗에서 다시 시작한다.
        """
        if (self._get_pipeline() if self._get_pipeline else None) is None:
            return
        _cfg = str(self._saved_recipe().get("config") or "")
        if _cfg:
            self._panel.set_config_path(_cfg)
        self._sync_contract()

    def _on_config(self) -> None:
        """config 경로가 확정됐다 — 계약을 다시 읽는다. **쓰지 않는다**(저장은 [clustering] 뿐)."""
        self._sync_contract()

    def _saved_recipe(self, bucket: Cluster_Bucket | None = None) -> dict:
        """산출물(``.analysis/``)이 든 설정. ``bucket`` 을 안 주면 params 만 열어 읽는다(밀리초)."""
        _pipe = self._get_pipeline() if self._get_pipeline else None
        if bucket is not None:
            return bucket.Recipe()
        if _pipe is None or not Path(Cluster_Bucket.Root(_pipe.meta.root)).exists():
            return {}
        try:
            return Cluster_Bucket.Open(_pipe.meta.root, params_only=True).Recipe()
        except Exception:                            # 산출물이 낡았거나 깨졌다 — 창은 뜬다
            return {}

    def _sync_contract(self) -> None:
        """계약(``contract`` params)을 읽어 **고를 수 있는 도메인**을 좌측에 채운다.

        정본이 없거나 아직 특징화 전이면 빈 목록이고, 패널이 "계약 없음"이라고 말한다 — 도메인을
        추측하지 않는다(그 목록의 진실은 추출기 계약뿐이다).
        """
        _pipe = self._get_pipeline() if self._get_pipeline else None
        if _pipe is None:
            self._panel.load_recipe(self._saved_recipe())
            self._panel.set_domains({})
            return
        try:
            _bucket = self._open(_pipe.meta.root, params_only=True)
        except Exception as _e:                      # config 가 깨졌다 — 창은 뜨되 이유를 적는다
            self._panel.load_recipe(self._saved_recipe())
            self._panel.set_domains({})
            self._panel.set_status(f"config 를 못 읽는다 — {_e}")
            return
        self._refresh_gauges(_bucket)                # 계약을 config 와 맞추는 **유일한 자리**
        self._panel.load_recipe(self._saved_recipe(_bucket))
        self._panel.set_domains(_bucket.Kinds(), _bucket.Gauges(), _bucket.Declared())
        if _bucket.Index():                          # 저장분이 있으면 **바로 건다**
            self._opened = _bucket
            try:
                self._show()
            except Type_explosion as _e:
                # 자동 복원이 **탈출구를 막으면 안 된다.** 죽은 산출물을 그리려다 창이 못 뜨면
                # [feature 삭제] 를 누를 방법이 없어 밖에서 폴더를 지워야 했다.
                self._view.set_bucket(None)
                self._panel.set_status(f"저장분을 못 건다 — {_e}")

    # ── 설정 → core 인자 ────────────────────────────────────────────────────────
    def _target(self) -> tuple[str, str] | None:
        """``(dataset_root, transform_config)`` — 둘 중 하나라도 없으면 None(상태에 적는다)."""
        _pipe = self._get_pipeline() if self._get_pipeline else None
        _cfg = self._panel.config_path()
        if _pipe is None:
            self._panel.set_status("dataset_root 미설정 — 정본을 먼저 연다")
            return None
        if not _cfg:
            self._panel.set_status("transform config 경로가 비었다")
            return None
        return _pipe.meta.root, _cfg

    def _open(self, root: str, *, params_only: bool = False) -> Cluster_Bucket:
        """이 정본의 산출물 bucket — **모델을 안 짓는다**(자리는 정본 하나로 정해진다).

        ``params_only`` 는 계약·index 만 물을 때다. 전체 복원은 6만 사이드카라 실측 4.0 s 이고 그게
        GUI 스레드에서 돌면 창이 언다 — params 만이면 밀리초다. **전체를 여는 경로는 전부 워커 안**이다.

        **계약은 안 건드린다.** 잣대를 config 와 맞추는 일은 :meth:`_sync_contract` 만 한다 —
        여기 붙여 두면 class 이동·적용·전파처럼 계약과 무관한 걸음까지 config 를 다시 읽어 덮는다.
        """
        return Cluster_Bucket.Open(root, params_only=params_only)

    def _refresh_gauges(self, bucket: Cluster_Bucket) -> None:   # noqa: D401  (_sync_contract 전용)
        """config 의 잣대를 계약에 **다시 모으지 않고** 반영한다.

        잣대를 계약의 features 와 같이 ``[적재]`` 만 쓰게 두면, config 에 축을 더해도 6만 표본을 다시
        모으기 전엔 화면에 안 뜬다 — 접는 식만 바뀌었는데 적재를 다시 도는 건 갈라 둔 이유를 무너뜨린다.
        계약이 아직 없으면(적재 전) 손대지 않는다 — 그건 ①이 통째로 쓴다.

        **마스크도 config 의 모듈도 안 태운다** — 계약이 드는 것은 정본이 이미 든 배열의 모양과
        config 의 잣대뿐이다.
        """
        _cfg = self._panel.config_path()
        _contract = bucket.Contract()
        if not _cfg or not _contract:
            return
        _feat, _shape = _feature_of(_contract)
        if _feat:
            bucket.Set_gauges(_gauges_of(Contract(_cfg, _feat, _shape)))

    # ── ① 적재 ─────────────────────────────────────────────────────────────────
    def _on_inject(self) -> None:
        """정본을 훑어 목록을 세우고 표본 벡터를 **묶음별로 모은다**.

        값을 만드는 것은 flow 다(``radial_profile``) — 여기는 그것을 읽어 묶는다. 정본에 그 배열이
        없으면(flow 를 안 돌렸으면) 대상이 0 건으로 나온다.
        """
        _t = self._target()
        if _t is None:
            return
        _root, _cfg = _t
        _spec = self._panel.source_spec()

        def _task(_progress) -> None:
            _store = Dataset_Meta.Restore(_root)
            _shape = _profile_shape(_store, _spec.leaf)
            if _shape is None:
                raise RuntimeError(
                    f"정본에 '{_spec.leaf}' 배열이 없다 — flow(radial_profile)를 먼저 돌린다")
            _bucket = self._open(_root)
            _c = Contract(_cfg, _spec.leaf, _shape)
            _bucket.Set_contract({
                "source": "canonical",
                "inputs": {_spec.leaf: _spec.leaf},
                "unit": _spec.unit,
                # 두 목록을 **갈라서** 남긴다 — 정본에 있는 것(features)과 그것을 접어 재는
                # 것(gauges). 잣대만 바뀌면 다시 모으지 않고 접기만 하면 된다.
                "features": {_f: {"shape": list(_o.shape)} for _f, _o in _c.features.items()},
                "gauges": _gauges_of(_c)})
            self._injected = inject(_store, _bucket, _spec, _c, progress=_progress)
            self._opened = _bucket

        self._injected = None
        self._run(_task, "적재", self._on_inject_done)

    def _on_inject_done(self, ok: bool, info: str) -> None:
        if not self._finish(ok, info, "적재"):
            return
        self._sync_contract()                    # ①이 계약을 남겼다 — 묶기 도메인 목록이 여기서 뜬다
        # 대상 수만 적으면 두 번째 실행도 같은 숫자라 증분이 걸렸는지 알 수 없다 — 새로 모은 수를 함께.
        _parts = " · ".join(f"{_c} {_v['total']}건(새로 모음 {_v['collected']})"
                            for _c, _v in sorted((self._injected or {}).items()))
        self._panel.set_status(f"적재 완료 — {_parts}.  이어서 [clustering]")

    # ── ②③ clustering (묶고 그대로 판정) ────────────────────────────────────────
    def _on_cluster(self) -> None:
        """저장된 feature 로 **바뀐 도메인만** 다시 뭉친다."""
        _t = self._target()
        if _t is None:
            return
        _root, _cfg = _t
        _spec = self._panel.source_spec()
        _params = self._panel.cluster_params()
        _use = self._panel.enabled_domains()
        if self._panel.domain_count() and not _use:
            self._panel.set_status("분석할 도메인을 하나 이상 켜야 한다 — 좌측 도메인 탭에서 체크한다")
            return

        _recipe = {**self._panel.recipe(), "config": _cfg}

        def _task(_progress) -> None:
            _bucket = self._open(_root)
            _bucket.Set_recipe(_recipe)          # 이 산출물을 만든 설정 — 폴더가 스스로 든다
            # 잣대는 config 가 늘릴 수 있지만 그 재료(feature)는 추출만이 만든다 — 없는 재료를 가리키는
            # 축은 **조용히 빠지면 안 된다**(체크해 둔 축이 결과에서 사라져도 화면은 성공이라 말한다).
            _have = set(_bucket.Contract().get("features") or {})
            _gone = sorted(_d for _d in _use if (_g := _bucket.Gauges().get(_d)) and _g[0] not in _have)
            if _gone:
                raise KeyError(f"{', '.join(_gone)} 의 feature 가 적재돼 있지 않다 — [적재] 를 다시 돈다")
            _done = build(_bucket, _params, domains=_use, progress=_progress)
            # 배정이 섰으니 캐시를 **type 축으로** 다시 편성한다 — 템플릿·재군집이 그 단위로 돌고,
            # class 축으로는 type 하나를 읽는 데 여러 파일을 다 열어야 한다. 축은 하나만 고른다
            # (여럿이면 같은 표본이 축마다 복제된다) — 사람이 켠 것 중 첫째.
            _axis = next((_d for _d in _use if _d in _done), "")
            if _axis:
                regroup(_bucket, _axis, progress=_progress)
            self._opened = _bucket

        self._run(_task, "clustering", self._on_cluster_done)

    def _on_cluster_done(self, ok: bool, info: str) -> None:
        if not self._finish(ok, info, "clustering"):
            return
        if self._opened is None or not self._opened.Index():
            self._panel.set_status("묶을 표본이 없다 — [feature 생성] 을 먼저 누른다")
            self._view.set_bucket(None)
            return
        self._show()

    def _on_propagate(self) -> None:
        """[메움 전파] — 종합이 메운 자리를 축 배정에 앉힌다 (재군집 없음).

        되돌릴 수 없는 **판단**이라 확인을 묻는다. 자동으로 돌면 측정(잣대가 문턱을 넘어 인정한 것)과
        추정(다른 축을 참고해 붙인 것)이 소리 없이 섞인다.
        """
        _t = self._target()
        if _t is None or self._opened is None:
            return
        _root, _ = _t
        _n = len(self._opened.Joint().get("imputed") or {})
        if not _n:
            self._panel.set_status("메운 자리가 없다 — [clustering] 을 먼저 돌린다")
            return
        if QMessageBox.question(
                self, "메움 전파",
                f"종합이 추정으로 붙인 {_n:,}건을 축 배정에 반영합니다.\n"
                "그 축의 중심·퍼짐·구성표가 바뀌고, 되돌리려면 [clustering] 을 다시 돌려야 합니다.\n"
                "계속할까요?") != QMessageBox.StandardButton.Yes:
            return

        def _task(_progress) -> None:
            _bucket = self._open(_root)
            self._propagated = propagate(_bucket, self._panel.cluster_params(),
                                         progress=_progress)
            self._opened = _bucket

        self._run(_task, "메움 전파", self._on_propagate_done)

    def _on_propagate_done(self, ok: bool, info: str) -> None:
        if not self._finish(ok, info, "메움 전파"):
            return
        _parts = " · ".join(f"{_d} {_n:,}건"
                            for _d, _n in sorted((self._propagated or {}).items()))
        self._show()
        self._panel.set_status(f"메움 전파 완료 — {_parts or '반영할 것 없음'}")

    def _show(self) -> None:
        """bucket 을 뷰에 건다 — 값은 뷰가 거기 물어본다.

        bucket 은 **워커가 이미 열어 둔 것**이다 — 여기서 열면 메인 스레드가 수 초 멈춘다.
        """
        _bucket = self._opened
        # 계약이 늘거나 줄었으면 목록도 따라간다
        self._panel.set_domains(_bucket.Kinds(), _bucket.Gauges(), _bucket.Declared())
        self._view.set_class_names(self._class_names())
        self._view.set_bucket(_bucket)
        self._view.set_domains(self._panel.enabled_domains())
        self._view.set_views(self._panel.view_modes())
        _parts = " · ".join(f"{_s} class {len(_bucket.Classes(_s))}"
                            for _s in _bucket.CATEGORIES if _bucket.Classes(_s))
        _n = len(_bucket.Index())
        self._panel.set_status(f"완료 — 표본 {_n}  ({_parts})")

    def _class_names(self) -> dict:
        """정본 id_map 의 ``{class_id: 이름}`` — 뷰가 번호 대신 이름을 보이게."""
        _pipe = self._get_pipeline() if self._get_pipeline else None
        return _pipe.Class_names() if _pipe is not None else {}

    # ── 이동 — 대기에 모으고 [적용] 이 한 번에 쓴다 ───────────────────────────────
    # **키는 주소 ``(stem, obj)`` 다.** 순회 축이 한 프레임의 객체 여럿을 낼 수 있어 stem 을 키로 두면
    # 같은 프레임의 다른 결정을 덮어쓴다. type 번호도 키가 될 수 없다(재군집하면 뜻이 달라진다).
    def _on_move(self, addresses: list, class_id: str) -> None:
        """[class 이동…] — picker 로 대상 class 를 받아 대기에 올린다 (정본은 안 건드린다)."""
        _cid = class_id or self._pick_class()
        if _cid is None or not addresses:
            return
        self._stage(addresses, str(_cid))

    def _on_unify(self, plan: list) -> None:
        """[최다 class 로 통일] — type 마다 다른 목적지를 **한 번에** 대기에 올린다.

        :meth:`_stage` 를 type 수만큼 부르지 않는 건 상태 문구 때문이다 — 한 동작인데 "방금 N건 → X" 가
        마지막 type 것만 남으면 무엇을 했는지 못 읽는다. 여기서 통째로 접수하고 한 줄로 알린다.
        """
        _n = 0
        for _addrs, _cid in plan:
            for _a in _addrs:
                self._pending[(str(_a[0]), int(_a[1]))] = str(_cid)
                _n += 1
        if not _n:
            return
        self._view.set_pending(self._pending)
        self._sync_pending()
        self._panel.set_status(
            f"대기 {len(self._pending)}건 — 방금 {len(plan)} type 의 소수파 {_n}건을 "
            f"각 type 의 최다 class 로 모았다.  [적용] 이 정본에 쓴다")

    def _on_unlabel(self, addresses: list) -> None:
        """[미분류로] — 판단에서 빼고 사람 앞에 남긴다.

        최근접 남의 class 로 옮기지 **않는다**: 화면이 말하는 것은 "지금 붙은 자리가 틀렸다"까지고
        "그 남이 정답이다"는 근거가 없다. 잘못 붙은 것을 다른 데 잘못 붙이면 틀린 라벨이 자리만 옮기고
        이력에서 사라진다.
        """
        if addresses:
            self._stage(addresses, str(UNCLASSIFIED_ID))

    def _on_stage(self, addresses: list) -> None:
        """고른 표본이 든 **프레임**을 STAGED 로 보낸다 — 정본 전이라 확인을 받는다.

        전이 단위가 프레임이라 같은 프레임의 다른 객체도 함께 간다. 그 수를 세어 보이고 누르게 한다 —
        분석 화면은 객체 단위라 이 차이가 안 보이면 의도보다 많이 옮겨진다.

        **대기에 안 쌓는다.** 대기는 class 이동(값 편집)의 자리고, 이건 검수 상태 전이라 성격이 다르다.
        """
        _pipe = self._get_pipeline() if self._get_pipeline else None
        if _pipe is None or not addresses or self._thread is not None:
            return
        _stems = sorted({str(_a[0]) for _a in addresses})
        _all = sum(len(_it.Branches()) for _s in _stems
                   if (_it := _pipe.meta.Find(_s)) is not None)
        if QMessageBox.question(
                self, "STAGED 로",
                f"고른 표본 {len(addresses):,} 건이 든 **프레임 {len(_stems):,} 개**를 "
                f"STAGED 로 보낸다.\n\n"
                f"전이 단위가 프레임이라 그 안의 객체 **{_all:,} 개가 함께** 간다"
                f"{f' (고른 것 외 {_all - len(addresses):,} 개 포함)' if _all > len(addresses) else ''}.\n"
                f"되돌리려면 메인 창에서 다시 전이해야 한다.\n\n보낼까?") != QMessageBox.Yes:
            return

        def _task(_progress) -> None:
            for _i, _s in enumerate(_stems, 1):
                _pipe.meta.Move(_s, STAGED)
                _progress("STAGED 로", _i, len(_stems))

        self._run(_task, "전이", self._on_stage_done)

    def _on_stage_done(self, ok: bool, info: str) -> None:
        if not self._finish(ok, info, "전이"):
            return
        self.meta_changed.emit()                 # 정본이 바뀌었다 — 메인 창 목록을 다시 그린다
        self._panel.set_status(
            "STAGED 로 보냈다.  산출물의 상태는 다음 [적재] 때 따라온다 "
            "(`index.state` 는 적재가 쓴다)")

    def _on_views(self) -> None:
        """도메인 켬/끔·보기 변경 — **재군집 없이** 그림만 다시 그리고 정본에 남긴다."""
        self._view.set_domains(self._panel.enabled_domains())
        self._view.set_views(self._panel.view_modes())

    def _on_threshold(self, class_id: str, value: float) -> None:
        """결과 화면에서 온 **도메인별 반경** 지정 — 설정에만 올리고 **재군집은 [clustering] 이** 한다.

        여러 도메인을 고친 뒤 한 번에 돌리는 것이 정상 사용이라, 고칠 때마다 다시 뭉치지 않는다.
        """
        _n = self._panel.set_threshold(class_id, value)
        _what = ("공통값으로 되돌림" if value < 0 else f"{value:.3f}σ 로 지정")
        self._panel.set_status(
            f"{class_id} → {_what} (도메인별 지정 {_n}개).  "
            f"[clustering] 이 **그 도메인만** 다시 가른다")

    def _stage(self, addresses: list, class_id: str) -> None:
        """이동을 대기에 올린다 — 같은 주소를 두 번 고르면 마지막 결정이 이긴다."""
        for _a in addresses:
            self._pending[(str(_a[0]), int(_a[1]))] = str(class_id)
        self._view.set_pending(self._pending)
        self._sync_pending()
        self._panel.set_status(
            f"대기 {len(self._pending)}건 — 방금 {len(addresses)}건 → "
            f"{self._class_names().get(str(class_id), class_id)}.  [적용] 이 정본에 쓴다")

    def _pick_class(self) -> str | None:
        """class picker 로 대상 class_id 를 받는다 (취소·목록 없음이면 None)."""
        _names = self._class_names()
        if not _names:
            self._panel.set_status("id_map 이 비어 있다 — 고를 class 가 없다")
            return None
        _picker = Class_picker({str(_n): str(_c) for _c, _n in _names.items()}, parent=self)
        return _picker.selected() if _picker.exec() else None

    def _sync_pending(self) -> None:
        """대기 건수를 버튼에 반영 — 대기는 **보여야** 잊히지 않는다."""
        self._panel.set_pending(len(self._pending))

    def _on_discard(self) -> None:
        """[대기 취소] — 모아 둔 이동을 버린다. 정본은 애초에 안 건드렸으니 되돌릴 것이 없다."""
        _n = len(self._pending)
        self._pending.clear()
        self._view.set_pending({})
        self._sync_pending()
        self._panel.set_status(f"대기 {_n}건 취소 (정본은 안 바뀌었다)")

    def _on_apply(self) -> None:
        """[적용] — 대기를 정본에 **한 번에** 쓴다. 재군집은 없다(class 는 배정에 안 들어간다)."""
        if not self._pending or self._thread is not None:
            return
        _items = sorted(self._pending.items())
        _names = self._class_names()
        _tally: dict[str, int] = {}
        for _, _cid in _items:
            _tally[_cid] = _tally.get(_cid, 0) + 1
        _lines = [f"  → {_names.get(_c, _c)}   ({_n}건)" for _c, _n in sorted(_tally.items())]
        if QMessageBox.question(
                self, "적용",
                f"대기 중인 class 이동 {len(_items)}건을 정본에 쓴다.\n"
                f"검수 상태(버킷)는 그대로다.\n\n" + "\n".join(_lines[:12])
                + (f"\n  … 외 {len(_lines) - 12}종" if len(_lines) > 12 else "")
                + "\n\n쓸까?") != QMessageBox.Yes:
            return

        _pipe = self._get_pipeline() if self._get_pipeline else None
        _t = self._target()
        if _pipe is None or _t is None:
            return
        _root, _cfg = _t

        _spec = self._panel.source_spec()

        def _task(_progress) -> None:
            _missed = _write_classes(_pipe.meta, _items, _progress)
            if _missed:
                raise KeyError(f"정본에 없거나 객체가 없는 주소 {_missed}건 — 적용이 불완전하다")
            # 산출물은 **옮긴 class 만** 다시 모은다 — 정본 전수 순회 없이 두 묶음뿐이다.
            # `index.class` 와 캐시 묶음이 한 걸음에서 함께 고쳐진다(주소가 곧 class 라 갈라지면
            # 그 행을 못 찾는다). 군집 결과·정규화 상수는 안 건드린다.
            _bucket = self._open(_root)
            self._reclassed = reclass(_pipe.meta, _bucket, _spec, _items, _progress)
            self._opened = _bucket

        self._run(_task, "적용", self._on_apply_done)

    def _on_apply_done(self, ok: bool, info: str) -> None:
        if not self._finish(ok, info, "적용"):
            return
        _n = len(self._pending)
        self._pending.clear()
        self._view.set_pending({})
        self._sync_pending()
        self.meta_changed.emit()                 # 정본이 바뀌었다 — 메인 창 목록을 다시 그린다
        if self._opened is None:
            self._panel.set_status(f"적용 {_n}건 — 볼 산출물이 없다")
            return
        self._show()
        _re = getattr(self, "_reclassed", {}) or {}
        self._panel.set_status(
            f"적용 {_n}건 완료 — 정본에 쓰고 옮긴 묶음 {len(_re)}개만 다시 모았다"
            f"{' (' + ' · '.join(f'{_c} {_v:,}' for _c, _v in sorted(_re.items())) + ')' if _re else ''}."
            f"  배정은 그대로다 (class 는 값이라 안 가른다)")

    # ── feature 삭제 ────────────────────────────────────────────────────────────
    def _on_drop(self) -> None:
        """산출물 폴더를 통째로 지운다 — 통계도 함께다(feature 에서 파생된 것이라).

        **정본은 안 건드린다.** 산출물이 정본 트리 밖(``.analysis/``)에 살아서 폴더 하나를 지우는
        일로 끝난다.
        """
        _t = self._target()
        if _t is None or self._thread is not None:
            return
        _root, _cfg = _t
        _dir = Path(Cluster_Bucket.Root(_root))  # 경로만 필요하다 — 열지 않는다(복원 4 s)
        if not _dir.exists():
            self._panel.set_status("지울 산출물이 없다")
            return
        if QMessageBox.question(
                self, "feature 삭제",
                f"산출물을 통째로 지운다 (feature · 통계 · index):\n{_dir}\n\n"
                f"정본과 **화면 설정(레시피)은 안 건드린다** — 지금 고른 도메인·파라미터는 그대로\n"
                f"남아서 [feature 생성] 을 다시 눌러도 같은 조건으로 돈다. 계속?"
                ) != QMessageBox.Yes:
            return
        shutil.rmtree(_dir)
        self._opened = None
        self._view.set_bucket(None)
        # 계약이 사라졌으니 고를 목록도 없다 — 다만 선택은 레시피가 들고 있어 목록이 다시 서면 얹힌다.
        self._panel.set_domains({})
        self._panel.set_progress("대기", 0)
        self._panel.set_status(f"산출물 삭제: {_dir.name} — 설정은 그대로다. [feature 생성] 부터")

    # ── 실행 (worker) ───────────────────────────────────────────────────────────
    def _run(self, task, verb: str, on_done) -> None:
        """국면 하나를 워커로 돌린다 — 재진입 가드·잠금·진행바가 둘에 같다.

        Args:
            task: ``(progress) -> None`` — 국면 본체. 국면끼리 산출을 메모리로 주고받지 않는다
                (디스크가 그 자리다).
            verb: 상태·진행바에 적을 동사.
            on_done: ``(ok, info)`` 완료 콜백 (메인 스레드).
        """
        _pipe = self._get_pipeline() if self._get_pipeline else None
        if _pipe is None or self._thread is not None:      # 재진입 가드
            return
        self._panel.set_busy(True)
        self._panel.set_status(f"{verb} 중…")
        self._panel.set_progress("준비 중…")                # busy — 개수를 아직 모른다
        self._done_cb = on_done
        self._thread = QThread()
        self._worker = Pipeline_worker(_pipe, task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)   # 바운드 메서드 = 큐드 연결
        self._worker.finished.connect(self._on_worker_done)
        self._thread.start()

    def _finish(self, ok: bool, info: str, verb: str) -> bool:
        """완료 공통 — 스레드를 접고 잠금을 푼다. 실패면 상태에 적고 False."""
        self._end_worker()
        self._panel.set_busy(False)
        if not ok:
            self._panel.set_progress("실패", 0)
            self._panel.set_status(f"{verb} 실패: {info.splitlines()[-1] if info else ''}")
            return False
        self._panel.set_progress("완료", 1)
        return True

    def _on_progress(self, done: int, total: int, label: str) -> None:
        """진행 통지 — ``total<=0`` 은 아직 개수를 모르는 단계(busy 막대)."""
        if total > 0:
            self._panel.set_progress(f"{label} : %v / %m", done, total)
        else:
            self._panel.set_progress(label or "…")

    def _on_worker_done(self, ok: bool, info: str) -> None:
        """워커 완료 — **메인 스레드**. 등록해 둔 콜백으로 넘긴다(1회만).

        ``finished`` 를 콜백에 **직접** 잇지 않는 이유가 있다: 람다처럼 QObject 가 아닌 콜러블에 이으면
        Qt 가 받을 스레드를 정할 수 없어 direct 연결이 되고, 그러면 콜백이 워커 스레드에서 돈다. 거기서
        :meth:`_end_worker` 가 ``wait()`` 를 부르면 **자기 자신을 기다리다** 프로세스가 죽는다.
        """
        _cb, self._done_cb = self._done_cb, None
        if _cb is not None:
            _cb(ok, info)

    def _end_worker(self) -> None:
        """스레드를 접는다. **자기 자신은 기다리지 않는다** — 그건 교착이자 크래시다."""
        _th, self._thread, self._worker = self._thread, None, None
        if _th is None:
            return
        _th.quit()
        if _th is not QThread.currentThread():
            _th.wait()
