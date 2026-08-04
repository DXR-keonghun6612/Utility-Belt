"""우측 결과 — **type 축 하나**. class 는 그 위에서 읽히는 구성 열이다.

**도메인마다 type 집합이 따로** 서고, class 는 배정에 안 들어가므로 그 안에 몇이 들었나로만 나타난다.

화면이 답하는 것은 셋이고 전부 한 표에서 나온다::

    한 type 에 여러 class          이 데이터로 안 갈린다
    한 class 가 여러 type          그 class 안에 다른 모양이 있다
    자기 class 가 소수인 type 의 표본   옮길 후보

**해상도 슬라이더는 재군집이 아니다.** 저장된 중심을 `k'` 로 묶어 보는 것이라 즉시 돈다
(`store.Resolution`). 그래서 "어느 해상도까지 붙어 있나" 를 `k` 를 고쳐 다시 돌리지 않고 훑는다 —
**키우는 방향만** 그렇고, 줄이려면 제어판에서 `k` 를 낮추고 [clustering] 을 다시 눌러야 한다.

**정본을 안 고친다.** 이동은 요청(`move_requested`)으로 올리기만 하고 쓰는 것은 [적용] 이다.

**matplotlib 이 그리는 글자만 영문**이다 — 범례·축 이름. 기본 폰트에 한글 글리프가 없어 글자마다
경고가 쏟아지고, 한글 폰트를 찾아 박아도 환경마다 되고 안 되고가 갈린다. **화면 글자는 한글 그대로**다
(제목줄·목록·버튼은 Qt 가 시스템 폰트로 그리므로 늘 나온다) — 설명은 거기 있고, 그림 안에는 짧은
범례 몇 개뿐이라 잃는 것이 없다.
"""

from __future__ import annotations

import html
from collections import Counter

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as Figure_canvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QMenu,
    QPushButton, QSlider, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTreeWidgetItemIterator, QVBoxLayout, QWidget,
)

from core.analysis import POOL, TOKEN, Cluster_Bucket, Type_explosion, pool_groups
from core.analysis.cluster import JOINT
from core.constant import UNCLASSIFIED_ID

#: 대기(이동 예약) 표시색 — 아직 정본에 안 쓴 것이라 **한눈에 갈려야** 한다.
#: 밝기·채도가 튀는 주황을 쓴다: 트리의 다른 글자는 전부 기본색이라 이것만 도드라진다.
_PENDING_FG = QBrush(QColor("#d97706"))

#: 해상도 슬라이더 눈금 수 — `k` 에서 :data:`_SPAN` 배까지.
_STEPS = 40
_SPAN = 5.0

#: 종합 자리의 표시 이름 — 콤보에서 축들과 나란히 서므로 축이 아님이 드러나야 한다.
_JOINT_LABEL = "종합 (곱집합)"

#: 한 그림에 겹칠 type 수 상한 — 넘으면 색이 돌아 어느 선이 무엇인지 못 읽는다.
_TYPE_CAP = 6

#: type 평균을 낼 때 실제로 읽는 표본 상한 — 멤버가 수천이면 전부 읽을 이유가 없다.
#: 평균은 표본 수의 √에 반비례해 안정되므로 200 이면 이미 눈으로 안 흔들린다.
_MEAN_CAP = 200

#: 배치 방법 — 판정이 아니라 **그림**이라 여기서 고른다(간선은 어느 쪽이든 원 거리로 긋는다).
_LAYOUTS = (("mds", "MDS (거리 보존)"), ("umap", "UMAP (구조 강조)"))

#: 그래프에 그릴 type 수 상한 — 거리 행렬이 자리 수의 제곱이고, 점이 수천이면 읽히지도 않는다.
_GRAPH_MAX = 3000
#: 그래프에 그릴 간선 수 상한 — 해상도를 키우면 쌍이 제곱으로 는다.
_EDGE_MAX = 4000

#: 지연 표본 줄의 자리 표시 — 이게 달린 자식은 "아직 안 만들었다" 는 뜻이다.
_LAZY = ("lazy",)

#: 그래프 점에 붙일 라벨 — **그림에만** 영향이 있다.
_GRAPH_LABELS = (("none", "없음"), ("selected", "고른 것만"), ("all", "전부"))

#: 그래프 확대 단계 — 가운데를 기준으로 잘라 본다(배치를 다시 계산하지 않는다).
_GRAPH_ZOOM = ((1.0, "1×"), (2.0, "2×"), (4.0, "4×"), (8.0, "8×"), (16.0, "16×"))

#: **단독** 갈래의 자리 번호 — 종합에서 표본 하나뿐인 type 들을 한 줄로 모은다.
#:
#: type 이 아니라 **보기 묶음**이다. 그것들도 어엿한 종합 type 이지만(축마다 문턱을 넘고 왔다), 큰
#: 덩어리 수백 개 사이에 한 줄씩 흩어져 있으면 목록에서 안 읽힌다 — 그리고 이 도구가 찾는 것이
#: 바로 저것들이라 오히려 모아 둬야 한다. :data:`~core.analysis.POOL` 과 안 겹치는 음수를 쓴다.
_SOLO = -2

#: 보류 하위 무리의 자리 번호 시작점 — ``#i`` 는 ``_POOL_BASE - i`` 다.
#:
#: 이것들도 type 이 아니라 **보기 묶음**이고(:data:`_SOLO` 와 같은 성질), 배정이 아니라서 type 번호를
#: 받을 수 없다. :data:`~core.analysis.POOL`·:data:`_SOLO` 와 안 겹치게 멀리 띄운 음수를 쓴다.
_POOL_BASE = -100


def _band_reader(ndim: int):
    """밴드 읽기 함수에 **기대 ndim** 을 달아 둔다 — 값 shape 이 안 맞으면 안 그린다."""
    def _wrap(fn):
        fn.ndim = ndim
        return fn
    return _wrap


