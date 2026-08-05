"""Split 창 — 검수 끝난(staged) 정본을 비율대로 갈라 폴더별로 내보낸다.

`Sampler`(파생 tasker 빌드) 자리를 대신한다. 중간 store 를 짓지 않고 **정본 → 산출 폴더** 한 걸음이라,
창이 하는 일은 인자를 모으는 것뿐이다: 어디로 · 어떤 몫으로 · 무엇을 기준으로.

**실행은 여기서 안 한다.** 수만 프레임의 이미지를 복사하는 일이라 진행바·편집잠금을 든 상위
(app `Meta_ops`)가 워커로 돌린다 — 전이·삭제·id_map 적용과 같은 길이다. 그래서 이 창은 모달이고,
[실행]은 그저 **인자를 확정**한다(`result_spec`).

## 몫은 이름·개수가 자유다

`train`/`val`/`test` 에 매이지 않는다 — 이름이 곧 폴더 이름이라 2분할·4분할·다른 어휘가 다 된다.
비율은 합을 안 맞춰도 되고(정규화한다), 규칙은 [`core/split.py`](../../../core/split.py) 가 소유한다.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import Pair_list_editor, Path_row, Pop_dialog

#: 기본 몫 — 흔한 관례 하나를 채워 두고, 이름·개수는 사용자가 고친다.
_DEFAULT_RATIOS = [("train", "0.8"), ("val", "0.1"), ("test", "0.1")]

#: 지금 낼 수 있는 것은 하나뿐 — **instance segmentation × coco**. 고를 것이 없으므로 화면에도
#: 칸을 안 둔다(detection 은 이 부분집합이라 걷었다 — bbox 는 mask 에서 나온다).
_TASK = "segmentation"


class Split_dialog(Pop_dialog):
    """분할 인자 입력 — 대상 폴더 · 몫 비율 · salt · 공평 배분 · task.

    ``exec()`` 가 참이면 :meth:`result_spec` 이 상위로 넘길 인자다.
    """

    def __init__(self, staged: int, parent=None) -> None:
        """Args:
        staged: 지금 staged 항목 수 — 나눌 게 있는지 눌러 보기 전에 보이게.
        """
        super().__init__("Split — staged 를 비율대로 나눠 내보내기", size=(520, 520), parent=parent)
        self._staged = staged
        self._build()

    def _build(self) -> None:
        _w = QWidget()
        _l = QVBoxLayout(_w)
        _l.setContentsMargins(0, 0, 0, 0)

        _head = QLabel(f"검수 완료(staged) {self._staged} 개를 나눈다. 정본은 안 바뀐다 — 복사만 한다.")
        _head.setWordWrap(True)
        _l.addWidget(_head)

        self._dest = Path_row("대상 폴더", placeholder="/path/to/output", mode="dir")
        _l.addWidget(self._dest)

        self._ratios = Pair_list_editor(
            "몫 (이름 = 폴더 이름 · 비율)",
            tip="이름이 곧 폴더 이름이다. 비율 합은 안 맞춰도 된다 — 합=1 로 정규화한다.")
        self._ratios.set_pairs(_DEFAULT_RATIOS)
        _l.addWidget(self._ratios, stretch=1)

        _form = QFormLayout()
        self._salt = QLineEdit()
        self._salt.setPlaceholderText("비우면 고정 (같은 데이터 → 늘 같은 분할)")
        self._salt.setToolTip("해시 salt — 같은 데이터를 다르게 나누되 재현 가능하게 한다")
        _form.addRow("salt", self._salt)

        self._strat = QCheckBox("class별 공평 배분")
        self._strat.setToolTip(
            "class 마다 따로 나눠 각 몫에 비율대로 들어가게 한다 (희귀 class 가 한 몫에 몰리는 걸 막는다).\n"
            "기준은 **0번 객체**의 class 다 (순회 축이 그것이라 프레임의 대표가 곧 0번).")
        self._strat.setChecked(True)
        _form.addRow("", self._strat)

        self._min = QSpinBox()
        self._min.setRange(0, 100000)
        self._min.setSpecialValueText("끄기")
        self._min.setToolTip(
            "이만큼 안 나온 class 의 **주석을 안 적는다** (0 = 전부 적는다).\n"
            "표본이 몇 건뿐인 class 는 학습에 쓸 수 없는데 val/test 로 새면 지표만 흔든다.\n"
            "**id_map 에서는 안 뺀다** — 표는 부품 목록이라 번호가 밀리면 이미 학습한 체크포인트와 "
            "어긋난다. 빠지는 것은 주석뿐이고, 그 객체가 없는 셈이 되지 사진이 없던 일이 되진 않는다.\n"
            "세는 단위는 **전 몫 합계**다 — 몫마다 세면 같은 class 가 train 에만 남는다")
        _form.addRow("기록 최소 수량", self._min)

        _l.addLayout(_form)

        self._set_body(_w)
        _box = self._bottom_bar(buttons=QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel,
                                on_reject=self.reject)
        _box.button(QDialogButtonBox.StandardButton.Ok).setText("실행")
        _box.accepted.connect(self._on_ok)

    # ── 결과 ──────────────────────────────────────────────────────────────────
    def result_spec(self) -> tuple[str, dict[str, float], str, bool, int, str]:
        """``(대상 폴더, {몫 이름: 비율}, salt, 공평 배분, 기록 최소 수량, task)``."""
        return (self._dest.text().strip(), self._parse_ratios(),
                self._salt.text().strip(), self._strat.isChecked(),
                int(self._min.value()), _TASK)

    def _parse_ratios(self) -> dict[str, float]:
        """행 → ``{이름: 비율}``. 숫자가 아니면 **버리지 않고 터진다**(:meth:`_on_ok` 가 받는다).

        같은 이름이 두 번 나오면 뒤가 이긴다 — 폴더 이름이라 유일해야 하고, 그건 :meth:`_on_ok` 가 막는다.
        """
        return {_k: float(_v) for _k, _v in self._ratios.pairs()}

    def _on_ok(self) -> None:
        """인자를 검사하고 닫는다 — **실행 전에** 막을 수 있는 건 여기서 다 막는다."""
        _names = [_k for _k, _ in self._ratios.pairs()]
        if not self._dest.text().strip():
            return self._warn("대상 폴더를 고르세요.")
        if not _names:
            return self._warn("몫을 하나 이상 지정하세요.")
        if len(set(_names)) != len(_names):
            return self._warn("몫 이름이 겹칩니다 — 폴더 이름이라 유일해야 합니다.")
        try:
            _ratios = self._parse_ratios()
        except ValueError:
            return self._warn("비율은 숫자여야 합니다.")
        if any(_v < 0 for _v in _ratios.values()):
            return self._warn("비율에 음수는 쓸 수 없습니다.")
        if sum(_ratios.values()) <= 0:
            return self._warn("비율이 전부 0 입니다 — 나눌 기준이 없습니다.")
        self.accept()

    def _warn(self, msg: str) -> None:
        QMessageBox.warning(self, "Split", msg)
