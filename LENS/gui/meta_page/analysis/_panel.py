"""좌측 제어판 — **무엇을 분석할지 정하고 국면을 시킨다.** 결과는 안 든다(그건 `_view`).

편집하는 것이 곧 `core.analysis` 의 인자다: transform config 경로 · `Source_Spec`(순회 축) ·
`Cluster_Params`(묶기 파라미터). 그 셋이면 두 국면을 부를 것이 다 모이므로 **여기서 새로 만드는
개념이 없다** — 새 필드가 필요하면 core 계약에 먼저 생긴다.

**core 를 실행하지 않는다** — 값을 내고 신호를 쏘는 데까지고, 워커·store 는 `_dialog` 가 든다.

버튼이 셋인 이유는 **비용이 셋으로 갈리기 때문**이다: feature 생성은 정본 전수 특징화(가장 비싸다),
삭제는 그 산출물을 통째로 버리는 일, clustering 은 저장된 feature 위에서만 도는 일.

**도메인을 한 좌표로 안 합친다** — 각자 갈린다. 그래서 설정도 도메인마다 따로 든다
(:meth:`Control_panel._build_domains`).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QProgressBar, QPushButton, QSpinBox, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.analysis.cluster import (
    NORM_EQUALIZE, NORM_FLOOR, NORM_NONE, Cluster_Params)
from core.analysis.inject import FRAME, OBJECT, Source_Spec
from gui.form._form import Config_form
from gui.form._spec import specs_from_callable
from gui.widgets import Path_row

#: 순회 축 — 표시 이름 ↔ `Source_Spec.unit` 값.
_UNITS = ((OBJECT, "object — 프레임의 객체마다"), (FRAME, "frame — 프레임 하나가 한 표본"))

#: 폼이 자동으로 못 만드는 필드 — 고를 목록이 **추출기 계약**에 달렸다(:meth:`Control_panel.set_domains`).
_THRESHOLDS_FIELD = "thresholds"
_NEIGHBORS_FIELD = "neighbor_counts"
_MEMBERS_FIELD = "min_member_counts"
_WELD_FIELD = "weld_axes"

#: 도메인별 spinbox 의 "공통값 사용" 자리 — 0 은 거리로도 이웃 수로도 뜻이 없어 특수값으로 쓴다.
_COMMON = 0.0
_COMMON_N = 0

#: 도메인별 **보기 방법** — 값의 좌표계는 원래 추출기 계약(`Feature_Spec.axis`)이 답해야 하는데
#: `radial_rle` 이 아직 선언하지 않아 **여기가 유일한 출처**다.
#:
#: **묶기 파라미터가 아니다** — `cluster_params()` 에 넣으면 도메인 서명이 바뀌어 보기만 고쳐도
#: 재군집이 돈다. 그래서 `recipe()` 에만 실린다.
_VIEWS_FIELD = "views"
#: 레시피 열쇠 — 분석에 쓸 도메인. 없는 이름은 **켠 것**으로 본다(새 도메인이 조용히 빠지면 안 된다).
_ENABLED_FIELD = "enabled"
_VIEW_MODES = (("auto", "자동"), ("silhouette", "실루엣"), ("channels", "채널"))

#: 축별 **종합 병합** — ``None`` 은 공통값 사용(다른 칸의 `공통` 과 같은 자리).
_WELD_MODES = ((None, "공통"), (True, "켬"), (False, "끔"))

#: 축별 **정규화** — `k` 의 단위를 정한다. 공통값이 없다(축마다 다른 것이 요점).
_NORM_FIELD = "norm_methods"
_NORM_MODES = ((NORM_EQUALIZE, "σ (기본)"), (NORM_NONE, "원 단위"), (NORM_FLOOR, "노이즈 바닥"))


class Control_panel(QWidget):
    """분석 대상·파라미터 설정 + 국면 버튼 + 상태 표시.

    Attributes:
        inject_requested: [feature 생성] — 정본을 훑어 바뀐 표본만 특징화.
        drop_requested: [feature 삭제] — 이 설정의 산출물을 버린다.
        cluster_requested: [clustering] — 저장된 feature 로 도메인마다 type 을 세운다.
        config_changed: transform config 경로가 확정됐다 — 산출물이 갈리므로 계약을 다시 읽어야 한다.
        apply_requested: [적용] — 모아 둔 이동을 정본에 쓴다.
        discard_requested: [대기 취소] — 모아 둔 이동을 버린다.
        views_changed: 도메인별 보기 방법이 바뀌었다 — **재군집 없이** 그림만 다시 그린다.
    """

    inject_requested = Signal()
    drop_requested = Signal()
    cluster_requested = Signal()
    config_changed = Signal()
    apply_requested = Signal()
    discard_requested = Signal()
    views_changed = Signal()

    def __init__(self, config_path: str = "", parent: QWidget | None = None) -> None:
        """Args:
            config_path: transform config(yaml) 초기 경로.
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._pending = 0                        # 대기 건수 (버튼 잠금 조건)
        self._busy = False
        self._wanted: dict[str, float] | None = None   # 복원된 도메인별 k — 목록이 선 뒤에 얹는다
        self._wanted_nb: dict[str, int] = {}
        self._wanted_mm: dict[str, int] = {}
        self._wanted_weld: dict[str, bool] = {}
        self._wanted_norm: dict[str, str] = {}
        self._wanted_views: dict[str, str] = {}
        self._wanted_on: set[str] | None = None
        self._domain_state: dict[str, dict] = {}
        self._build(config_path)

    # ── 구성 ────────────────────────────────────────────────────────────────────
    def _build(self, config_path: str) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(4, 4, 4, 4)

        # ↺ 는 **계약 다시 읽기**다 — 창을 열 때 산출물을 복원하면(6만 사이드카) 창이 늦게 뜨므로,
        # 지난 세션 산출물의 도메인 목록은 사용자가 이걸로 부른다.
        self._cfg = Path_row("transform config:", mode="file", refresh=True,
                             file_filter="YAML (*.yaml *.yml)")
        self._cfg.setText(config_path)
        self._cfg.setToolTip("전처리 config (crop → resize → geometry). 이걸 고치면 계약이 바뀌므로 "
                             "[feature 생성] 을 다시 돌려야 한다 — 산출물 자리는 정본당 하나다")
        self._cfg.committed.connect(self.config_changed)
        _lay.addWidget(self._cfg)

        _lay.addWidget(_heading("분석 대상"))
        _lay.addWidget(self._build_source())

        _lay.addWidget(_heading("묶기 파라미터"))
        # 도메인별 dict 두 개는 폼에서 뺀다 — 고를 목록이 dataclass 가 아니라 **추출기 계약**에
        # 달렸다(아래 잣대 트리가 든다).
        self._params = Config_form([_s for _s in specs_from_callable(Cluster_Params)
                                    if _s.name not in (_THRESHOLDS_FIELD, _NEIGHBORS_FIELD,
                                                       _MEMBERS_FIELD, _WELD_FIELD,
                                                       _NORM_FIELD)])
        _lay.addWidget(self._params)
        _lay.addWidget(self._build_domains())

        _lay.addStretch(1)
        _lay.addWidget(_heading("실행"))
        _lay.addLayout(self._build_actions())
        _lay.addWidget(_heading("이동 (정본 쓰기)"))
        _lay.addLayout(self._build_pending())

        self._status = QLabel("[feature 생성] → [clustering] 순으로 누른다")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color:#666;")
        _lay.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFormat("대기")
        _lay.addWidget(self._progress)

    def _build_source(self) -> QWidget:
        """`Source_Spec` 편집 — 순회 축(unit·obj_index)과 class 필터.

        입력 배선(``inputs``)은 안 낸다 — 기본값이 "파라미터 이름 = 정본 leaf 이름" 이고, 그걸 여기서
        고치려면 GUI 가 추출기의 파라미터 이름을 알아야 한다(계약이 이미 아는 것을 화면이 또 안다).
        """
        _w = QWidget()
        _lay = QVBoxLayout(_w)
        _lay.setContentsMargins(0, 0, 0, 0)

        _row = QHBoxLayout()
        _row.addWidget(QLabel("순회 단위"))
        self._unit = QComboBox()
        for _value, _label in _UNITS:
            self._unit.addItem(_label, _value)
        self._unit.currentIndexChanged.connect(self._sync_unit)
        _row.addWidget(self._unit, stretch=1)
        _lay.addLayout(_row)

        _row = QHBoxLayout()
        self._all_objs = QCheckBox("모든 객체")
        self._all_objs.setToolTip("끄면 아래 번호의 객체 하나만 본다 (0 = 중심 최근접)")
        self._all_objs.toggled.connect(self._sync_unit)
        _row.addWidget(self._all_objs)
        _row.addWidget(QLabel("객체 번호"))
        self._obj = QSpinBox()
        self._obj.setRange(0, 999)
        _row.addWidget(self._obj)
        _row.addStretch()
        _lay.addLayout(_row)

        _row = QHBoxLayout()
        _row.addWidget(QLabel("class 필터"))
        self._classes = QLineEdit()
        self._classes.setPlaceholderText("쉼표 구분 · 비면 전체")
        _row.addWidget(self._classes, stretch=1)
        _lay.addLayout(_row)

        # 중심 거리 — 정본의 ``center_offset``(무차원) 과 **같은 단위**로 받는다. px 로 받으면 화면이
        # 프레임 대각선을 알아야 하는데 그건 이미지를 열어야 나온다.
        _row = QHBoxLayout()
        self._center_on = QCheckBox("중심 거리 제한")
        self._center_on.setToolTip(
            "프레임 가장자리에 치우친 객체를 분석에서 뺀다 (정본은 안 건드린다).\n"
            "끄면 전부 본다. 값이 없는 객체(백필 전)는 거르지 않는다")
        self._center_on.toggled.connect(self._sync_unit)
        _row.addWidget(self._center_on)
        self._center = QDoubleSpinBox()
        self._center.setRange(0.01, 0.50)
        self._center.setSingleStep(0.01)
        self._center.setDecimals(2)
        self._center.setValue(0.30)
        self._center.setToolTip("중심=0.00 · 좌우 가장자리 한복판=0.40 · 모서리=0.50 "
                                "(중심에서의 거리 ÷ 프레임 대각선)")
        _row.addWidget(self._center)
        _row.addWidget(QLabel("이하 (0=중심 · 0.5=모서리)"))
        _row.addStretch()
        _lay.addLayout(_row)

        self._sync_unit()                     # 초기 상태도 규칙을 따른다 (기본값에 기대지 않는다)
        return _w

    def _build_domains(self) -> QWidget:
        """**도메인 → 잣대 트리** — 갈래가 저장 feature 고, 그 아래 줄마다 잣대 하나.

        `k` 는 **잣대에 붙는다** — 가르기가 도는 단위가 잣대라서다. 같은 `radial_rle` 에서 나온
        `signed` 와 `outline` 도 노이즈 바닥이 달라 값을 따로 줘야 한다(실측 도넛÷솔리드 최근접비
        2.45 vs 0.89). 그래서 평평한 목록이 아니라 **한 단 묶은** 트리다: 무엇이 한 측정에서
        나왔는지(= 무엇이 함께 재추출되는지)가 보이면서 눈금은 각자 든다.

        잣대 줄에 붙는 값 넷:

        - **분석에 쓴다** (체크) — 끄면 안 가른다. 비용은 채널 수에 비례해 radial 계열이 지배적이고
          scalar 다섯은 합쳐 23채널이라 사실상 공짜다.
        - **거리 상한 k** — 비우면(``공통``) 위 공통값. 이보다 먼 쌍은 간선을 안 만든다.
        - **이웃 수** — 몇 번째 이웃까지 볼지. 비우면(``0``) 공통값.
        - **보기** — 그리는 좌표계. **계산에 영향이 없다.**

        `k` 와 이웃 수가 **둘 다 잣대에 붙는** 이유가 다르다. `k` 는 축척을 타고(도메인마다 값이
        움직이는 크기가 다르다), 이웃 수는 **밀도**를 탄다(2채널짜리 ``area`` 는 값이 겹치고
        512채널짜리 ``radial_outline`` 은 흩어져, 같은 이웃 수가 같은 뜻이 아니다).
        """
        _w = QWidget()
        _lay = QVBoxLayout(_w)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.addWidget(QLabel("도메인 → 잣대별 설정"))
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(
            ["도메인 / 잣대", "거리 상한", "정규화", "이웃", "최소 표본", "종합 병합", "보기"])
        self._tree.setRootIsDecorated(True)
        self._tree.setSelectionMode(QAbstractItemView.NoSelection)
        self._tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for _c in (1, 2, 3, 4, 5, 6):
            self._tree.header().setSectionResizeMode(_c, QHeaderView.ResizeToContents)
        self._tree.setMinimumHeight(200)
        _lay.addWidget(self._tree)
        self._hint = QLabel("계약 없음 — [feature 생성] 뒤에 목록이 뜬다")
        self._hint.setStyleSheet("color:#666;")
        self._hint.setWordWrap(True)
        _lay.addWidget(self._hint)
        return _w

    def _on_item_changed(self, *_args) -> None:
        """체크 변경 — 요약을 고치고 **결과 쪽에도 알린다**(끈 잣대는 볼 목록에서도 빠진다)."""
        self._sync_hint()
        self.views_changed.emit()

    def _add_gauge(self, parent: QTreeWidgetItem, gauge: str, kind: str, label: str) -> None:
        """도메인 갈래 아래 잣대 한 줄 — 위젯 둘을 :attr:`_domain_state` 가 **잣대 이름**으로 든다.

        키가 잣대 이름인 것이 중요하다 — 아래 계층(`build`·`store`)이 그 이름으로만 도메인을
        만나므로, 묶어 보이는 것은 여기서 끝나고 밖으로 새 개념이 안 나간다.
        """
        _row = QTreeWidgetItem(parent, [label, "", "", "", "", "", ""])
        _row.setFlags(_row.flags() | Qt.ItemIsUserCheckable)
        _row.setCheckState(0, Qt.Checked)
        _row.setToolTip(0, f"{gauge} ({kind})\n"
                           "끄면 이 잣대는 안 가른다 — 다시 켜면 그때 돈다(서명과 무관하다).\n"
                           "**종합 판정에서도 빠진다** — 종합은 켠 축들의 곱집합이다")

        _k = QDoubleSpinBox()
        _k.setRange(_COMMON, 2.0)
        _k.setSingleStep(0.01)
        _k.setDecimals(3)
        _k.setSpecialValueText("공통")
        _k.setToolTip(
            "이보다 먼 쌍은 **간선을 안 만든다** (단위 = 표준편차).\n"
            "구 방식과 달리 type 의 **크기**가 아니라 **이을지 말지**만 정하므로 민감하지 않다 — "
            "실측 0.08 ↔ 0.15 에서 순도 88.0% ↔ 87.8%.\n"
            "바닥은 **노이즈 하한** — 그보다 작게 잡으면 원리상 못 가르는 것을 가르게 되어 부서진다.\n"
            "키우는 방향은 결과 화면의 [해상도] 로 재군집 없이 즉시 본다")
        _k.valueChanged.connect(lambda *_a: self._sync_hint())
        self._tree.setItemWidget(_row, 1, _k)

        # **`k` 의 단위를 정한다** — 셋 다 스칼라 나눗셈이라 군집 결과는 같고 숫자의 뜻만 바뀐다.
        _nm = QComboBox()
        for _val, _txt in _NORM_MODES:
            _nm.addItem(_txt, _val)
        _nm.setToolTip(
            "왼쪽 `거리 상한` 을 **무엇으로 재나**.\n"
            "**σ** — 이 축 값의 표준편차. 지금까지의 기본. 표본 구성이 바뀌면 같은 k 가 다른 뜻이 된다.\n"
            "**원 단위** — px 그대로. 채널이 전부 px 인 축(`radial_*`)에서 물리적 뜻이 그대로 읽힌다.\n"
            "**노이즈 바닥** — 같은 것을 다시 쟀을 때 값이 흔들리는 거리로 나눈다. k 가 '바닥의 몇 배' "
            "가 되어 **축을 건너 같은 뜻**이 된다.\n"
            "**축척만 바뀐다** — 군집 결과는 그대로고 k 의 숫자가 달라진다(바꾸면 그 축만 다시 돈다)")
        _nm.currentIndexChanged.connect(lambda *_a: self._sync_hint())
        self._tree.setItemWidget(_row, 2, _nm)

        _m = QSpinBox()
        _m.setRange(_COMMON_N, 50)
        _m.setSpecialValueText("공통")
        _m.setToolTip(
            "몇 번째 이웃까지 볼지. **서로가 서로의 목록에 있어야** 간선이 생긴다 — 그 상호성이 "
            "사슬을 끊는다(촘촘한 덩어리 옆에 붙은 표본은 자기 쪽에서만 이웃이다).\n"
            "키우면 잘 이어져 배정률이 오르는 대신 다른 class 로 새는 간선도 는다.\n"
            "**잣대마다 다른 값이 필요한 이유는 밀도다** — 채널 수가 다르면 같은 이웃 수가 같은 "
            "뜻이 아니다")
        _m.valueChanged.connect(lambda *_a: self._sync_hint())
        self._tree.setItemWidget(_row, 3, _m)

        _p2 = QSpinBox()
        _p2.setRange(_COMMON_N, 50)
        _p2.setSpecialValueText("공통")
        _p2.setToolTip(
            "이만큼 안 모인 연결 성분은 type 이 아니라 **대기 풀**로 간다.\n"
            "잣대마다 두는 이유는 **서명 때문**이다 — 전역으로 두면 값 하나를 만졌을 때 안 건드린 "
            "게이지까지 전부 다시 돈다.")
        _p2.valueChanged.connect(lambda *_a: self._sync_hint())
        self._tree.setItemWidget(_row, 4, _p2)

        # **종합 전용** — 이 축의 가르기는 안 바뀐다. 축마다 답이 다르므로 여기 둔다.
        _wd = QComboBox()
        for _val, _txt in _WELD_MODES:
            _wd.addItem(_txt, _val)
        _wd.setToolTip(
            "종합에서 이 축의 **이웃한 type 끼리도 붙일지**. 끄면 '같을 때만' 붙어 **이 축이 가른 "
            "것이 지켜진다**.\n"
            "축마다 답이 다르다 — 실루엣은 분할 노이즈로 경계가 흔들려 붙일 값어치가 있지만, 구멍이 "
            "가른 것은 실체가 있어 지켜야 한다(실측 도넛÷솔리드 최근접비 outline 0.89 / signed 2.45).\n"
            "실측: `outline` 만 켰을 때 signed 되붙임 45자리→0 · 순수type 93.2%→93.7%.\n"
            "**이 축의 type 은 안 바뀐다** — 종합만 다시 돈다")
        _wd.currentIndexChanged.connect(lambda *_a: self._sync_hint())
        self._tree.setItemWidget(_row, 5, _wd)

        _v = QComboBox()
        for _val, _txt in _VIEW_MODES:
            _v.addItem(_txt, _val)
        _v.setToolTip(
            "그리는 좌표계. `TOKEN` 은 '순서 있음'만 말하지 극좌표인지 직교인지는 말하지 않는다 — "
            "그건 값의 뜻이라 원래 추출기 계약이 답해야 하는데 아직 선언이 없다.\n"
            "**계산에 영향이 없다** — 보기만 바뀌고 재군집은 안 돈다")
        _v.currentIndexChanged.connect(lambda *_a: self.views_changed.emit())
        self._tree.setItemWidget(_row, 6, _v)

        self._domain_state[gauge] = {"k": _k, "neighbors": _m, "members": _p2, "norm": _nm,
                                     "weld": _wd, "view": _v, "node": _row}

    def _build_actions(self) -> QHBoxLayout:
        _row = QHBoxLayout()
        self._inject_btn = QPushButton("feature 생성")
        self._inject_btn.setToolTip(
            "정본을 훑어 **바뀐 표본만** 특징화해 저장한다 — 가장 비싸다. "
            "정본을 고친 뒤 누르면 그 표본만 덮어쓴다")
        self._inject_btn.clicked.connect(self.inject_requested)
        self._drop_btn = QPushButton("feature 삭제")
        self._drop_btn.setToolTip("이 config 의 산출물(feature·통계)을 폴더째 지운다 — 정본은 안 건드린다")
        self._drop_btn.clicked.connect(self.drop_requested)
        self._cluster_btn = QPushButton("clustering")
        self._cluster_btn.setToolTip(
            "저장된 feature 로 도메인마다 type 을 세운다 — **바뀐 도메인만** 돈다. 특징화는 없다.\n"
            "class 라벨만 고쳤으면 아무것도 다시 돌지 않는다 (class 는 배정에 안 들어간다)")
        self._cluster_btn.clicked.connect(self.cluster_requested)
        for _b in (self._inject_btn, self._drop_btn, self._cluster_btn):
            _row.addWidget(_b)
        return _row

    def _build_pending(self) -> QHBoxLayout:
        """대기(pending) 줄 — 정본을 고치는 유일한 자리라 실행 버튼과 나란히 둔다("무엇이 디스크를
        건드리나"가 한눈에 보이게)."""
        _row = QHBoxLayout()
        self._apply_btn = QPushButton("적용")
        self._apply_btn.setToolTip("모아 둔 class 이동을 정본에 쓴다 — 배정은 안 바뀐다(class 는 값이다)")
        self._apply_btn.clicked.connect(self.apply_requested)
        self._discard_btn = QPushButton("대기 취소")
        self._discard_btn.setToolTip("모아 둔 이동을 버린다 (정본은 안 건드렸다)")
        self._discard_btn.clicked.connect(self.discard_requested)
        for _b in (self._apply_btn, self._discard_btn):
            _b.setEnabled(False)                 # 대기가 있어야 열린다
            _row.addWidget(_b)
        return _row

    def set_pending(self, count: int) -> None:
        """대기 건수를 버튼에 반영 — 0이면 잠근다(누를 것이 없다)."""
        self._pending = int(count)
        self._apply_btn.setText(f"적용 ({count})" if count else "적용")
        self._sync_pending()

    def _sync_pending(self) -> None:
        _on = bool(getattr(self, "_pending", 0)) and not self._busy
        self._apply_btn.setEnabled(_on)
        self._discard_btn.setEnabled(_on)

    def _sync_unit(self, *_args) -> None:
        """frame 단위면 객체 축 위젯이 뜻이 없다 — 끈다(무시되는 값을 만질 수 있으면 거짓말이다)."""
        _obj_axis = self._unit.currentData() == OBJECT
        self._all_objs.setEnabled(_obj_axis)
        self._obj.setEnabled(_obj_axis and not self._all_objs.isChecked())
        self._center_on.setEnabled(_obj_axis)             # 중심 거리는 객체의 성질이다
        self._center.setEnabled(_obj_axis and self._center_on.isChecked())

    # ── 값 ──────────────────────────────────────────────────────────────────────
    def config_path(self) -> str:
        """transform config 경로 (빈 문자열이면 미설정)."""
        return self._cfg.text().strip()

    def set_config_path(self, path: str) -> None:
        """transform config 경로를 얹는다 (신호 없이 — 복원은 사용자의 편집과 구별된다)."""
        self._cfg.setText(str(path or ""))

    def source_spec(self) -> Source_Spec:
        """지금 설정의 순회 축 — 두 국면이 같은 값을 받는다(축이 갈리면 주소가 안 맞는다)."""
        _classes = [_c.strip() for _c in self._classes.text().split(",") if _c.strip()]
        return Source_Spec(
            unit=str(self._unit.currentData()),
            obj_index=None if self._all_objs.isChecked() else int(self._obj.value()),
            classes=_classes or None,
            center_limit=float(self._center.value()) if self._center_on.isChecked() else None)

    def cluster_params(self) -> dict:
        """묶기 파라미터 — `Cluster_Params` 그대로.

        ``thresholds``·``neighbor_counts`` 는 **공통값과 다르게 둔 도메인만** 담는다. 비운 자리를
        0 으로 넣으면 상한 0 · 이웃 0 이 되어 아무것도 안 이어진다 — 없는 것과 0 은 다르다.
        """
        return {**self._params.get(),
                _THRESHOLDS_FIELD: self._threshold_state(),
                _NEIGHBORS_FIELD: self._neighbor_state(),
                _MEMBERS_FIELD: self._member_state(),
                _WELD_FIELD: self._weld_state(),
                _NORM_FIELD: self._norm_state()}

    def _weld_state(self) -> dict[str, bool]:
        """축별 병합 허용 — **공통값과 다르게 둔 축만**. 자리는 :meth:`_threshold_state` 와 같다."""
        return {_d: bool(_s["weld"].currentData()) for _d, _s in self._domain_state.items()
                if _s["weld"].currentData() is not None}

    def _norm_state(self) -> dict[str, str]:
        """축별 정규화 방법 — **기본과 다르게 둔 축만**."""
        return {_d: str(_s["norm"].currentData()) for _d, _s in self._domain_state.items()
                if str(_s["norm"].currentData()) != NORM_EQUALIZE}

    def set_threshold(self, domain: str, value: float) -> int:
        """그 도메인의 거리 상한을 지정한다 (**음수면 해제** — 공통값으로 되돌린다).

        값만 든다 — 다시 가르는 것은 [clustering] 이 한다.

        Returns:
            지금 지정돼 있는 도메인 수.
        """
        _st = self._domain_state.get(str(domain))
        if _st is not None:
            _st["k"].setValue(_COMMON if value < 0 else float(value))
        return len(self._threshold_state())

    def view_modes(self) -> dict[str, str]:
        """``{도메인: auto|silhouette|channels}`` — 그리는 방법. **묶기 파라미터가 아니다**."""
        return {_d: str(_s["view"].currentData()) for _d, _s in self._domain_state.items()}

    def enabled_domains(self) -> list[str]:
        """분석에 쓸 도메인 — 계약이 없으면 빈 목록(고를 게 없는 것이지 안 고른 게 아니다)."""
        return [_d for _d, _s in self._domain_state.items()
                if _s["node"].checkState(0) == Qt.Checked]

    def _threshold_state(self) -> dict[str, float]:
        """``{도메인: k}`` — 공통값 자리(0)는 빼고 낸다."""
        return {_d: float(_s["k"].value()) for _d, _s in self._domain_state.items()
                if float(_s["k"].value()) > _COMMON}

    def _neighbor_state(self) -> dict[str, int]:
        """``{도메인: 이웃 수}`` — 공통값 자리(0)는 빼고 낸다."""
        return {_d: int(_s["neighbors"].value()) for _d, _s in self._domain_state.items()
                if int(_s["neighbors"].value()) > _COMMON_N}

    def _member_state(self) -> dict[str, int]:
        """``{도메인: 승격 최소 표본}`` — 공통값 자리(0)는 빼고 낸다."""
        return {_d: int(_s["members"].value()) for _d, _s in self._domain_state.items()
                if int(_s["members"].value()) > _COMMON_N}

    def recipe(self) -> dict:
        """지금 화면 설정 전부 — 창을 다시 열면 이대로 시작한다(순회 축 + 묶기 파라미터)."""
        _spec = self.source_spec()
        return {"unit": _spec.unit, "obj_index": _spec.obj_index, "classes": _spec.classes,
                "center_limit": _spec.center_limit, **self.cluster_params(),
                _VIEWS_FIELD: self.view_modes(),
                _ENABLED_FIELD: self.enabled_domains()}

    def load_recipe(self, recipe: dict) -> None:
        """저장된 설정을 폼에 되얹는다 (없는 key 는 그대로 둔다).

        **도메인별 k 는 목록이 선 뒤에** 얹는다 — 고를 목록이 계약에서 오므로, 계약을 읽기 전에
        넣으면 갈 자리가 없다(:meth:`set_domains` 가 이 값을 소비한다).
        """
        if not recipe:
            return
        _at = self._unit.findData(str(recipe.get("unit", OBJECT)))
        if _at >= 0:
            self._unit.setCurrentIndex(_at)
        _obj = recipe.get("obj_index", 0)
        self._all_objs.setChecked(_obj is None)
        if _obj is not None:
            self._obj.setValue(int(_obj))
        self._classes.setText(", ".join(str(_c) for _c in (recipe.get("classes") or [])))
        _limit = recipe.get("center_limit")               # None = 끄기 (0.0 과 다르다)
        self._center_on.setChecked(_limit is not None)
        if _limit is not None:
            self._center.setValue(float(_limit))
        self._params.load({_k: _v for _k, _v in recipe.items()
                           if _k in ("threshold", "neighbors", "min_members", "impute_bound",
                                     "weld_types", "max_axis_types")})
        self._wanted = {str(_d): float(_v)
                        for _d, _v in (recipe.get(_THRESHOLDS_FIELD) or {}).items()}
        self._wanted_nb = {str(_d): int(_v)
                           for _d, _v in (recipe.get(_NEIGHBORS_FIELD) or {}).items()}
        self._wanted_mm = {str(_d): int(_v)
                           for _d, _v in (recipe.get(_MEMBERS_FIELD) or {}).items()}
        self._wanted_weld = {str(_d): bool(_v)
                             for _d, _v in (recipe.get(_WELD_FIELD) or {}).items()}
        self._wanted_norm = {str(_d): str(_v)
                             for _d, _v in (recipe.get(_NORM_FIELD) or {}).items()}
        self._wanted_views = {str(_d): str(_v)
                              for _d, _v in (recipe.get(_VIEWS_FIELD) or {}).items()}
        self._wanted_on = ({str(_d) for _d in recipe[_ENABLED_FIELD]}
                           if _ENABLED_FIELD in recipe else None)
        self._apply_wanted()
        self._sync_unit()

    def _apply_wanted(self) -> None:
        """복원값을 트리에 얹는다 — **저장된 이름만**. 나머지는 기본(공통 k · 자동 보기 · 켬)."""
        if not self._domain_state or self._wanted is None:
            return
        _order = [_v for _v, _ in _VIEW_MODES]
        for _d, _st in self._domain_state.items():
            _st["k"].setValue(float(self._wanted.get(_d, _COMMON)))
            _st["neighbors"].setValue(int((self._wanted_nb or {}).get(_d, _COMMON_N)))
            _st["members"].setValue(int((self._wanted_mm or {}).get(_d, _COMMON_N)))
            _nmv = str((self._wanted_norm or {}).get(_d, NORM_EQUALIZE))
            _order_n = [_v for _v, _ in _NORM_MODES]
            _st["norm"].setCurrentIndex(_order_n.index(_nmv) if _nmv in _order_n else 0)
            _w = (self._wanted_weld or {}).get(_d)
            _st["weld"].setCurrentIndex([_v for _v, _ in _WELD_MODES].index(_w) if _w in (True, False)
                                        else 0)
            _m = str((self._wanted_views or {}).get(_d, "auto"))
            _st["view"].setCurrentIndex(_order.index(_m) if _m in _order else 0)
            _st["node"].setCheckState(
                0, Qt.Checked if (self._wanted_on is None or _d in self._wanted_on)
                else Qt.Unchecked)

    def set_domains(self, kinds: dict, gauges: dict | None = None,
                    declared: list[str] | None = None) -> None:
        """계약이 답하는 잣대로 트리를 세운다 — ``{잣대: 성질}`` + ``{잣대: (feature, 접기)}``.

        ``gauges`` 가 **묶는 근거**다. 같은 feature 에서 나온 잣대끼리 한 갈래로 모이므로 무엇이
        함께 재추출되는지가 보인다. 안 주면 잣대마다 제 갈래를 갖는다(묶을 근거가 없으니 추측 안 한다).

        ``declared`` 는 **처음 켤 것**이다 — config `gauges:` 에 적힌 잣대. 안 적은 feature 가
        자동으로 받는 항등 잣대는 꺼진 채로 시작한다. config 에 적었다는 것이 곧 "이걸로 보겠다" 는
        선언이고, 그게 config 의 용도다. 실측으로도 항등 잣대 다섯(scalar)은 순도 17~42% 라 종합
        배정을 7pp 깎기만 했다(73.8% → 66.8%, 순도는 +1.2pp).

        **저장된 선택이 있으면 그것이 이긴다** (:meth:`load_recipe`) — 기본값은 첫 실행에만 쓴다.
        ``declared`` 가 비면(옛 계약이라 표시가 없다) 근거가 없는 것이므로 전부 켠다.

        **값은 잣대 이름으로 보존한다** — 계약을 다시 읽는 일(① 실행 후·config 변경)이 사용자의
        설정을 지우면 안 된다. 목록에서 없어진 잣대의 값은 함께 사라진다(고칠 수 없는 것을 든 채로
        둘 수 없다).
        """
        _first = set(declared or ()) or None
        _keep_k, _keep_v = self._threshold_state(), self.view_modes()
        _keep_n, _keep_m = self._neighbor_state(), self._member_state()
        _keep_nm = {_d: str(_s['norm'].currentData()) for _d, _s in self._domain_state.items()}
        _keep_wd = {_d: _s['weld'].currentData() for _d, _s in self._domain_state.items()}
        _keep_on = set(self.enabled_domains()) if self._domain_state else None
        _g = dict(gauges or {})
        self._tree.blockSignals(True)
        self._tree.clear()
        self._domain_state = {}
        self._group_nodes: dict[str, QTreeWidgetItem] = {}

        _by_group: dict[str, list[str]] = {}
        for _d in sorted(kinds):
            _by_group.setdefault(str(_g.get(_d, (_d, ()))[0]), []).append(_d)

        for _grp, _members in sorted(_by_group.items()):
            _top = QTreeWidgetItem(self._tree, [_grp] + [""] * (self._tree.columnCount() - 1))
            _top.setFlags(_top.flags() & ~Qt.ItemIsUserCheckable)
            _top.setToolTip(0, f"저장 feature '{_grp}' — 여기 달린 잣대는 **함께 재추출**된다. "
                               f"눈금(k)은 잣대마다 따로다")
            _top.setExpanded(True)
            self._group_nodes[_grp] = _top
            for _d in _members:
                _folds = tuple(_g.get(_d, (_d, ()))[1])
                self._add_gauge(_top, _d, str(kinds[_d]),
                                " + ".join(_folds) if _folds else "그대로")
                _st = self._domain_state[_d]
                _st["k"].setValue(float(_keep_k.get(_d, _COMMON)))
                _st["neighbors"].setValue(int(_keep_n.get(_d, _COMMON_N)))
                _st["members"].setValue(int(_keep_m.get(_d, _COMMON_N)))
                if _d in _keep_nm:
                    _st["norm"].setCurrentIndex(
                        [_v for _v, _ in _NORM_MODES].index(_keep_nm[_d]))
                if _d in _keep_wd:
                    _st["weld"].setCurrentIndex(
                        [_v for _v, _ in _WELD_MODES].index(_keep_wd[_d]))
                if _d in _keep_v:
                    _st["view"].setCurrentIndex(
                        [_v for _v, _ in _VIEW_MODES].index(_keep_v[_d]))
                _want = (_d in _keep_on) if _keep_on is not None else \
                        (_first is None or _d in _first)
                _st["node"].setCheckState(0, Qt.Checked if _want else Qt.Unchecked)

        if self._wanted is not None:                 # 복원 대기분이 있으면 지금 얹는다
            self._apply_wanted()
            self._wanted = None
        self._tree.blockSignals(False)
        self._sync_hint()

    def _sync_hint(self) -> None:
        """끈 잣대는 흐리게, 갈래 줄에는 **접어 둬도 보이게** 요약을 단다.

        요약은 **칸이 아니라 툴팁**이다 — 값 칸(`거리 상한`)에 적으면 잣대가 늘어날수록 문자열이
        길어지고 그 칸이 `ResizeToContents` 라 폭이 끝없이 밀린다.
        """
        self._tree.blockSignals(True)
        _summary: dict[str, list[str]] = {}
        for _d, _st in self._domain_state.items():
            _node = _st["node"]
            _on = _node.checkState(0) == Qt.Checked
            _k, _m = float(_st["k"].value()), int(_st["neighbors"].value())
            _mm = int(_st["members"].value())
            _node.setForeground(0, self.palette().text() if _on
                                else self.palette().placeholderText())
            _grp = _node.parent()
            if _grp is not None:
                _summary.setdefault(_grp.text(0), []).append(
                    f"{_node.text(0)}   k {f'{_k:.3f}' if _k > _COMMON else '공통'}"
                    f" · 이웃 {_m if _m > _COMMON_N else '공통'}"
                    f" · 최소 {_mm if _mm > _COMMON_N else '공통'}"
                    if _on else f"{_node.text(0)}   (끔)")
        for _grp, _node in getattr(self, "_group_nodes", {}).items():
            _rows = _summary.get(_grp, [])
            _node.setToolTip(0, "\n".join(["이 feature 의 잣대 설정 — 접어 둬도 여기서 읽는다", *_rows]))
            _node.setText(1, f"잣대 {len(_rows)}" if _rows else "")
        self._tree.blockSignals(False)
        _n = len(self._domain_state)
        if not _n:
            self._hint.setText("계약 없음 — [feature 생성] 뒤에 목록이 뜬다")
            return
        _on = len(self.enabled_domains())
        _own = len(set(self._threshold_state()) | set(self._neighbor_state())
                   | set(self._member_state()))
        self._hint.setText(
            f"도메인 {_n}개 · 분석 {_on}개 · 개별값 {_own}개"
            + ("  — 하나 이상 켜야 [clustering] 이 돈다" if not _on else
               "  · 종합 = 켠 축들의 곱집합"))

    def domain_count(self) -> int:
        """계약이 답한 도메인 개수 — 0 이면 계약이 아직 없다."""
        return len(self._domain_state)

    # ── 표시 ────────────────────────────────────────────────────────────────────
    def set_busy(self, busy: bool) -> None:
        """실행 중엔 버튼을 모두 잠근다 — 산출물이 변형되는 동안 다른 국면이 끼어들지 못하게."""
        self._busy = bool(busy)
        for _b in (self._inject_btn, self._drop_btn, self._cluster_btn):
            _b.setEnabled(not busy)
        self._sync_pending()

    def set_status(self, text: str) -> None:
        """상태 한 줄."""
        self._status.setText(text)

    def set_progress(self, label: str, done: int | None = None, total: int = 1) -> None:
        """진행바 한 자리 — ``done`` 이 None 이면 개수를 모르는 단계(busy 막대)."""
        if done is None:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, max(total, 1))
            self._progress.setValue(done)
        self._progress.setFormat(label)


def _heading(text: str) -> QLabel:
    """섹션 제목 — 설정 덩어리의 경계를 눈에 보이게."""
    _lbl = QLabel(text)
    _lbl.setStyleSheet("font-weight: bold; margin-top: 6px;")
    return _lbl