@_band_reader(2)
def _bands_from_rle(a: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """원본 RLE ``(NT, K)`` — 간격의 누적이 곧 경계. **홀수 간격이 살, 짝수가 구멍**이다."""
    _cum = np.cumsum(a, axis=1)
    return [(np.where(a[:, _k] > 0, _cum[:, _k - 1], np.nan),
             np.where(a[:, _k] > 0, _cum[:, _k], np.nan))
            for _k in range(1, a.shape[1], 2)]


@_band_reader(1)
def _bands_from_outline(a: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """``[outline]`` ``(NT,)`` — 그 자체가 바깥 반경이라 ``(0, outline)`` 한 겹.

    구멍을 안 보므로 꽉 찬 원반으로 그려지는데, 그것이 **이 잣대가 보는 형상**이다.
    """
    return [(np.where(a > 0, 0.0, np.nan), np.where(a > 0, a, np.nan))]


@_band_reader(2)
def _bands_from_signed_outline(a: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """``[signed, outline]`` ``(NT, 2)`` — ``살합 = (signed + outline)/2`` 이므로 안쪽은 그 차의 반.

    ``signed = 2·살합 − 외곽r`` 이라 밴드가 하나면 **정확한 복원**이고(도넛 안쪽 a · 바깥 b →
    그대로 a·b), 여럿이면 한 겹으로 환산한 살이다.
    """
    _signed, _outer = a[:, 0], a[:, 1]
    _has = _outer > 0
    return [(np.where(_has, (_outer - _signed) / 2.0, np.nan), np.where(_has, _outer, np.nan))]


#: **접기 조합 → 반지름으로 읽는 법.** 잣대 목록이 config 라 조합도 config 가 정하는데, 그 값을
#: *극좌표 형상으로* 읽는 규칙만은 데이터로 못 낸다 — 여기가 그 유일한 자리다.
#:
#: 새 접기를 `RADIAL_FOLDS` 와 config 에 더하면 가르기·저장·되읽기는 다 따라오고 **그림만 안 온다**
#: (여기 없는 조합은 채널 그림으로 떨어진다 — 조용히 틀리게 그리지는 않는다). 형상으로 보고 싶으면
#: 여기 한 줄을 더한다.
BAND_READERS = {
    ():                     _bands_from_rle,
    ("outline",):           _bands_from_outline,
    ("signed", "outline"):  _bands_from_signed_outline,
}


class Result_view(QWidget):
    """도메인 하나의 type 목록 + 그 type 의 class 구성 + 표본 + 형상.

    Attributes:
        move_requested: ``(주소들, class_id)`` — class_id 가 비면 호출 측이 picker 를 연다.
        unlabel_requested: ``(주소들)`` — 미분류로 내린다.
        unify_requested: ``[(주소들, class_id)…]`` — type 마다 **최다 class 로** 통일. 목적지가 type 마다
            달라 ``move_requested`` 로는 못 싣고, 여러 번 나눠 보내면 한 동작이 여러 건으로 흩어진다.
        threshold_requested: ``(도메인, k)`` — 음수면 공통값으로 되돌린다.
        propagate_requested: 종합이 메운 자리를 **축에 반영**한다 (사람이 눌러야 돈다).
        focus_requested: 표본 줄 **더블클릭** ``(stem, obj)`` — 메인 본문을 그 표본으로 옮긴다.
            여기선 정본을 모르므로 주소만 올린다.
    """

    move_requested = Signal(list, str)
    unlabel_requested = Signal(list)
    unify_requested = Signal(list)
    threshold_requested = Signal(str, float)
    propagate_requested = Signal()
    focus_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bucket: Cluster_Bucket | None = None
        self._names: dict[str, str] = {}
        self._pending: dict = {}
        self._groups: dict[int, list[int]] = {}     # 해상도 그룹 → 그 안의 type 들
        self._pool_groups: dict[int, list[str]] = {}  # 보류 하위 무리 → 그 key 들 (type 이 아니라 명단)
        self._pool_key: tuple = ()                  # 하위 무리 캐시 키 (도메인·type 수·보류 수)
        self._pool_cache: list[list[str]] = []
        self._views: dict[str, str] = {}            # 도메인별 보기 — 제어판이 준다
        self._enabled: list[str] | None = None      # 볼 도메인 — 제어판의 체크가 정한다
        self._checked: set = set()                  # 체크한 표본 = **옮길 대상**
        self._build()

    # ── 주입 ────────────────────────────────────────────────────────────────────
    def set_class_names(self, names: dict) -> None:
        """``{class_id: 표시 이름}`` — 번호만으로는 사람이 못 읽는다."""
        self._names = {str(_k): str(_v) for _k, _v in (names or {}).items()}
        self._fill_types()

    def set_bucket(self, bucket: Cluster_Bucket | None) -> None:
        """산출물 store 를 걸고 화면을 다시 세운다 (None 이면 비운다)."""
        self._bucket = bucket
        self._checked.clear()
        self._fill_domains()

    def set_domains(self, domains: list | None) -> None:
        """콤보에 올릴 도메인 — **제어판에서 체크한 것만**. ``None`` 이면 계약 전부.

        끈 도메인은 가르지도 않으므로 type 이 없다. 목록에 남겨 두면 고를 수는 있는데 늘 비어 있어
        "값이 없다" 와 "안 돌렸다" 가 구분되지 않는다.
        """
        self._enabled = None if domains is None else [str(_d) for _d in domains]
        self._fill_domains()

    def set_views(self, views: dict) -> None:
        """``{도메인: auto|silhouette|channels}`` — 그리는 방법. 제어판이 소유하고 여기는 받는다.

        계약(`Feature_Spec.axis`)이 답하기 시작하면 이 값은 **override** 로 남는다(`auto` 가 계약을 따른다).
        """
        self._views = {str(_k): str(_v) for _k, _v in (views or {}).items()}
        self._redraw()

    # ── 대기 표기 — 아직 정본에 안 쓴 것이라 **한눈에 갈려야** 한다 ─────────────────
    def _mark_pending(self, item: QTreeWidgetItem, target) -> None:
        """표본 줄에 대기를 표시한다 — ``→ 대상`` + 색. ``target`` 이 None 이면 지운다.

        화살표를 붙이는 건 **방향이 보여야** 하기 때문이다. 옆 칸에 지금 class 가, 이 칸에 갈 class 가
        있는데 화살표가 없으면 둘 중 어느 쪽이 결과인지가 안 읽힌다("대기" 라는 머리글만으로는 부족했다).
        """
        item.setText(3, f"→ {self._display(target)}" if target is not None else "")
        for _c in range(4):
            item.setForeground(_c, _PENDING_FG if target is not None else QBrush())
        _f = item.font(0)
        _f.setBold(target is not None)
        for _c in range(4):
            item.setFont(_c, _f)

    def _pending_counts(self) -> tuple[Counter, Counter]:
        """``(갈래별 대기 수, (갈래, class)별 대기 수)`` — 접힌 줄에도 대기를 보이려면 필요하다.

        **``_pending`` 만 훑는다**(보통 수십~수백 건) — 트리를 뒤지면 안 펼친 자리는 셀 수가 없고,
        전 표본을 훑으면 6만 건을 매번 돈다. 표본 하나의 자리는 index 한 줄이 답한다.
        """
        _b, _d = self._bucket, self._domain_of()
        if _b is None or not _d or not self._pending:
            return Counter(), Counter()
        _index = _b.Index()
        _assign = _b.Joint().get("assign", {}) if _d == JOINT else None
        _seat = {_t: _g for _g, _ts in self._groups.items() for _t in _ts}
        _pool_of = {_k: _g for _g, _ks in self._pool_groups.items() for _k in _ks}
        _by_group: Counter = Counter()
        _by_class: Counter = Counter()
        for _addr in self._pending:
            _key = Cluster_Bucket.Key(_addr)
            _rec = _index.get(_key)
            if _rec is None:
                continue
            _t = int(_assign.get(_key, POOL) if _assign is not None
                     else (_rec.get("types") or {}).get(_d, POOL))
            _g = _pool_of.get(_key, POOL if _t == POOL else _seat.get(_t))
            if _g is None:                      # 걸러진 자리(고른 class 밖) — 트리에 줄이 없다
                continue
            _by_group[_g] += 1
            _by_class[(_g, str(_rec.get("class", "")))] += 1
        return _by_group, _by_class

    def _sync_pending_marks(self) -> None:
        """트리 전체의 대기 표기를 지금 값에 맞춘다 — 표본 줄은 화살표, 상위 줄은 건수."""
        _by_group, _by_class = self._pending_counts()
        self._tree.blockSignals(True)
        _it = QTreeWidgetItemIterator(self._tree)
        while _it.value():
            _n = _it.value()
            _role = _n.data(0, Qt.UserRole) or ()
            if len(_role) == 2 and _role[0] == "sample":
                self._mark_pending(_n, self._pending.get(Cluster_Bucket.Address(str(_role[1]))))
            elif len(_role) == 2 and _role[0] == "group":
                _c = _by_group.get(int(_role[1]), 0)
                _n.setText(3, f"대기 {_c:,}" if _c else "")
                _n.setForeground(3, _PENDING_FG if _c else QBrush())
            elif len(_role) == 3 and _role[0] == "class":
                _c = _by_class.get((int(_role[1]), str(_role[2])), 0)
                _n.setText(3, f"대기 {_c:,}" if _c else "")
                _n.setForeground(3, _PENDING_FG if _c else QBrush())
            _it += 1
        self._tree.blockSignals(False)

    def set_pending(self, pending: dict) -> None:
        """대기 중인 이동 ``{(stem, obj): class_id}`` — **이미 그려진 줄의 표기만** 고친다.

        예전엔 트리를 통째로 다시 세웠다(``_fill_types``). 대기가 걸리는 곳은 표본 줄의 마지막 칸 하나뿐인데
        (그 말고 대기에 기대는 표시가 없다) 전체를 다시 그리면 **펼친 자리·선택·스크롤이 함께 날아가** 한 건
        지정할 때마다 보던 자리를 다시 찾아가야 했다 — 여러 건을 훑어보며 지정하는 게 이 화면의 주 동선이라
        거기서 흐름이 끊긴다.

        아직 안 펼친 표본 줄은 손댈 것이 없다 — 펼치는 순간 :meth:`_on_expand` 가 **지금** 값으로 그리고,
        그때까지는 부모(type·class) 줄의 건수가 "이 안에 대기가 있다"를 대신 말한다.
        """
        self._pending = dict(pending or {})
        self._sync_pending_marks()
        self._note()

    def _display(self, class_id) -> str:
        _cid = str(class_id)
        return f"{self._names.get(_cid, _cid)} ({_cid})" if _cid in self._names else _cid

    # ── 구성 ────────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(4, 4, 4, 4)
        _lay.addLayout(self._build_head())

        # **배치 그래프가 위에서 폭을 다 쓴다.** type 이 수백~수천이라 좁은 칸에서는 점이 뭉쳐
        # 아무것도 안 읽힌다 — 이 그림이 답하는 것("어느 덩어리가 어디에 붙나")은 넓어야 보인다.
        _v = QSplitter(Qt.Orientation.Vertical)
        _v.addWidget(self._build_graph())
        _bot = QSplitter(Qt.Orientation.Horizontal)
        _bot.addWidget(self._build_tree())
        _bot.addWidget(self._build_shape())
        _bot.setSizes([620, 460])
        _v.addWidget(_bot)
        _v.setSizes([420, 380])
        _lay.addWidget(_v, stretch=1)

    def _build_head(self) -> QHBoxLayout:
        _row = QHBoxLayout()
        _row.addWidget(QLabel("도메인"))
        self._domain = QComboBox()
        self._domain.setMinimumWidth(140)
        self._domain.currentIndexChanged.connect(lambda *_a: self._fill_types())
        _row.addWidget(self._domain)

        # 종합에는 좌표가 없어 형상을 그릴 잣대를 **사람이 고른다**. 자동으로 첫 축을 집으면
        # (이름순이라 `area` 가 온다) 왜 그 축인지가 화면에서 안 읽힌다.
        self._shape_axis_label = QLabel("  형상 축")
        _row.addWidget(self._shape_axis_label)
        self._shape_axis = QComboBox()
        self._shape_axis.setMinimumWidth(130)
        self._shape_axis.setToolTip(
            "**종합을 볼 때** 형상을 어느 잣대로 그릴지. 종합은 축 label 의 조합이라 자기 좌표가 "
            "없다 — 멤버는 정해져 있으니 평균 형상은 그릴 수 있고, 그리려면 어느 잣대의 원본 "
            "feature 인지가 있어야 한다.\n"
            "**판정과 무관하다** — 보기만 바뀐다")
        self._shape_axis.currentIndexChanged.connect(lambda *_a: self._redraw())
        _row.addWidget(self._shape_axis)

        # 메운 값은 **종합 전용**이라 축 화면은 계속 "모른다"고 말한다. 그 추정을 보고 맞다고
        # 판단했을 때만 축에 앉힌다 — 자동으로 하면 측정과 추정이 소리 없이 섞인다.
        self._propagate_btn = QPushButton("메움 전파")
        self._propagate_btn.setToolTip(
            "종합이 **다른 축을 참고해 메운** 자리를 그 축의 배정에 반영한다.\n"
            "지금은 종합에서만 쓰이고 축 화면은 '모른다' 로 남아 있다 — 추정이기 때문이다.\n"
            "누르면 축의 type 에 앉고, 그 축의 중심·퍼짐·구성표가 그 표본을 포함하게 된다.\n"
            "**재군집은 안 한다** — type 경계는 그대로고 붙이기만 한다. 되돌리려면 [clustering] 을 "
            "다시 돌린다")
        self._propagate_btn.clicked.connect(self.propagate_requested)
        _row.addWidget(self._propagate_btn)

        _row.addWidget(QLabel("  해상도 k′"))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, _STEPS)
        self._slider.setValue(0)
        self._slider.setToolTip(
            "저장된 중심을 이 반경으로 **묶어 본다** — 재군집이 아니라 조회라 즉시 돈다.\n"
            "왼쪽 끝이 가른 `k` 그대로다. 더 잘게 보려면 제어판에서 k 를 낮추고 [clustering].")
        self._slider.valueChanged.connect(lambda *_a: self._fill_types())
        _row.addWidget(self._slider, stretch=1)
        self._res_label = QLabel("—")
        self._res_label.setMinimumWidth(220)
        _row.addWidget(self._res_label)
        return _row

    def _build_tree(self) -> QWidget:
        """``type → class → 표본`` **한 트리** — 셋이 늘 같이 움직이므로 나눌 이유가 없다.

        한때 type→class 트리와 표본 표를 따로 뒀다. 고르는 것과 보이는 것이 늘 붙어 다녔고(트리에서
        고르면 표가 갈리고, 표에서 고르면 형상이 갈린다) 화면만 둘로 쪼개져 있었다. 합치면 ``#12 >
        c153 > 그 표본`` 이 **한 줄기**로 읽힌다.

        합치는 데 걸리던 것은 **초기 비용** 하나였다 — type 하나에 표본 수천이면 미리 만들 수 없다.
        그래서 표본 줄은 **class 를 펼칠 때** 만든다(:meth:`_on_expand`). 접혀 있는 동안은 자리
        표시만 있고, 비용이 표본 수가 아니라 **펼친 만큼**이다.

        칸이 층마다 다른 것을 든다 — 층이 다르면 물어볼 것도 다르기 때문이다::

            type    이름                 표본 수    (class 종수)
            class   class 이름           표본 수    비율
            표본    stem · obj           거리       class          대기
        """
        _w = QWidget()
        _lay = QVBoxLayout(_w)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.addWidget(QLabel("type → class → 표본"))
        # **class 로 거르기** — "이 class 가 어디에 흩어져 있나" 가 이 화면의 물음 중 하나인데,
        # type 이 수백이면 눈으로 못 찾는다. 거르면 그 class 를 든 type 만 남고 **많이 든 순**으로 선다.
        _row = QHBoxLayout()
        _row.addWidget(QLabel("class 필터"))
        # **고르면 더해지는 콤보**다 — 체크 목록이 아니라. 담긴 것은 아래 줄이 ✕ 와 함께 들고,
        # 콤보는 "다음에 무엇을 더할까" 만 답한다. 한 위젯이 두 일(고르기·보여주기)을 겸하지 않는다.
        self._class_filter = QComboBox()
        self._class_filter.setMinimumWidth(200)
        self._class_filter.setToolTip(
            "고른 class 를 **하나라도 가진 type 만** 남긴다 — 그 class 들이 몇 갈래로 흩어졌는지가 "
            "바로 보인다. 여럿 더하면 **함께 어디에 있나** 를 묻는 것이 된다(둘이 늘 같은 type 에 "
            "있으면 이 잣대로 안 갈리는 쌍이다).\n"
            "고르면 아래 줄에 담기고, 거기 ✕ 로 하나씩 뺀다.\n"
            "**거르기일 뿐 판정이 아니다** — 배정도 그림도 안 바뀐다")
        # ``activated`` 는 **사람이 고를 때만** 온다 — 아래에서 자리를 0 으로 되돌리는 것이
        # 다시 이 핸들러를 부르지 않는다(``currentIndexChanged`` 를 쓰면 그 되돌림이 재진입한다).
        self._class_filter.activated.connect(self._on_filter_add)
        _row.addWidget(self._class_filter)
        self._clear_filter = QPushButton("해제")
        self._clear_filter.setToolTip("고른 class 를 전부 끈다 (전체 보기로)")
        self._clear_filter.setFixedWidth(48)
        self._clear_filter.clicked.connect(self._on_clear_filter)
        _row.addWidget(self._clear_filter)
        _row.addStretch(1)
        _lay.addLayout(_row)
        # 고른 것을 **펼쳐서** 한 줄 더 쓴다 — 콤보 칸은 좁아 셋을 넘으면 개수로 접히는데, 무엇을
        # 보고 있는지는 늘 보여야 판단이 흔들리지 않는다. 항목마다 ✕ 를 링크로 달아 **여기서 바로**
        # 뺀다(콤보를 다시 열어 목록에서 찾는 것보다 짧다).
        self._filter_note = QLabel("")
        self._filter_note.setWordWrap(True)
        self._filter_note.setTextFormat(Qt.TextFormat.RichText)
        self._filter_note.setOpenExternalLinks(False)
        self._filter_note.linkActivated.connect(self._on_filter_link)
        _lay.addWidget(self._filter_note)
        self._filter: set[str] = set()          # 거르는 class — **화면이 든다**(위젯이 아니라)
        _lay.addWidget(QLabel("class 를 펼치면 표본이 뜬다 · 체크 = 옮길 대상 · 선택 = 형상에 그린다"))
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["type / class / 표본", "수 · 거리", "비율 · class", "대기"])
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setRootIsDecorated(True)
        self._tree.setUniformRowHeights(True)          # 수만 줄에서 높이 계산이 O(n) 이 되지 않게
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for _c in (1, 2, 3):
            self._tree.header().setSectionResizeMode(_c, QHeaderView.ResizeToContents)
        self._tree.itemSelectionChanged.connect(self._on_type)
        self._tree.itemExpanded.connect(self._on_expand)
        self._tree.itemChanged.connect(self._on_check)
        self._tree.itemDoubleClicked.connect(self._on_activate)   # 표본 → 메인 본문으로 이동
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_type_menu)
        _lay.addWidget(self._tree, stretch=1)
        self._comp_note = QLabel("")
        self._comp_note.setWordWrap(True)
        self._comp_note.setStyleSheet("color:#666;")
        _lay.addWidget(self._comp_note)
        self._sample_note = QLabel("")
        self._sample_note.setStyleSheet("color:#666;")
        self._sample_note.setWordWrap(True)            # 대기 내역이 두 줄로 붙는다
        _lay.addWidget(self._sample_note)
        return _w

    def _build_graph(self) -> QWidget:
        """type 끼리의 **가까움 그래프** — 슬라이더가 무엇을 붙이는지 눈으로 본다.

        트리는 "지금 몇 갈래인가" 만 답한다. 중심끼리의 거리를 펴 놓고 ``k'`` 안의 쌍을 이으면,
        해상도를 올릴 때 **어느 덩어리가 어디에 붙는지**가 보인다.

        보기 옵션은 여기 모은다(배치·라벨·확대) — 전부 **그림에만** 영향이 있고 판정과 무관하다.
        """
        _w = QWidget()
        _lay = QVBoxLayout(_w)
        _lay.setContentsMargins(0, 0, 0, 0)
        _row = QHBoxLayout()
        _row.addWidget(QLabel("배치"))
        self._layout_mode = QComboBox()
        for _v, _t in _LAYOUTS:
            self._layout_mode.addItem(_t, _v)
        self._layout_mode.setToolTip(
            "**MDS** — 거리를 보존한다(중심들의 PCA와 같다). 선이 짧으면 실제로 가깝다.\n"
            "**UMAP** — 구조를 강조해 벌려 놓는다. 보기는 좋지만 **거리·간격에 뜻이 없다** — "
            "덩어리 크기도 사이 간격도 읽으면 안 된다.\n"
            "어느 쪽이든 **간선은 원 거리로 긋는다** — 배치가 뭉갠 자리에서도 선은 사실이다.")
        self._layout_mode.currentIndexChanged.connect(lambda *_a: self._redraw_graph())
        _row.addWidget(self._layout_mode)

        _row.addWidget(QLabel("  라벨"))
        self._label_mode = QComboBox()
        for _v, _txt in _GRAPH_LABELS:
            self._label_mode.addItem(_txt, _v)
        self._label_mode.setToolTip(
            "점 옆에 무엇을 적을지. **고른 것만** 은 트리에서 고른 type 에만 번호를 붙인다 — "
            "수백 개에 전부 적으면 글자가 겹쳐 그림이 안 보인다.\n"
            "번호는 트리의 ``#번호`` 와 같은 값이라 둘을 눈으로 잇는 자리다.")
        self._label_mode.currentIndexChanged.connect(lambda *_a: self._redraw_graph())
        _row.addWidget(self._label_mode)

        self._graph_zoom = QComboBox()
        for _v, _txt in _GRAPH_ZOOM:
            self._graph_zoom.addItem(_txt, _v)
        self._graph_zoom.setToolTip("가운데를 기준으로 잘라 본다 — **점 위치는 안 바뀐다**(배치를 "
                                    "다시 계산하지 않는다). 캔버스에서 휠로도 된다")
        self._graph_zoom.currentIndexChanged.connect(lambda *_a: self._redraw_graph())
        _row.addWidget(QLabel("  확대"))
        _row.addWidget(self._graph_zoom)
        _row.addStretch(1)
        _lay.addLayout(_row)

        self._graph_title = QLabel("type 근접 — 점=type(크기∝표본) · 선=k′ 안 · 색=섞임 정도")
        self._graph_title.setWordWrap(True)
        _lay.addWidget(self._graph_title)
        self._gfig = Figure(figsize=(7.2, 3.6))
        self._gcanvas = Figure_canvas(self._gfig)
        self._gcanvas.mpl_connect("scroll_event", self._on_graph_scroll)
        _lay.addWidget(self._gcanvas, stretch=1)
        return _w

    def _on_graph_scroll(self, event) -> None:
        """휠 = 확대 단계 이동 — 콤보와 **같은 값**을 움직인다(두 손잡이가 어긋나지 않게)."""
        _i = self._graph_zoom.currentIndex()
        _n = self._graph_zoom.count()
        _at = _i + (1 if getattr(event, "button", None) == "up" or event.step > 0 else -1)
        if 0 <= _at < _n:
            self._graph_zoom.setCurrentIndex(_at)

    def _build_shape(self) -> QWidget:
        _w = QWidget()
        _lay = QVBoxLayout(_w)
        _lay.setContentsMargins(0, 0, 0, 0)
        # 산포는 **평균만으로는 못 읽는 것**을 답한다 — 같은 평균이라도 멤버가 딸싹 붙어 있는 것과
        # 넓게 퍼진 것은 다른 것이다. 끌 수 있게 둔 이유는 type 을 여럿 겹칠 때 띠끼리 겹쳐서다.
        self._spread = QCheckBox("산포 (±1σ)")
        self._spread.setChecked(True)
        self._spread.setToolTip(
            "type 평균 둘레에 **채널별 표준편차**를 옅은 띠로 얹는다.\n"
            "띠가 얇으면 그 type 은 한 덩어리고, 두꺼우면 평균이 멤버를 대표하지 못한다 — "
            "묶인 것들이 실제로 얼마나 닮았는지가 여기서 읽힌다.\n"
            "**계산에 영향이 없다** · 표본이 하나면 퍼짐이 정의되지 않아 안 그린다")
        self._spread.toggled.connect(lambda *_a: self._redraw())
        _lay.addWidget(self._spread)
        self._shape_title = QLabel("—")
        self._shape_title.setWordWrap(True)
        _lay.addWidget(self._shape_title)
        self._fig = Figure(figsize=(3.4, 3.4))
        self._canvas = Figure_canvas(self._fig)
        _lay.addWidget(self._canvas, stretch=1)
        return _w

    # ── 채우기 ──────────────────────────────────────────────────────────────────
    def _fill_domains(self) -> None:
        """콤보를 다시 세운다 — **고른 도메인은 이름으로 보존한다**(목록이 흔들려도 자리가 안 튄다)."""
        _was = self._domain_of()
        self._domain.blockSignals(True)
        self._domain.clear()
        if self._bucket is not None:
            for _d in self._bucket.View_domains(self._enabled):
                self._domain.addItem(_JOINT_LABEL if _d == JOINT else _d, _d)
        _at = self._domain.findData(_was)
        if _at >= 0:
            self._domain.setCurrentIndex(_at)
        self._domain.blockSignals(False)
        self._fill_types()

    def _domain_of(self) -> str:
        return str(self._domain.currentData() or "")

    def _base_k(self) -> float:
        """가른 거리 상한 — 슬라이더의 왼쪽 끝이다. 종합은 자기 상한이 없어 0."""
        _d = self._domain_of()
        if _d == JOINT or not (self._bucket and _d):
            return 0.0
        return self._bucket.Threshold_of(_d)[0]

    def _draw_domain(self, domain: str) -> str:
        """형상을 그릴 때 실제로 쓸 도메인 — 종합이면 **[형상 축] 이 고른 것**.

        종합 type 의 멤버는 정해져 있으니 평균 형상은 그릴 수 있는데, 그리려면 어느 잣대의 원본
        feature 인지가 있어야 한다. 그걸 화면이 몰래 정하지 않는다 — 축마다 그림의 뜻이 다르고
        (`radial_outline` 은 실루엣, `area` 는 순서 없는 채널) 어느 것을 보고 있는지가 판단에
        들어가기 때문이다.
        """
        if domain != JOINT:
            return domain
        return str(self._shape_axis.currentData() or domain)

    def _fill_shape_axis(self) -> None:
        """[형상 축] 목록을 종합의 축들로 채운다 — **종합일 때만 열린다**.

        고른 축은 이름으로 보존한다(목록이 다시 서도 자리가 안 튄다).
        """
        _b = self._bucket
        _joint = self._domain_of() == JOINT
        _was = str(self._shape_axis.currentData() or "")
        self._shape_axis.blockSignals(True)
        self._shape_axis.clear()
        _axes = _b.Joint_coords()[0] if _b is not None else []
        for _a in _axes:
            self._shape_axis.addItem(_a, _a)
        _at = self._shape_axis.findData(_was)
        if _at >= 0:
            self._shape_axis.setCurrentIndex(_at)
        self._shape_axis.blockSignals(False)
        for _w in (self._shape_axis, self._shape_axis_label):
            _w.setVisible(_joint and bool(_axes))
        _n = len(_b.Joint().get("imputed") or {}) if _b is not None else 0
        self._propagate_btn.setVisible(_joint)
        self._propagate_btn.setEnabled(bool(_n))
        self._propagate_btn.setText(f"메움 전파 ({_n:,})" if _n else "메움 전파")

    def _res_k(self) -> float:
        """슬라이더가 가리키는 조회 반경 ``k' ≥ k``."""
        _k = self._base_k()
        return _k * (1.0 + (_SPAN - 1.0) * self._slider.value() / max(_STEPS, 1))

    def _fill_types(self) -> None:
        """해상도 그룹을 트리로 — 표본 많은 순, 자식은 class 구성, 마지막에 미배정."""
        self._tree.clear()
        self._groups = {}
        self._pool_groups = {}          # 명단은 트리와 함께 산다 (캐시 `_pool_cache` 는 남긴다)
        self._comp_note.setText("")
        _b, _d = self._bucket, self._domain_of()
        if _b is None or not _d:
            self._res_label.setText("—")
            self._note()
            self._redraw()
            return

        _joint = _d == JOINT
        self._slider.setEnabled(not _joint)
        self._fill_shape_axis()
        _k, _kp = self._base_k(), self._res_k()
        try:
            _grp = _b.Resolution(_d, _kp)
        except Type_explosion as _e:
            self._res_label.setText("type 과다")
            self._comp_note.setText(str(_e))
            self._note()
            self._redraw()
            return

        for _t, _g in enumerate(_grp.tolist()):
            self._groups.setdefault(int(_g), []).append(_t)
        _comp = _b.Composition(_d)
        _only = self._sync_class_filter(_comp)
        _rows = [(_g, Counter({_c: _n for _t in _ts
                               for _c, _n in _comp.get(_t, Counter()).items()}), _ts)
                 for _g, _ts in self._groups.items()]
        _rows = [(_g, _acc, _ts) for _g, _acc, _ts in _rows if _acc]
        if _only:              # 고른 것을 **하나라도** 든 것만 · 그 합이 많은 순
            _rows = [_r for _r in _rows if any(_r[1].get(_c) for _c in _only)]
            _rows.sort(key=lambda _r: -sum(_r[1].get(_c, 0) for _c in _only))
        else:
            _rows.sort(key=lambda _r: -sum(_r[1].values()))
        _pool = _comp.get(POOL, Counter())
        if _only and _pool:
            _pool = Counter({_c: _pool[_c] for _c in _only if _pool.get(_c)})

        # 종합의 **단독**(표본 1건)은 한 줄로 모은다 — 큰 덩어리 사이에 흩어지면 안 읽힌다.
        _solo = [(_g, _acc, _ts) for _g, _acc, _ts in _rows
                 if _joint and sum(_acc.values()) == 1] if _joint else []
        if _solo:
            _rows = [_r for _r in _rows if sum(_r[1].values()) > 1]
        for _g, _acc, _ts in _rows:
            self._add_group(self._group_label(_d, _g, _ts), _g, _acc, _only)
        if _solo:
            self._groups[_SOLO] = [_t for _, _, _ts in _solo for _t in _ts]
            _acc: Counter = Counter()
            for _, _a, _ in _solo:
                _acc.update(_a)
            self._add_group(f"단독 — 이 조합을 가진 표본이 하나뿐 ({len(_solo):,} type)",
                            _SOLO, _acc, _only)
        if _pool:
            self._add_pool(_d, _joint, _only)

        _filt = (f" · [{' · '.join(self._display(_c) for _c in sorted(_only))}] 든 type "
                 f"{len(_rows):,}" if _only else "")
        if _joint:
            _axes = " × ".join(_b.Joint_coords()[0])
            self._res_label.setText(
                f"{_axes} · type {_b.Types(_d):,}{_filt}"
                + (f" · 단독 {len(_solo):,}" if _solo else "")
                + (f" · 보류 {sum(_pool.values()):,}" if _pool else ""))
        else:
            _own = " (도메인 지정)" if _b.Threshold_of(_d)[1] else " (공통값)"
            self._res_label.setText(
                f"k={_k:.3f}{_own} → k′={_kp:.3f} · type {_b.Types(_d):,}{_filt}"
                + (f" · 미배정 {sum(_pool.values()):,}" if _pool else ""))
        self._sync_pending_marks()      # 새로 세운 갈래 줄에도 대기 건수를 얹는다
        self._redraw_graph()
        if self._tree.topLevelItemCount():
            self._tree.setCurrentItem(self._tree.topLevelItem(0))
        else:
            self._note()
            self._redraw()

    def _sync_class_filter(self, comp: dict) -> set[str]:
        """필터 목록을 지금 도메인의 class 로 채우고 **고른 것들**을 돌려준다 (빈 집합 = 전체).

        고른 값은 이름으로 보존한다 — 도메인을 옮겨도 같은 class 를 계속 좇을 수 있어야 한다.
        """
        _cnt: Counter = Counter()
        for _c in comp.values():
            _cnt.update(_c)
        # **순서는 id_map 이 정한다** — 건수 순으로 두면 데이터가 바뀔 때마다 자리가 뒤바뀌어
        # 손이 기억한 위치가 무너진다. 사람이 아는 순서는 라벨 목록의 순서다.
        _order = [_c for _c in self._names if _c in _cnt]
        _order += [_c for _c in sorted(_cnt) if _c not in self._names]   # id_map 밖은 뒤에
        self._filter &= set(_cnt)               # 도메인이 바뀌어 없어진 class 는 떨군다
        _on = set(self._filter)
        self._class_filter.blockSignals(True)
        self._class_filter.clear()
        self._class_filter.addItem("class 추가…", "")
        for _c in _order:                       # **이미 담은 것은 안 보인다** — 고를 이유가 없다
            if _c not in _on:
                self._class_filter.addItem(f"{self._display(_c)} — {_cnt[_c]:,}", _c)
        self._class_filter.setCurrentIndex(0)
        self._class_filter.blockSignals(False)
        self._filter_note.setText(
            "" if not _on else
            f"거르는 중 ({len(_on)}) &nbsp; " + " &nbsp; ".join(
                f'<span style="background:#eef1f5;">&nbsp;{html.escape(self._display(_c))} '
                f'{_cnt.get(_c, 0):,}&nbsp;<a href="{html.escape(_c)}" '
                f'style="color:#a02020;text-decoration:none;">✕</a>&nbsp;</span>'
                for _c in _order if _c in _on))
        self._clear_filter.setEnabled(bool(_on))
        return _on

    def _on_filter_add(self, index: int) -> None:
        """콤보에서 골랐다 — 거르는 목록에 **더한다** (콤보 자리는 안내문으로 되돌린다)."""
        _c = str(self._class_filter.itemData(index) or "")
        if _c:
            self._filter.add(_c)
            self._fill_types()

    def _on_filter_link(self, href: str) -> None:
        """담긴 class 옆 ✕ — 그것만 뺀다."""
        self._filter.discard(str(href))
        self._fill_types()

    def _on_clear_filter(self) -> None:
        """[해제] — 거르는 class 를 전부 뺀다."""
        self._filter.clear()
        self._fill_types()

    def _group_label(self, domain: str, group: int, types: list[int]) -> str:
        """트리 갈래 이름. 종합이면 **축별 좌표**를 적는다 — 번호만으론 왜 갈렸는지 못 읽는다.

        ``#12  [outline 3 · signed 7]`` 처럼 보이면 옆 갈래와 대조해 어느 축이 달랐는지가 바로
        읽힌다. 그게 이 화면의 용건이다 ("실루엣은 같은데 구멍이 다르다").
        """
        if group == _SOLO:
            return f"단독 ({len(types):,} type)"
        if domain == JOINT and self._bucket is not None:
            # 병합 뒤에는 축 type 이 스물씩 들어와 번호를 다 적으면 줄이 안 읽힌다 — **개수**만.
            # 무엇이 뭉쳤는지는 툴팁이 든다(:meth:`_add_group`).
            _axis = self._bucket.Joint_axis_of(int(group))
            _txt = " · ".join(f"{_a.rsplit('_', 1)[-1]} {len(_ts)}"
                              for _a, _ts in _axis.items() if _ts)
            return f"#{group}" + (f"   [{_txt}]" if _txt else "")
        return f"#{group}" + (f"  ({len(types)}개 묶임)" if len(types) > 1 else "")

    def _add_group(self, label: str, group: int, acc: Counter,
                   only: set[str] | None = None) -> None:
        """트리 한 갈래 — type 줄 + class 줄. **표본은 아직 안 만든다**(펼칠 때 온다).

        ``only`` 로 거르는 중이면 수 칸이 **고른 class 들의 몫**이다 — 거르는 이유가 "이것들이 여기
        몇 건 있나" 인데 총계를 보이면 그 답이 안 나온다. 총계는 옆 칸으로 밀린다.
        """
        _total = max(sum(acc.values()), 1)
        _n = sum(acc.get(_c, 0) for _c in only) if only else _total
        _top = QTreeWidgetItem(self._tree,
                               [f"{label}   ({len(acc)} class)", f"{_n:,}",
                                f"/ {_total:,}" if only else "", ""])
        _top.setData(0, Qt.UserRole, ("group", int(group)))
        if self._domain_of() == JOINT and self._bucket is not None:
            _axis = self._bucket.Joint_axis_of(int(group))
            _top.setToolTip(0, "\n".join(
                f"{_a}: {', '.join(str(_v) for _v in _ts)}" for _a, _ts in _axis.items() if _ts))
        for _c, _n in acc.most_common():
            _it = QTreeWidgetItem(_top, [self._display(_c), f"{_n:,}", f"{_n / _total:.0%}", ""])
            _it.setData(0, Qt.UserRole, ("class", int(group), str(_c)))
            if _n:
                # 자리 표시 — 이게 있어야 화살표가 뜨고, 펼치는 순간 진짜 줄로 바뀐다.
                QTreeWidgetItem(_it, ["…", "", "", ""]).setData(0, Qt.UserRole, _LAZY)

    def _add_pool(self, domain: str, joint: bool, only: set[str] | None) -> None:
        """보류를 **최근접 이웃으로 이은 하위 무리**로 나눠 단다 (못 나누면 한 줄 그대로).

        한 덩어리로 쌓아 두면 그 안에 서로 닮은 것들이 섞여 있어도 목록에서 안 보인다. 나누는 규칙과
        "이건 배정이 아니다"라는 성질은 ``core.analysis.pool_groups`` 가 소유한다 — 여기는 **보이기만**
        한다(저장하지 않고, type 번호도 안 준다).

        종합(``JOINT``)은 좌표가 없어 이웃을 못 재므로 예전처럼 한 줄이다.
        """
        _b = self._bucket
        _label = "보류 (어느 축도 판단 못 함)" if joint else "미배정"
        _comp = _b.Composition(domain)
        _sub = self._pool_subgroups(domain)
        if len(_sub) < 2:                          # 나눌 게 없다 — 한 줄로 두는 게 정직하다
            _acc = _comp.get(POOL, Counter())
            if only:
                _acc = Counter({_c: _acc[_c] for _c in only if _acc.get(_c)})
            self._add_group(_label, POOL, _acc, only)
            return
        _index = _b.Index()
        for _i, _keys in enumerate(_sub):
            _acc = Counter(str(_index.get(_k, {}).get("class", "")) for _k in _keys)
            if only:
                _acc = Counter({_c: _acc[_c] for _c in only if _acc.get(_c)})
            if not _acc:
                continue
            _gid = _POOL_BASE - _i
            self._pool_groups[_gid] = list(_keys)
            self._add_group(f"{_label} #{_i}  — 최근접 이웃으로 이어진 무리 ({len(_keys):,} 건)",
                            _gid, _acc, only)

    def _pool_subgroups(self, domain: str) -> list[list[str]]:
        """보류 하위 무리 (캐시) — 좌표를 다시 읽는 일이라 같은 자리를 다시 그릴 때마다 돌리지 않는다.

        캐시 키에 type 수를 넣는다 — 재군집하면 보류 명단 자체가 달라지기 때문이다.
        """
        _b = self._bucket
        if _b is None or not domain:
            return []
        _key = (domain, _b.Types(domain), len(_b.Keys(domain, POOL)))
        if _key != self._pool_key:
            self._pool_key, self._pool_cache = _key, pool_groups(_b, domain)
        return self._pool_cache

    def _keys_of_group(self, group: int) -> list[str]:
        """그 갈래가 든 표본 key — **네 갈래가 여기 한 곳에서만 갈린다**.

        보류 하위 무리는 type 이 아니라(배정이 아니므로 번호가 없다) 자기 명단이 답하고, 나머지는
        "갈래 → type 번호들 → ``Keys``" 로 되짚는다. 예전엔 이 분기가 :meth:`_on_expand` 와
        :meth:`_addrs_of_selection` 에 각각 펼쳐져 있어 한쪽만 고치면 조용히 어긋났다.
        """
        _b, _d = self._bucket, self._domain_of()
        if _b is None or not _d:
            return []
        if group in self._pool_groups:
            return list(self._pool_groups[group])
        _types = [POOL] if group == POOL else self._groups.get(group, [])
        return [_k for _t in _types for _k in _b.Keys(_d, _t)]

    def _on_expand(self, item: QTreeWidgetItem) -> None:
        """class 줄을 펼쳤다 — **그때** 표본 줄을 만든다 (거리 내림차순).

        먼 것이 위다 — 억지로 붙은 것이라 사람이 먼저 봐야 한다. 종합은 좌표가 없어 거리가 전부
        ``inf`` 이므로 그대로 이름순이 된다.
        """
        _role = item.data(0, Qt.UserRole) or ()
        if len(_role) != 3 or item.childCount() != 1:
            return
        if (item.child(0).data(0, Qt.UserRole) or ()) != _LAZY:
            return
        _b, _d = self._bucket, self._domain_of()
        if _b is None or not _d:
            return
        item.takeChildren()
        _g, _cls = int(_role[1]), str(_role[2])
        _index, _dist = _b.Index(), _b.Distances(_d)
        _keys = [_k for _k in self._keys_of_group(_g)
                 if str(_index.get(_k, {}).get("class", "")) == _cls]
        _keys.sort(key=lambda _k: -_dist.get(_k, 0.0))
        self._tree.blockSignals(True)
        for _k in _keys:
            _stem, _obj = Cluster_Bucket.Address(_k)
            _v = _dist.get(_k, float("inf"))
            _row = QTreeWidgetItem(item, [f"{_stem} · obj {_obj}",
                                          "∞" if not np.isfinite(_v) else f"{_v:.4f}",
                                          self._display(_cls), ""])
            _row.setData(0, Qt.UserRole, ("sample", _k))
            _row.setFlags(_row.flags() | Qt.ItemIsUserCheckable)
            _row.setCheckState(0, Qt.Checked if (_stem, _obj) in self._checked else Qt.Unchecked)
            self._mark_pending(_row, self._pending.get((_stem, _obj)))   # 표기는 한 자리가 소유
        self._tree.blockSignals(False)
        self._note()

    def _on_check(self, item: QTreeWidgetItem, column: int) -> None:
        """표본 체크 — **옮길 대상**이다(선택은 보는 대상이라 따로 논다)."""
        _role = item.data(0, Qt.UserRole) or ()
        if column or len(_role) != 2 or _role[0] != "sample":
            return
        _a = Cluster_Bucket.Address(str(_role[1]))
        if item.checkState(0) == Qt.Checked:
            self._checked.add(_a)
        else:
            self._checked.discard(_a)
        self._note()

    def _on_activate(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        """표본 줄 더블클릭 → 메인 본문을 그 표본으로 옮긴다 (다른 줄은 Qt 기본 = 펼치기).

        여기서 화면을 옮기지 않고 주소만 올린다 — 이 창은 정본도 본문도 모른다(읽기 전용 판정 화면이다).
        """
        _role = item.data(0, Qt.UserRole) or ()
        if len(_role) == 2 and _role[0] == "sample":
            _stem, _obj = Cluster_Bucket.Address(str(_role[1]))
            self.focus_requested.emit(_stem, int(_obj))

    @staticmethod
    def _anchor(item) -> tuple:
        """그 줄이 가리키는 **type/class 자리** — 표본 줄이면 부모를 거슬러 올라간다."""
        while item is not None:
            _role = item.data(0, Qt.UserRole) or ()
            if _role and _role[0] in ("group", "class"):
                return _role
            item = item.parent()
        return ()

    def _selected_groups(self) -> list[int]:
        """고른 줄이 가리키는 **갈래 번호들** — 표본을 되짚는 축(:meth:`_keys_of_group` 의 입력)."""
        return sorted({int(_r[1]) for _it in self._tree.selectedItems()
                       if (_r := self._anchor(_it))})

    def _selected_types(self) -> list[int]:
        """고른 줄이 가리키는 **type 번호들** (미배정이면 ``[POOL]``).

        갈래와 갈라 둔다 — 반경·다수파처럼 *type* 을 다루는 것들이 쓴다. 보류 하위 무리는 type 이
        아니므로 여기서 아무것도 안 낸다(그 갈래를 골라 반경을 고칠 수는 없다는 뜻이고, 맞다).
        """
        _out: list[int] = []
        for _g in self._selected_groups():
            if _g in self._pool_groups:
                continue
            _out += [POOL] if _g == POOL else self._groups.get(_g, [])
        return sorted(set(_out))

    def _selected_classes(self) -> set[str]:
        """class 줄(또는 그 아래 표본)을 골랐으면 그 class 들 — 비면 거르지 않는다."""
        return {str(_r[2]) for _it in self._tree.selectedItems()
                if len(_r := self._anchor(_it)) == 3}

    def _selected_samples(self) -> list[str]:
        """직접 고른 **표본 줄**의 key — 형상에 그릴 대상이다."""
        return [str(_r[1]) for _it in self._tree.selectedItems()
                if len(_r := (_it.data(0, Qt.UserRole) or ())) == 2 and _r[0] == "sample"]

    def _on_type(self) -> None:
        _n = len({_it.data(0, Qt.UserRole)[1] for _it in self._tree.selectedItems()
                  if _it.data(0, Qt.UserRole)})
        _cls = self._selected_classes()
        self._comp_note.setText(
            "여러 class 가 한 type 에 있다 — 이 데이터로 안 갈린다는 뜻이다. 다만 **작은 class 가 "
            "큰 class 안에 들어앉은 경우**도 이렇게 보이므로 그대로 '같은 물건' 으로 읽으면 안 된다."
            if _n == 1 and not _cls and self._multi_class() else "")
        self._note()
        self._redraw()
        self._redraw_graph()

    def _multi_class(self) -> bool:
        _b, _d = self._bucket, self._domain_of()
        if _b is None or not _d:
            return False
        _comp = _b.Composition(_d)
        _acc: Counter = Counter()
        for _t in self._selected_types():
            _acc.update(_comp.get(_t, Counter()))
        return len(_acc) > 1

    def _note(self) -> None:
        """트리 밑줄 — 고른 자리·체크·**대기 내역**. 한 자리에서만 쓴다(문구가 갈리면 어긋난다).

        대기는 건수만으로는 안 읽힌다("12건"이 어디로 가는 12건인가) — **목적지별로** 쪼개 적는다.
        많으면 위 셋만 적고 나머지는 접는다.
        """
        _txt = (f"고른 자리 {len(self._addrs_of_selection()):,} 건  ·  체크 {len(self._checked):,}"
                "  —  체크 = 옮길 대상 · 표본 줄 선택 = 형상에 그린다")
        if self._pending:
            _by = Counter(str(_c) for _c in self._pending.values())
            _top = _by.most_common(3)
            _parts = " · ".join(f"{self._display(_c)} {_n:,}" for _c, _n in _top)
            _rest = len(_by) - len(_top)
            _txt += (f"\n대기 {len(self._pending):,} 건 → {_parts}"
                     + (f" · 그 외 {_rest} class" if _rest > 0 else "")
                     + "   (아직 정본에 안 씀 — [적용] 이 쓴다)")
        self._sample_note.setText(_txt)

    def _on_type_menu(self, pos) -> None:
        """트리 우클릭 — 고른 자리/표본에 할 일 + 이 도메인의 반경(재군집은 [clustering]).

        어느 줄에서 눌러도 같은 메뉴다 — 항목은 **무엇을 골랐나**로 갈린다(자리 / 고른 표본 / 체크한 표본).
        """
        _d = self._domain_of()
        if not _d:
            return
        _menu = QMenu(self)
        _all = self._addrs_of_selection()
        _cls = self._selected_classes()
        _what = f"이 class 만 ({len(_all)})" if _cls else f"이 type 전체 ({len(_all)})"
        _mv = _menu.addAction(f"{_what} → class 이동…")
        _mv.setEnabled(bool(_all))
        _mv.triggered.connect(lambda: self.move_requested.emit(_all, ""))
        _un = _menu.addAction(f"{_what} → 미분류로")
        _un.setEnabled(bool(_all))
        _un.triggered.connect(lambda: self.unlabel_requested.emit(_all))
        _menu.addSeparator()                       # 흩어진 라벨을 type 의 다수파로 모은다
        self._add_unify(_menu, self._selected_types(), "고른 type →")

        _sel = self._selected_samples()
        if _sel or self._checked:
            _menu.addSeparator()
        if _sel:
            # 고른 것을 체크로 옮기는 길 — 여럿을 골라 놓고 체크박스를 하나씩 누르게 두지 않는다.
            _menu.addAction(f"고른 표본 전부 체크 ({len(_sel)})", self._check_selected)
        if self._checked:
            _ck = sorted(self._checked)
            _a = _menu.addAction(f"체크한 표본 → class 이동… ({len(_ck)})")
            _a.triggered.connect(lambda: self.move_requested.emit(_ck, ""))
            _b2 = _menu.addAction(f"체크한 표본 → 미분류로 ({len(_ck)})")
            _b2.triggered.connect(lambda: self.unlabel_requested.emit(_ck))
            _menu.addAction("체크 전부 해제", self._uncheck_all)
        _menu.addSeparator()
        for _v in (0.01, 0.02, 0.03, 0.05, 0.1, 0.2):
            _menu.addAction(f"반경 k = {_v:.3f}",
                            lambda _x=_v: self.threshold_requested.emit(_d, _x))
        _menu.addSeparator()
        _menu.addAction(f"지금 해상도 k′ = {self._res_k():.3f} 로 지정",
                        lambda: self.threshold_requested.emit(_d, self._res_k()))
        _menu.addAction("공통값으로 되돌리기", lambda: self.threshold_requested.emit(_d, -1.0))
        _menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ── 최다 class 로 통일 ──────────────────────────────────────────────────────
    def _add_unify(self, menu, types: list[int], what: str) -> None:
        """메뉴에 "``what`` 마다 최다 class 로 통일" 을 단다 — **옮길 게 없으면 안 단다**."""
        _plan, _tied, _none, _kept = self._unify_plan(types)
        if not (_plan or _tied or _none or _kept):
            return
        _n = sum(len(_a) for _a, _ in _plan)
        _why = [_t for _t in (f"표결 미달 {len(_tied)}" if _tied else "",
                              f"미분류 최다 {len(_none)}" if _none else "",
                              f"본거지 보호 {len(_kept)}" if _kept else "") if _t]
        _skip = f"  [건너뜀: {' · '.join(_why)}]" if _why else ""
        _act = menu.addAction(f"{what} 최다 class 로 통일 ({len(_plan)} type · {_n:,} 건){_skip}")
        _act.setEnabled(bool(_plan))
        _act.triggered.connect(lambda _c=False, p=list(_plan): self.unify_requested.emit(p))

    #: 소수파를 **흡수하지 않는** 문턱 — 그 class 전체 표본 중 이 type 에 있는 몫.
    #:
    #: 넘으면 그건 "흩어진 몇 개" 가 아니라 **그 class 의 본거지**다. 10개뿐인 부품에서 6개가
    #: 오분류되면 이 type 의 다수결은 틀린 쪽이고, 통일하면 제대로 붙은 4개까지 넘어가 **class 가
    #: 통째로 사라진다**(id 역전). 다수결이 답할 수 없는 자리라 손대지 않는다.
    _ABSORB_SHARE = 0.5

    #: 다수결이 성립하려면 1등이 2등의 몇 배여야 하나 — **6 대 4 짜리 표결은 표결이 아니다**.
    #: 2배로 잡으면 6:4(6 < 8)는 미달이고 100:3 은 통과한다. 60:40 처럼 팽팽한 자리는 "다수" 가 아니라
    #: **안 갈린 것**이라 손대면 안 된다.
    _VOTE_MARGIN = 2.0

    def _unify_plan(self, types: list[int]) -> tuple[list, list[int], list[int]]:
        """type 마다 ``(옮길 주소들, 최다 class)`` — **소수파만** 옮긴다.

        두 경우는 **빼고 그 사실을 알린다**(조용히 아무 쪽으로나 붙이지 않는다):

        - **동률** — 최다가 둘 이상이면 "최다 class" 가 없다. 한쪽을 골라 주면 그건 근거가 아니라 동전이다.
        - **미분류가 최다** — 통일하면 라벨이 붙은 소수파의 근거를 지운다. 이 기능은 흩어진 라벨을
          모으는 것이지 지우는 것이 아니다(지우려면 [미분류로]가 따로 있다).

        Returns:
            ``(계획, 동률로 뺀 type, 미분류 최다라 뺀 type)``.
        """
        _b, _d = self._bucket, self._domain_of()
        if _b is None or not _d:
            return [], [], []
        _index, _comp = _b.Index(), _b.Composition(_d)
        _totals: Counter = Counter()             # class 전체 표본 수 — 흡수 판정의 분모
        for _acc in _comp.values():
            _totals.update(_acc)
        _plan, _tied, _none, _kept = [], [], [], []
        for _t in types:
            if _t == POOL:              # 미배정은 type 이 아니다 — "이 무리의 다수파" 라는 근거가 없다
                continue
            _acc = _comp.get(_t, Counter())
            _ranked = _acc.most_common()
            if len(_ranked) < 2:                     # 비었거나 이미 한 class — 옮길 것이 없다
                continue
            if _ranked[0][1] < self._VOTE_MARGIN * _ranked[1][1]:
                _tied.append(_t)                     # 표결이 안 됐다 (동률 포함)
                continue
            _win = str(_ranked[0][0])
            if _win == str(UNCLASSIFIED_ID):
                _none.append(_t)
                continue
            # **본거지인 class 는 안 건드린다** — 옮기면 그 class 가 사라진다(위 `_ABSORB_SHARE`).
            _keep = {str(_c) for _c, _n in _acc.items()
                     if str(_c) != _win and _n / max(_totals.get(_c, 0), 1) >= self._ABSORB_SHARE}
            if _keep:
                _kept.append(_t)                     # 보호했다는 사실을 알린다 (조용히 넘기지 않는다)
            _addrs = [Cluster_Bucket.Address(_k) for _k in _b.Keys(_d, _t)
                      if (_c := str(_index.get(_k, {}).get("class", ""))) != _win
                      and _c not in _keep]
            if _addrs:
                _plan.append((_addrs, _win))
        return _plan, _tied, _none, _kept

    def _addrs_of_selection(self) -> list:
        """트리에서 고른 자리의 **표본 주소 전부** — 목록에 보이는 것과 무관하게 index 에서 모은다
        ("이 type 을 통째로 옮긴다" 가 실제 작업이라, 보이는 만큼만 옮기면 조용히 일부만 옮겨진다)."""
        _b, _d = self._bucket, self._domain_of()
        if _b is None or not _d:
            return []
        _index = _b.Index()
        _want = self._selected_classes()
        _keys = [_k for _g in self._selected_groups() for _k in self._keys_of_group(_g)]
        if _want:
            _keys = [_k for _k in _keys
                     if str(_index.get(_k, {}).get("class", "")) in _want]
        return [Cluster_Bucket.Address(_k) for _k in sorted(set(_keys))]

    def _check_selected(self) -> None:
        """고른 **표본 줄**을 전부 체크한다 — 선택(보는 대상)을 체크(옮길 대상)로 옮기는 길.

        둘이 따로 노는 건 의도다(형상에 그려 보는 것과 옮길 것을 고르는 것은 다른 일이다). 다만 훑어보다
        "이것들이다" 싶을 때 하나씩 체크박스를 누르게 두면 그 판단이 끊긴다 — 여기가 그 다리다.
        선택에 type·class 줄이 섞여 있어도 **표본 줄만** 집는다.

        신호를 막고 :attr:`_checked` 를 직접 갱신하는 건 :meth:`_uncheck_all` 과 같은 이유다 — 줄마다
        ``itemChanged`` 가 튀면 수천 건에서 그만큼 재계산이 돈다.
        """
        self._tree.blockSignals(True)
        for _it in self._tree.selectedItems():
            _role = _it.data(0, Qt.UserRole) or ()
            if len(_role) == 2 and _role[0] == "sample":
                _it.setCheckState(0, Qt.Checked)
                self._checked.add(Cluster_Bucket.Address(str(_role[1])))
        self._tree.blockSignals(False)
        self._note()

    def _uncheck_all(self) -> None:
        """체크 해제 — 트리에 이미 만들어진 줄만 손보면 된다(안 펼친 것은 애초에 체크가 없다)."""
        self._checked.clear()
        self._tree.blockSignals(True)
        _it = QTreeWidgetItemIterator(self._tree)
        while _it.value():
            _n = _it.value()
            if (_n.data(0, Qt.UserRole) or ("",))[0] == "sample":
                _n.setCheckState(0, Qt.Unchecked)
            _it += 1
        self._tree.blockSignals(False)
        self._note()

    # ── 형상 ────────────────────────────────────────────────────────────────────
    def _embed(self, domain: str, how: str) -> tuple[np.ndarray, str]:
        """type 중심의 3D 배치 ``((M, 3), 설명 문구)`` — ``how`` 가 방법을 고른다.

        UMAP 은 **배치에만** 쓴다 — 판정에 해당하는 값(거리·간선·묶기)은 전부 원 좌표에서 나온다.
        """
        _key = ("embed", domain, how, self._bucket.Types(domain) if self._bucket else 0)
        if _key == getattr(self, "_embed_key", None):
            return self._embed_xy, self._embed_note
        if how == "umap":
            _xy, _note = self._umap(self._bucket.Centers(domain))
        else:
            _xy, _kept = self._mds(domain)
            _note = (f"MDS 3축이 담은 몫 {_kept:.0%}"
                     + ("  — 낮다: 배치는 참고만" if _kept < 0.5 else ""))
        self._embed_key, self._embed_xy, self._embed_note = _key, _xy, _note
        return _xy, _note

    @staticmethod
    def _umap(C: np.ndarray) -> tuple[np.ndarray, str]:
        """UMAP 2D — 없거나 표본이 모자라면 영좌표와 사유를 돌려준다(조용히 안 죽는다)."""
        if len(C) < 4:
            return np.zeros((len(C), 3)), "UMAP: type 이 너무 적다"
        try:
            from umap import UMAP
        except ImportError:
            return np.zeros((len(C), 3)), "UMAP 미설치 — `pip install umap-learn`"
        _xy = UMAP(n_components=3, n_neighbors=min(15, len(C) - 1), min_dist=0.10,
                   metric="euclidean", random_state=0).fit_transform(np.asarray(C, np.float32))
        return np.asarray(_xy, float), "UMAP — **거리·간격에 뜻 없음**, 선만 사실"

    def _mds(self, domain: str) -> tuple[np.ndarray, float]:
        """type 중심을 3D 로 편 좌표 ``(M, 3)`` 와 **그 3축이 담은 분산 몫**.

        고전 MDS(Torgerson) — 제곱거리를 이중중심화한 Gram 행렬의 상위 고유벡터다. 입력이 이미
        유클리드 좌표라 이 경우 **중심들의 PCA 와 같다**. 힘기반 배치는 거리를 보존하지 않아
        "선이 짧으면 가깝다" 가 거짓이 되므로 안 쓴다.

        **담은 몫을 함께 낸다** — 그 값이 작으면 그림을 믿으면 안 되는데, 화면이 말하지 않으면
        사용자는 배치를 사실로 읽는다. 축이 셋인 것도 같은 이유다(2축은 실측 61% 라 나머지가 화면
        밖에서 겹쳤고, 돌려 보면 그 겹침이 풀린다).

        Returns:
            ``((M, 3) 좌표, 상위 3축이 담은 분산 몫 [0, 1])``.
        """
        _key = ("mds", domain, self._bucket.Types(domain) if self._bucket else 0)
        if _key == getattr(self, "_mds_key", None):
            return self._mds_xy, self._mds_kept
        _C = self._bucket.Centers(domain)
        _kept = 0.0
        if len(_C) < 3:
            _xy = np.zeros((len(_C), 3))
        else:
            _q = (_C ** 2).sum(1)
            _D2 = np.maximum(_q[:, None] + _q[None, :] - 2.0 * _C @ _C.T, 0.0)
            _J = np.eye(len(_C)) - 1.0 / len(_C)
            _w, _v = np.linalg.eigh(-0.5 * _J @ _D2 @ _J)
            _xy = _v[:, -3:] * np.sqrt(np.maximum(_w[-3:], 0.0))
            _pos = _w[_w > 0]
            _kept = float(_w[-3:][_w[-3:] > 0].sum() / _pos.sum()) if _pos.size else 0.0
        self._mds_key, self._mds_xy, self._mds_kept = _key, _xy, _kept
        return _xy, _kept

    def _redraw_graph(self) -> None:
        """type 근접 그래프 — 점 크기 ∝ 표본, 색 = class 종수, 선 = ``k'`` 안의 쌍."""
        self._gfig.clear()
        _b, _d = self._bucket, self._domain_of()
        if _d == JOINT:
            # 종합은 축들의 곱이라 **좌표가 없다** — 중심끼리 잴 것이 없으니 배치도 없다.
            self._graph_title.setText(
                "종합에는 근접 그래프가 없다 — 좌표가 아니라 축 label 의 조합이다. "
                "축을 골라 보면 그 축의 그래프가 나온다")
            self._gcanvas.draw()
            return
        if _b is None or not _d or _b.Types(_d) < 2:
            self._gcanvas.draw()
            return
        _M = _b.Types(_d)
        if _M > _GRAPH_MAX:
            self._graph_title.setText(f"type {_M:,}개 — 너무 많아 그리지 않는다 (상한 {_GRAPH_MAX:,})")
            self._gcanvas.draw()
            return

        _how = str(self._layout_mode.currentData() or "mds")
        _xy, _note = self._embed(_d, _how)
        _comp = _b.Composition(_d)
        _n = np.asarray([sum(_comp.get(_t, Counter()).values()) for _t in range(_M)], float)
        _ncls = np.asarray([len(_comp.get(_t, Counter())) for _t in range(_M)], float)
        _C = _b.Centers(_d)
        _kp = self._res_k()

        # **간선은 원 거리로 긋는다** — 배치가 3D 로 눌러 뭉갠 자리에서도 "k′ 안" 은 사실이다.
        _q = (_C ** 2).sum(1)
        _D = np.sqrt(np.maximum(_q[:, None] + _q[None, :] - 2.0 * _C @ _C.T, 0.0))
        _i, _j = np.where(np.triu(_D <= _kp, 1))

        _ax = self._gfig.add_subplot(111, projection="3d")
        if len(_i):
            # 선분을 **한 컬렉션**으로 — 하나씩 plot 하면 수백 개에서 눈에 띄게 느려진다.
            _seg = np.stack([_xy[_i[:_EDGE_MAX]], _xy[_j[:_EDGE_MAX]]], axis=1)
            _ax.add_collection3d(Line3DCollection(_seg, colors="#4a90d9",
                                                  linewidths=0.6, alpha=0.35))
        _sel = set(self._selected_types())
        _size = 12.0 + 120.0 * (_n / max(_n.max(), 1.0)) ** 0.5
        _ax.scatter(_xy[:, 0], _xy[:, 1], _xy[:, 2], s=_size, c=_ncls, cmap="YlOrRd",
                    vmin=1, vmax=max(_ncls.max(), 2), edgecolors="#555", linewidths=0.3,
                    depthshade=False)
        _sel = [_t for _t in self._selected_types() if 0 <= _t < _M]
        if _sel:
            _ax.scatter(_xy[_sel, 0], _xy[_sel, 1], _xy[_sel, 2], s=_size[_sel] + 90,
                        facecolors="none", edgecolors="#111", linewidths=1.4, depthshade=False)
        for _axis in (_ax.xaxis, _ax.yaxis, _ax.zaxis):
            _axis.set_ticklabels([])
            _axis.set_pane_color((1.0, 1.0, 1.0, 0.0))      # 벽면을 지운다 — 점이 축이다
        _ax.grid(alpha=0.15)
        # **배치를 얼마나 믿을지를 먼저 적는다** — 그림은 늘 사실보다 그럴듯해 보인다.
        self._graph_title.setText(
            f"{_note} · 점 {_M:,} · 선 {len(_i):,}쌍 (k′={_kp:.3f} 안) · 색 = class 종수"
            f"  —  **끌어서 돌린다**")
        # **3D 축에는 `tight_layout` 을 안 쓴다** — 투영이라 여백을 못 재고, 다시 그릴 때마다
        # "Tight layout not applied" 경고를 뱉는다(회전 한 번에 수십 줄). 여백을 직접 준다.
        _mode = str(self._label_mode.currentData() or "none")
        if _mode != "none":
            _who = range(_M) if _mode == "all" else sorted(_sel)
            for _t2 in _who:
                if 0 <= _t2 < _M:
                    _ax.text(_xy[_t2, 0], _xy[_t2, 1], _xy[_t2, 2], f"{_t2}",
                             fontsize=6, color="#333333")
        _z = float(self._graph_zoom.currentData() or 1.0)
        if _z > 1.0:                      # 가운데를 기준으로 잘라 본다 — 배치는 그대로다
            for _set, _lim in ((_ax.set_xlim, _ax.get_xlim()), (_ax.set_ylim, _ax.get_ylim()),
                               (_ax.set_zlim, _ax.get_zlim())):
                _c0 = (_lim[0] + _lim[1]) / 2.0
                _h = (_lim[1] - _lim[0]) / (2.0 * _z)
                _set(_c0 - _h, _c0 + _h)
        self._gfig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        self._gcanvas.draw()

    def _token_domains(self) -> list[str]:
        """형상으로 그릴 수 있는 도메인 — 성질이 :data:`~core.analysis.TOKEN` 인 것."""
        _kinds = self._bucket.Kinds() if self._bucket is not None else {}
        return [_d for _d, _k in _kinds.items() if _k == TOKEN]

    @staticmethod
    def _polar_theta(nt: int) -> np.ndarray:
        """token bin 색인 → matplotlib polar 각도.

        ``Polar_Raster`` 는 bin ``j`` 를 ``(j+0.5)*dtheta - pi`` 에 두고 그 좌표의 세로축을
        **row(아래 방향)** 으로 쓴다. matplotlib polar 는 반시계·y 위쪽이라 부호가 뒤집히므로
        ``phi = pi - (j+0.5)*dtheta`` 다 (실마스크 40개 정합 RMS 0.48px).
        """
        return np.pi - (np.arange(nt) + 0.5) * (2.0 * np.pi / nt)

    @staticmethod
    def _close_loop(theta: np.ndarray, *arrays: np.ndarray):
        """극좌표 폐곡선용 끝점 이어붙이기.

        ``theta`` 가 **감소열**이라 시작점을 그대로 붙이면 반대 방향으로 한 바퀴 되돌아간다.
        """
        return (np.append(theta, theta[0] - 2.0 * np.pi),
                *(np.append(_a, _a[0]) for _a in arrays))

    @classmethod
    def _bands_of(cls, folds, angular: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
        """잣대 값 → 살 밴드마다 ``(안쪽 반지름, 바깥 반지름)``. 표는 :data:`BAND_READERS`.

        **접기를 봐야 뜻이 정해진다** — 같은 ``(NT, 2)`` 여도 원본 간격이면 ``[시작r, 살]`` 이라
        누적이 경계고, ``[signed, outline]`` 이면 누적은 아무 뜻도 아니다. 그래서 값의 shape 으로는
        못 고르고 잣대가 든 접기 조합으로 고른다.

        표에 없는 조합이면 **빈 목록**이다 — 반지름으로 읽을 근거가 없다는 뜻이고, 호출 측이
        채널 그림으로 넘긴다(억지로 그리면 거짓 형상이 된다).
        """
        _r = BAND_READERS.get(tuple(folds))
        if _r is None:
            return []
        _a = np.asarray(angular, np.float64)
        return _r(_a) if _a.ndim == _r.ndim else []

    def _draw_shape(self, ax, angular: np.ndarray, label: str, color,
                    alpha: float = 1.0, width: float = 2.0, folds=(),
                    spread: np.ndarray | None = None) -> None:
        """한 항목의 형상 — 살 채움 + 바깥 윤곽(실선) + 내부 경계(파선).

        ``spread`` 를 주면 바깥 윤곽에 **±1σ 띠**를 옅게 얹는다. 그것이 "이 type 이 얼마나 한
        덩어리인가" 다 — 띠가 얇으면 멤버가 겹쳐 있고, 두꺼우면 평균이 대표하지 못한다.
        """
        _bands = self._bands_of(folds, angular)
        if not _bands:
            return
        _theta = self._polar_theta(len(_bands[0][0]))
        if spread is not None:
            _s = np.asarray(spread, np.float64)
            _s = _s.reshape(np.shape(angular))[..., -1] if _s.ndim > 1 else _s
            _out = np.nanmax(np.stack([np.nan_to_num(_hi) for _, _hi in _bands]), axis=0)
            if _s.shape == _out.shape:
                ax.fill_between(*self._close_loop(_theta, _out - _s, _out + _s),
                                color=color, alpha=0.16 * alpha, linewidth=0)
        for _lo, _hi in _bands:
            ax.fill_between(*self._close_loop(_theta, _lo, _hi),
                            color=color, alpha=0.25 * alpha, linewidth=0)
        for _lo, _hi in _bands:
            for _r in (_lo, _hi):
                ax.plot(*self._close_loop(_theta, _r), color=color,
                        linewidth=0.8, alpha=0.55 * alpha, linestyle="--")
        _outer = np.nanmax(np.stack([np.nan_to_num(_hi) for _, _hi in _bands]), axis=0)
        ax.plot(*self._close_loop(_theta, _outer), color=color, linewidth=width,
                alpha=0.95 * alpha, **({"label": label} if label else {}))

    def _merged_shape(self, domain: str, type_ids: list[int]) -> np.ndarray | None:
        """고른 type 들의 **병합 중심**을 원 단위(px)로 되돌린다 — 멤버를 안 읽는다.

        중심은 충분통계 ``Σx/n`` 이고 좌표는 :func:`~core.analysis.equalize` 를 거친 것이라
        ``x = z·√D·std + mean`` 으로 되돌린다. 여러 type 을 묶어 보고 있으면 **표본 수로 가중해**
        합친다 — 그게 그 해상도에서의 한 덩어리다.

        Returns:
            ``(NT, K)`` 원 단위 값. 잴 것이 없으면 None.
        """
        _b = self._bucket
        if _b is None:
            return None
        _ids = [_t for _t in type_ids if _t >= 0]
        _stats = _b.Type_stats(domain)
        if not _ids or not _stats.count:
            return None
        _n = _stats.n[_ids].sum()
        if _n <= 0:
            return None
        _z = _stats.sum[_ids].sum(0) / _n                     # 가중 평균 = 병합 중심
        _norm = _b.Norm().get(domain) or {}
        _shape = tuple((_b.Contract().get("gauges") or {}).get(domain, {}).get("shape") or ())
        _raw = _z * np.sqrt(len(_z)) * float(_norm.get("std", 1.0)) + float(_norm.get("mean", 0.0))
        return _raw.reshape(_shape) if _shape else None

    def _mean_shape(self, member_of: str, draw_as: str, type_ids: list[int],
                    raw: bool) -> tuple[np.ndarray | None, np.ndarray | None, int]:
        """고른 type 에 **속한 표본들의 평균** ``(값, 센 표본 수)``.

        도메인이 **둘**이다. ``member_of`` 는 "누가 이 type 의 멤버인가" 를 답하는 자리(트리에서 고른
        도메인 — 종합일 수도 있다)고, ``draw_as`` 는 "그 표본에서 무엇을 읽어 그릴 것인가" 다. 종합은
        멤버는 알지만 자기 좌표가 없어 축 하나를 빌려 그리므로 둘이 갈린다. 한때 이 둘을 하나로 묶어
        두었더니 종합에서 **축의 type 번호로 멤버를 찾아** 엉뚱한 표본을 평균했다.

        ``raw`` 가 **무엇을 읽을지**를 가른다:

        * ``True`` (실루엣) — 저장된 **원본 feature**. 잣대는 구멍 여럿을 한 겹으로 접으므로 형상을
          볼 때는 원본이라야 실제 모양이 나온다.
        * ``False`` (채널) — **잣대 값**. 채널 그림은 표본도 잣대 값으로 그리므로 평균만 원본을 쓰면
          채널 수부터 다르다(``radial_rle`` 4096 vs ``radial_signed`` 512) — 나란히 놓을 수 없는
          두 가지를 겹쳐 그리게 된다.

        **산포도 함께 낸다** — 채널마다의 표준편차다. 평균만 그리면 "이 type 이 한 덩어리인가" 를
        못 읽는다: 같은 평균이라도 멤버가 딱 붙어 있는 것과 넓게 퍼진 것은 다른 것이고, 그 판단이
        곧 이 화면의 용건이다. 옅은 띠로 얹으면 선 하나를 더 그리지 않고도 보인다.

        멤버를 읽으므로 :data:`_MEAN_CAP` 건에서 끊는다 — 앞에서 자르지 않고 **고르게 뽑는다**
        (표본 목록이 거리순이라 앞만 쓰면 중심 근처만 평균하게 된다).

        Returns:
            ``(평균, 표준편차, 센 표본 수)`` — 못 읽으면 ``(None, None, 0)``. 표본이 하나면
            표준편차가 없으므로 ``None`` 이다(0 을 내면 "퍼짐이 없다" 로 읽힌다).
        """
        _b = self._bucket
        if _b is None:
            return None, None, 0
        _src = _b.Gauges().get(draw_as, (draw_as, ()))[0]
        _keys = [_k for _t in type_ids for _k in _b.Keys(member_of, _t)]
        if not _keys:
            return None, None, 0
        _step = max(len(_keys) // _MEAN_CAP, 1)
        _use = _keys[::_step][:_MEAN_CAP]
        _acc, _sq, _n = None, None, 0
        for _k in _use:
            _addr = _b.Address(_k)
            _v = (_b.Features(_addr, [_src]).get(_src) if raw
                  else _b.Measure(_addr, [draw_as]).get(draw_as))
            if _v is None:
                continue
            _a = np.asarray(_v, np.float64)
            _acc, _sq = (_a, _a ** 2) if _acc is None else (_acc + _a, _sq + _a ** 2)
            _n += 1
        if not _n:
            return None, None, 0
        _mean = _acc / _n
        # 표본 하나면 퍼짐이 정의되지 않는다 — 0 을 내면 "안 퍼졌다" 로 읽혀 거짓말이 된다.
        _std = np.sqrt(np.maximum(_sq / _n - _mean ** 2, 0.0)) if _n > 1 else None
        return _mean, _std, _n

    def _redraw(self) -> None:
        """type 의 평균을 굵게, **고른 표본**을 그 위에 색으로.

        평균이 **둘**이다. 검정은 잣대 좌표의 중심(충분통계를 되돌린 값 — 디스크를 안 탄다), 빨강은
        저장된 원본의 평균(멤버를 읽는다). 접기가 있으면 둘이 갈라지고, 그 차이가 잣대가 버린
        정보다. 종합(:data:`~core.analysis.cluster.JOINT`)에는 좌표가 없으므로 빨강만 나온다.

        도메인 **성질에 맞춰** 그린다 — ``TOKEN`` 은 θ 프로파일이라 극좌표 실루엣이 되지만
        ``FEATURE`` 는 순서 없는 채널이라 극좌표로 그리면 뜻이 없다.
        """
        self._fig.clear()
        _b, _d = self._bucket, self._domain_of()
        if _b is None or not _d:
            self._shape_title.setText("—")
            self._canvas.draw()
            return
        _draw_as = self._draw_domain(_d)         # 종합은 그릴 좌표가 없어 첫 축을 빌린다
        _mode = str(self._views.get(_draw_as, "auto"))
        _token = (_b.Kinds().get(_draw_as) == TOKEN) if _mode == "auto" else (_mode == "silhouette")
        if _token and not self._drawable_as_shape(_b, _draw_as):
            _token = False                       # 실루엣으로 그릴 수 없는 shape — 조용히 안 그리지 않는다
        _src, _folds = _b.Gauges().get(_draw_as, (_draw_as, ()))
        _forced = "  [보기 고정]" if _mode != "auto" else ""

        _ax = self._fig.add_subplot(111, projection="polar" if _token else None)
        _types = self._selected_types()

        # **type 마다 따로 그린다 — 평균 내지 않는다.** 여럿을 고르는 이유가 "이것들이 서로
        # 다른가" 를 보려는 것인데, 합쳐 버리면 그 물음이 사라진다(가운데 하나만 남는다).
        _drawn, _total = [], 0
        for _t2 in _types[:_TYPE_CAP]:
            _color = _ax._get_lines.get_next_color()
            _mean, _std, _cnt = self._mean_shape(_d, _draw_as, [_t2], raw=_token)
            if _mean is None:
                continue
            _total += _cnt
            _name = "미배정" if _t2 == POOL else f"#{_t2}"
            _band = _std if self._spread.isChecked() else None
            if _token:
                self._draw_shape(_ax, _mean, f"{_name} (n={_cnt})", _color, width=2.2, spread=_band)
            else:
                self._draw_channels(_ax, _mean.ravel(), f"{_name} (n={_cnt})", _color, width=2.2,
                                    spread=None if _band is None else _band.ravel())
            _drawn.append(_t2)

        # 잣대 중심은 **하나만 골랐을 때**만 얹는다 — 여럿이면 색이 두 배가 되어 안 읽히고,
        # type 끼리의 거리는 위 그래프가 답하는 자리다.
        _merged = (self._merged_shape(_d, _types)
                   if _d != JOINT and len(_drawn) == 1 else None)
        if _merged is not None:
            if _token:
                self._draw_shape(_ax, _merged, "gauge center", "#111111", width=1.4, folds=_folds)
            else:
                self._draw_channels(_ax, _merged, "gauge center", "#111111", width=1.4)

        _who = f"{_d}" + (f"  (형상은 {_draw_as})" if _draw_as != _d else "")
        _more = f" · +{len(_types) - _TYPE_CAP} type 은 안 그렸다" if len(_types) > _TYPE_CAP else ""
        _cen = " · 검정=잣대 중심" + ("(한 겹으로 접힌 값)" if _folds and _token else "") \
            if _merged is not None else ""
        self._shape_title.setText(
            (f"{_who} — 채움=살 · 실선=바깥 윤곽 · 파선=구멍 가장자리 · "
             f"색=type 별 평균({len(_drawn)} type · 원본 {_total}건)"
             + (" · 옅은 띠=±1σ" if self._spread.isChecked() else "")
             if _token else
             f"{_who} — 채널별 값 · 색=type 별 평균({len(_drawn)} type · {_total}건)"
             + (" · 옅은 띠=±1σ" if self._spread.isChecked() else ""))
            + _cen + _more + _forced)

        # 표본도 **원본 feature** 로 그린다 — 잣대는 구멍 여럿을 한 겹으로 접으므로 그림에서
        # 뭉갠다. 원본을 그려야 실제 형상이 보인다.
        for _key in self._selected_samples()[:8]:            # **여기서만** 디스크를 탄다
            _addr = Cluster_Bucket.Address(_key)
            _label, _color = f"{_addr[0][-9:]}·{_addr[1]}", _ax._get_lines.get_next_color()
            if _token:
                _v = _b.Features(_addr, [_src]).get(_src)
                if _v is not None:
                    self._draw_shape(_ax, _v, _label, _color)
            else:
                _v = _b.Measure(_addr, [_draw_as]).get(_draw_as)
                if _v is not None:
                    self._draw_channels(_ax, _v, _label, _color)
        if not _token:
            _ax.set_xlabel("channel", fontsize=7)
            _ax.tick_params(labelsize=7)
            _ax.grid(alpha=0.25)
        if _ax.has_data():
            _ax.legend(fontsize=6, loc="upper right",
                       bbox_to_anchor=(1.25, 1.12) if _token else (1.0, 1.0))
        self._fig.tight_layout()
        self._canvas.draw()

    @classmethod
    def _drawable_as_shape(cls, bucket, domain: str) -> bool:
        """실루엣으로 그릴 수 있는 잣대인가 — **접기가 정한다**.

        [실루엣] 로 고정한 채 scalar 도메인으로 옮기면 그릴 것이 없는데, 빈 화면은 "값이 없다" 로
        읽힌다. 그래서 못 그리면 채널 쪽으로 넘긴다. 판별은 :meth:`_bands_of` 에게 그 잣대의 native
        shape 을 흘려 보고 밴드가 나오는지 묻는다 — 규칙을 두 곳에 적지 않으려는 것이다.
        """
        _g = (bucket.Contract().get("gauges") or {}).get(domain, {})
        _shape = tuple(_g.get("shape") or ())
        if not _shape:
            return False
        return bool(cls._bands_of(tuple(_g.get("folds") or ()), np.ones(_shape)))

    @staticmethod
    def _draw_channels(ax, values: np.ndarray, label: str, color,
                       alpha: float = 1.0, width: float = 2.0,
                       spread: np.ndarray | None = None) -> None:
        """순서 없는 도메인(``FEATURE``) — 채널별 값을 꺾은선 하나로.

        막대가 아니라 선인 이유는 **겹쳐 그려야** 하기 때문이다. 멤버 수십 개를 옅게 얹으면 그
        번짐이 곧 산포라, 별도의 오차막대 없이 "이 type 이 얼마나 퍼졌나" 가 보인다.
        """
        _v = np.asarray(values, np.float64).ravel()
        if not _v.size:
            return
        if spread is not None:
            _s = np.asarray(spread, np.float64).ravel()
            if _s.size == _v.size:               # ±1σ — 띠가 두꺼우면 평균이 대표하지 못한다
                ax.fill_between(np.arange(_v.size), _v - _s, _v + _s,
                                color=color, alpha=0.16 * alpha, linewidth=0)
        ax.plot(np.arange(_v.size), _v, color=color, linewidth=width, alpha=0.95 * alpha,
                marker="o" if _v.size <= 12 else None, markersize=3,
                **({"label": label} if label else {}))
