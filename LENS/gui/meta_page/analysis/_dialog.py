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

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QMessageBox, QSplitter, QWidget

from core.analysis import Cluster_Bucket, Mask_Geometry, build, inject, propagate
from core.analysis.store import Type_explosion
from core.constant import CLASS_SRC, SRC_HUMAN, TO_META, TO_STORAGE, UNCLASSIFIED_ID
from core.store import Dataset_Meta
from gui._worker import Pipeline_worker
from gui.widgets import Class_picker, Pop_dialog
from ._panel import Control_panel
from ._view import Result_view

#: 정본 params — 이 데이터셋을 무엇으로 분석하나(transform config 경로).
_CFG_PARAM = "analysis_config"

#: 정본 params — 화면 레시피 ``{unit, obj_index, classes, 묶기 파라미터, domains}``.
#:
#: **산출물이 아니라 정본이 든다** — 레시피는 config 고 버킷은 data 라 수명이 다르다. 한 폴더에 두면
#: ``[feature 삭제]`` 가 도메인 선택까지 지우고, 되살아난 기본값(전부 선택)이 단위 섞인 축을 조용히
#: 켠다.
_RECIPE_PARAM = "analysis_recipe"

#: 레시피 그릇 — **파일(docs)** 이다. 인라인 ``attr`` 은 str·int·float·list 뿐이라 중첩 dict 가 못
#: 간다. 정본 ``params/`` 의 ``id_map.yaml`` 과 같은 자리다.
_RECIPE_SPEC = {"to": TO_STORAGE, "type": "docs", "format": "json"}

