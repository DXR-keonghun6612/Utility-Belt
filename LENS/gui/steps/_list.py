"""Step_list — ``Process_step`` 동적 목록 컨테이너 (추가/삭제/이동·순서 + min-count 정책 캡슐화)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from gui.widgets import drop, reorder

from ._step import Process_step


class Step_list(QWidget):
    """``Process_step`` 체인을 추가/삭제/순서변경하는 컨테이너 위젯.

    Flow_card 의 per-unit·finalize 체인, Sampler 의 실체화 체인이 공유하던 step 관리
    (add/remove/move + reorder)를 한곳에 모은다. ``min_count`` 미만으로는 지우지 않으며
    (per-unit·실체화 체인은 1, finalize 는 0), 하단 "추가" 버튼을 자체 소유한다. 자신이
    ``QWidget`` 이라 ``setEnabled(False)`` 한 번으로 전체(스텝+추가버튼)를 잠근다(lock 캐스케이드).

    Attributes:
        changed: step 추가/삭제/이동/내부 편집 시 emit.
    """

    changed = Signal()

    def __init__(self, *, min_count: int = 1, show_outputs: bool = True,
                 outputs_block: bool = False, add_label: str = "+ process 추가",
                 parent=None) -> None:
        """컨테이너를 구성한다 (``min_count`` 개로 채워 시작).

        Args:
            min_count: 유지할 최소 step 수 (이 밑으로는 삭제 거부). 신규 시작 시에도 이만큼 채운다.
            show_outputs: 각 step 이 우측 배선/저장 편집기를 갖는지 (``Process_step.show_outputs``).
            outputs_block: 각 step 의 outputs 가 finalize/params 레벨인지 (``Process_step.outputs_block``).
            add_label: 하단 추가 버튼 라벨.
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._min = min_count
        self._show_outputs = show_outputs
        self._outputs_block = outputs_block
        self._steps: list[Process_step] = []

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)
        self._steps_layout = QVBoxLayout()
        self._steps_layout.setSpacing(4)
        _lay.addLayout(self._steps_layout)
        self._add_btn = QPushButton(add_label)
        self._add_btn.clicked.connect(lambda: self.add())
        _lay.addWidget(self._add_btn)

        self._fill_to_min()

    # ── step 관리 ──────────────────────────────────────────────────────────────

    def add(self, key: str | None = None) -> Process_step:
        """process step 하나를 체인 끝에 추가한다 (시그널 연결 + ``changed`` emit)."""
        _step = Process_step(key, show_outputs=self._show_outputs,
                             outputs_block=self._outputs_block)
        _step.changed.connect(self.changed)
        _step.remove_requested.connect(self._remove)
        _step.move_requested.connect(self._move)
        self._steps.append(_step)
        reorder(self._steps_layout, self._steps)
        self.changed.emit()
        return _step

    def _remove(self, step: Process_step) -> None:
        if len(self._steps) <= self._min:   # min-count 미만으로는 안 줄인다
            return
        self._steps.remove(step)
        drop(step)
        reorder(self._steps_layout, self._steps)
        self.changed.emit()

    def _move(self, step: Process_step, direction: int) -> None:
        _i = self._steps.index(step)
        _j = _i + direction
        if 0 <= _j < len(self._steps):
            self._steps[_i], self._steps[_j] = self._steps[_j], self._steps[_i]
            reorder(self._steps_layout, self._steps)
            self.changed.emit()

    def _fill_to_min(self) -> None:
        while len(self._steps) < self._min:
            self.add()

    def clear(self) -> None:
        """모든 step 을 비운다 (재로드 공용 — ``changed`` 는 emit하지 않음)."""
        for _s in list(self._steps):
            self._steps.remove(_s)
            drop(_s)

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def steps(self) -> list[Process_step]:
        """현재 step 목록 (읽기용 복사본)."""
        return list(self._steps)

    def to_config(self) -> list[dict]:
        """모든 step 을 process config dict 리스트로 직렬화한다."""
        return [_s.to_config() for _s in self._steps]

    def load(self, metas) -> None:
        """process config 리스트로 체인을 복원한다 (``min_count`` 보장).

        Args:
            metas: ``{"object_type": ..., ...}`` dict(또는 타입 문자열) 목록.
        """
        self.clear()
        for _pmeta in metas or []:
            _key = _pmeta.get("object_type", "") if isinstance(_pmeta, dict) else str(_pmeta)
            _step = self.add(_key)
            if isinstance(_pmeta, dict):
                _step.load(_key, {_k: _v for _k, _v in _pmeta.items() if _k != "object_type"})
        self._fill_to_min()