#: 기본 전처리 config — **이 레포의 `config/` 안**이다. 학습(413 `conf/transform/`)과 같은 사슬을
#: 태우되 `radial_domains` 만 다르므로(학습은 `rle` 하나) 파일을 갈라 뒀다. 편집 가능하게 노출한다.
_DEFAULT_CFG = str(Path(__file__).resolve().parents[3] / "config/analysis/mask_geometry.yaml")


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
        """지난 세션 이어가기 — config 경로 → 설정 → **저장된 산출물을 바로 건다**.

        **config 경로는 정본이 든다** — 그 경로가 있어야 산출물 폴더를 찾으므로 산출물 안에 둘 수
        없다. 정본에 값이 있으면 그것이 이긴다 — :data:`_DEFAULT_CFG` 는 **한 번도 안 고른 정본을
        위한 씨앗**이지 기본 정책이 아니다.
        """
        _pipe = self._get_pipeline() if self._get_pipeline else None
        if _pipe is None:
            return
        _saved = str((_pipe.meta.Param(_CFG_PARAM) or "") or "")
        if _saved:
            self._panel.set_config_path(_saved)
        else:
            self._remember_config()      # 씨앗도 곧바로 굳힌다 — 다음에 열면 "고른 값"이다
        self._sync_contract()

    def _on_config(self) -> None:
        """config 경로가 확정됐다 — **곧바로 정본에 남기고** 계약을 다시 읽는다.

        옛 구현은 이 값을 :meth:`_remember` 안에서만 썼는데 그건 [feature 생성]·[clustering] 이
        불렀다. 그래서 경로만 고르고 창을 닫으면 다음에 열 때 씨앗값으로 되돌아갔다 — 사용자가 고른
        것이 사라진 자리다. 고르는 것 자체가 결정이므로 누르는 것과 묶지 않는다.
        """
        self._remember_config()
        self._sync_contract()

    def _remember_config(self) -> None:
        """config 경로만 정본에 쓴다 (레시피는 안 건드린다 — 목록이 아직 안 섰을 수 있다).

        **인라인이다** — 파일 codec 에 경로 문자열을 주면 "그 파일을 들여오라"로 읽혀 config 내용이
        통째로 복사된다(``File_Codec.Save`` 는 raw Path 를 복사한다).
        """
        _pipe = self._get_pipeline() if self._get_pipeline else None
        _cfg = self._panel.config_path()
        if _pipe is not None and _cfg:
            _pipe.meta.Put_param(_CFG_PARAM, {"to": TO_META}, _cfg)

    def _remember(self) -> None:
        """지금 설정을 남긴다 — config 경로도 레시피도 **정본**에."""
        _pipe = self._get_pipeline() if self._get_pipeline else None
        _t = self._target()
        if _pipe is None or _t is None:
            return
        _root, _cfg = _t
        self._remember_config()
        _recipe = self._panel.recipe()
        if not self._panel.domain_count():
            # 계약이 없어 표가 **비어 있는 것**이지 사용자가 값을 지운 게 아니다. 이 상태로 덮으면
            # `[feature 삭제]` → `[feature 생성]` 사이에서 도메인별 k 가 조용히 증발한다.
            _recipe["thresholds"] = dict(self._saved_recipe().get("thresholds") or {})
        _pipe.meta.Put_param(_RECIPE_PARAM, _RECIPE_SPEC, _recipe)

    def _saved_recipe(self) -> dict:
        """정본에 남긴 레시피 (없으면 빈 dict)."""
        _pipe = self._get_pipeline() if self._get_pipeline else None
        return dict((_pipe.meta.Param(_RECIPE_PARAM) or {}) if _pipe is not None else {})

    def _sync_contract(self) -> None:
        """계약(``contract`` params)을 읽어 **고를 수 있는 도메인**을 좌측에 채운다.

        정본이 없거나 아직 특징화 전이면 빈 목록이고, 패널이 "계약 없음"이라고 말한다 — 도메인을
        추측하지 않는다(그 목록의 진실은 추출기 계약뿐이다).
        """
        _pipe = self._get_pipeline() if self._get_pipeline else None
        # 레시피는 **산출물과 무관하게** 먼저 얹는다 — 산출물을 지운 뒤에도 설정은 남아 있어야 한다.
        self._panel.load_recipe(self._saved_recipe())
        if _pipe is None:
            self._panel.set_domains({})
            return
        try:
            _bucket = self._open(_pipe.meta.root, params_only=True)
        except Exception as _e:                      # config 가 깨졌다 — 창은 뜨되 이유를 적는다
            self._panel.set_domains({})
            self._panel.set_status(f"config 를 못 읽는다 — {_e}")
            return
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

        여는 김에 **잣대를 config 와 맞춘다** — 여기가 유일한 여는 자리라 한 번만 걸면 된다.
        """
        _b = Cluster_Bucket.Open(root, params_only=params_only)
        self._refresh_gauges(_b)
        return _b

    def _refresh_gauges(self, bucket: Cluster_Bucket) -> None:
        """config 의 잣대를 계약에 **재추출 없이** 반영한다.

        잣대를 계약의 features 와 같이 ``[feature 생성]`` 만 쓰게 두면, config 에 축을 더해도 6만
        표본을 다시 뽑기 전엔 화면에 안 뜬다 — 접는 식만 바뀌었는데 추출을 다시 도는 건 갈라 둔 이유를
        무너뜨린다. 계약이 아직 없으면(추출 전) 손대지 않는다 — 그건 ①이 통째로 쓴다.

        추출기를 짓지만 마스크는 안 태운다(실측 24 ms — 8×8 탐침만 돈다).
        """
        _cfg = self._panel.config_path()
        if not _cfg or not bucket.Contract():
            return
        bucket.Set_gauges(_gauges_of(Mask_Geometry(_cfg).Spec()))

    # ── ① feature 생성 ──────────────────────────────────────────────────────────
    def _on_inject(self) -> None:
        """정본을 훑어 **바뀐 표본만** 특징화해 저장한다 (가장 비싸다)."""
        _t = self._target()
        if _t is None:
            return
        _root, _cfg = _t
        _spec = self._panel.source_spec()

        def _task(_progress) -> None:
            _bucket = self._open(_root)
            _ex = Mask_Geometry(_cfg)
            _c = _ex.Spec()
            _bucket.Set_contract({
                "extractor": type(_ex).__name__,
                "inputs": {_p: _spec.Leaf_of(_p) for _p in _c.inputs},
                "unit": _spec.unit,
                # 두 목록을 **갈라서** 남긴다 — 디스크에 있는 것(features)과 그것을 접어 재는
                # 것(gauges). 잣대만 바뀌면 재추출 없이 다시 접기만 하면 된다.
                "features": {_f: {"shape": list(_o.shape)} for _f, _o in _c.features.items()},
                "gauges": _gauges_of(_c)})
            self._injected = inject(Dataset_Meta.Restore(_root), _bucket, _ex, _spec,
                                    progress=_progress)
            self._opened = _bucket

        self._remember()
        self._injected = None
        self._run(_task, "feature 생성", self._on_inject_done)

    def _on_inject_done(self, ok: bool, info: str) -> None:
        if not self._finish(ok, info, "feature 생성"):
            return
        self._sync_contract()                    # ①이 계약을 남겼다 — 묶기 도메인 목록이 여기서 뜬다
        # 대상 수만 적으면 두 번째 실행도 같은 숫자라 증분이 걸렸는지 알 수 없다 — 재추출 수를 함께.
        _parts = " · ".join(f"{_c} {_v['total']}건(재추출 {_v['extracted']})"
                            for _c, _v in sorted((self._injected or {}).items()))
        self._panel.set_status(f"feature 생성 완료 — {_parts}.  이어서 [clustering]")

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

        def _task(_progress) -> None:
            _bucket = self._open(_root)
            # 잣대는 config 가 늘릴 수 있지만 그 재료(feature)는 추출만이 만든다 — 없는 재료를 가리키는
            # 축은 **조용히 빠지면 안 된다**(체크해 둔 축이 결과에서 사라져도 화면은 성공이라 말한다).
            _have = set(_bucket.Contract().get("features") or {})
            _gone = sorted(_d for _d in _use if (_g := _bucket.Gauges().get(_d)) and _g[0] not in _have)
            if _gone:
                raise KeyError(f"{', '.join(_gone)} 의 feature 가 저장돼 있지 않다 — [feature 생성] 을 다시 돈다")
            build(_bucket, _params, domains=_use, progress=_progress)
            self._opened = _bucket

        self._remember()
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

        self._remember()
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

    def _on_views(self) -> None:
        """도메인 켬/끔·보기 변경 — **재군집 없이** 그림만 다시 그리고 정본에 남긴다."""
        self._view.set_domains(self._panel.enabled_domains())
        self._view.set_views(self._panel.view_modes())
        self._remember()

    def _on_threshold(self, class_id: str, value: float) -> None:
        """결과 화면에서 온 **도메인별 반경** 지정 — 설정에만 올리고 **재군집은 [clustering] 이** 한다.

        여러 도메인을 고친 뒤 한 번에 돌리는 것이 정상 사용이라, 고칠 때마다 다시 뭉치지 않는다.
        """
        _n = self._panel.set_threshold(class_id, value)
        _what = ("공통값으로 되돌림" if value < 0 else f"{value:.3f}σ 로 지정")
        self._remember()                         # 정본에 남긴다 — 창을 닫아도 유지된다
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

        def _task(_progress) -> None:
            _missed = _write_classes(_pipe.meta, _items, _progress)
            if _missed:
                raise KeyError(f"정본에 없거나 객체가 없는 주소 {_missed}건 — 적용이 불완전하다")
            # bucket 은 **index 한 줄**만 고친다 — 파일도 재추출도 **재군집도** 없다. class 는 obj 에
            # 붙은 값이라 배정에 안 들어가고, 바뀌는 것은 저장하지 않는 집계뿐이다.
            _bucket = self._open(_root)
            for _cid in {_c for _, _c in _items}:
                _bucket.Set_class([_a for _a, _c in _items if _c == _cid], _cid)
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
        self._panel.set_status(f"적용 {_n}건 완료 — 배정은 그대로다 (class 는 값이라 안 가른다)")

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
