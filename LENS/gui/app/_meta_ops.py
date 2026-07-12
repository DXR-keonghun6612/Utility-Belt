"""Meta_ops — 보유 ``Pipeline`` 위의 백그라운드 meta 연산(run·전이·삭제) 컨트롤러.

한 워커로 진행바 + 실행 중 ``Meta_view`` 편집 잠금을 공유한다. store 라이프사이클(``Move``/``Delete``)과
``Pipeline.Run`` 을 백그라운드로 돌리고 완료 후 ``Meta_view`` 를 동기화한다 — app 연결층이라 core 는 주입받은
``pipeline`` 으로만 만진다. 완료 슬롯은 **bound method** 로 연결(cross-thread 큐드 — 워커 스레드서 self.wait 금지).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QMessageBox, QProgressBar, QPushButton, QWidget

from gui._worker import Pipeline_worker


class Meta_ops(QObject):
    """run·전이·삭제를 한 워커로 실행 (동시 실행 금지, 진행바·편집잠금 공유).

    Args:
        meta_view: 완료 후 동기화할 본문 뷰 (``set_editable``·``apply_transition``·``apply_removal``·``refresh``).
        progress: 진행 표시 바.
        run_btn: 실행 중 비활성화할 run 버튼.
        parent: ``QMessageBox`` 부모 + ``QObject`` 소유자(메인 스레드 affinity).
    """

    def __init__(self, meta_view, progress: QProgressBar, run_btn: QPushButton,
                 parent: QWidget) -> None:
        super().__init__(parent)
        self._view = meta_view
        self._progress = progress
        self._run_btn = run_btn
        self._parent = parent
        self._thread: QThread | None = None
        self._worker: Pipeline_worker | None = None
        self._txn: tuple[str, list] | None = None     # 진행 중 전이 완료 컨텍스트 (to_state, stems)
        self._rm: list | None = None                  # 진행 중 삭제 완료 컨텍스트 (stems)

    @property
    def busy(self) -> bool:
        """워커가 도는 중이면 True (동시 실행 금지 가드)."""
        return self._thread is not None

    # ── run (보유 Pipeline + 현재 프로필) ───────────────────────────────────────

    def run(self, pipeline, flows: list) -> None:
        """flows 프로필을 pipeline 위에서 실행한다 (→ modified). pipeline 없거나 busy 면 무시."""
        if pipeline is None or self.busy:
            return
        _pipe, _flows = pipeline, flows                # 보유 Pipeline + 편집한 프로필 주입
        self._start(pipeline, lambda _p: _pipe.Run(progress=_p, flows=_flows),
                    self._run_done, "실행 중…")

    def _run_done(self, ok: bool, info: str) -> None:
        if ok:
            self._view.refresh()                       # in-place 갱신된 meta(modified) 반영
        self._end(ok)
        if not ok:
            QMessageBox.critical(self._parent, "run 실패", info)

    # ── 전이·삭제 (항상 백그라운드 — 대량 아니어도 UI 멈춤·꼬임 방지) ─────────────────
    # 완료 컨텍스트는 self 에 둔다 — finished 는 **bound method**(QObject slot)로 연결해야 cross-thread
    # 큐드 연결이 돼 메인 스레드에서 돈다(lambda 는 affinity 없어 direct=워커 스레드 실행 → wait-on-self).

    def transition(self, pipeline, stems: list, to_state: str) -> None:
        """선택 stem 들을 ``to_state`` 로 전이한다 (백그라운드, 진행바; 완료 후 목록 동기화)."""
        if pipeline is None or not stems or self.busy:
            return
        _pipe = pipeline

        def _task(_progress) -> None:
            _n = len(stems)
            for _i, _stem in enumerate(stems, 1):
                _pipe.meta.Move(_stem, to_state)  # payload+사이드카+버킷 (Bucket_Store 소유)
                _progress("이동 중", _i, _n)

        self._txn = (to_state, stems)
        self._start(pipeline, _task, self._transition_done, "이동 중…")

    def _transition_done(self, ok: bool, info: str) -> None:
        _to_state, _stems = self._txn
        if ok:
            self._view.apply_transition(_to_state, _stems)
        self._end(ok)
        if not ok:
            QMessageBox.critical(self._parent, "이동 실패", info)

    def remove(self, pipeline, stems: list) -> None:
        """선택 stem 들을 완전히 삭제한다 (백그라운드, 진행바; 완료 후 목록 정리)."""
        if pipeline is None or not stems or self.busy:
            return
        _pipe = pipeline

        def _task(_progress) -> None:
            _n = len(stems)
            for _i, _stem in enumerate(stems, 1):
                _pipe.meta.Delete(_stem)          # payload+사이드카+버킷 제거 (Bucket_Store 소유)
                _progress("삭제 중", _i, _n)

        self._rm = stems
        self._start(pipeline, _task, self._remove_done, "삭제 중…")

    def _remove_done(self, ok: bool, info: str) -> None:
        if ok:
            self._view.apply_removal(self._rm)
        self._end(ok)
        if not ok:
            QMessageBox.critical(self._parent, "삭제 실패", info)

    # ── 워커 공용 (진행바 + 실행 중 편집 잠금) ──────────────────────────────────

    def _start(self, pipeline, task, on_finished, busy_label: str) -> None:
        """단일 워커로 ``task`` 를 백그라운드 실행한다 — 진행바 + 실행 중 meta 편집 차단(보기는 유지)."""
        self._view.set_editable(False)                 # 실행 중 수정 차단 (stem 클릭·이미지 보기는 유지)
        self._run_btn.setEnabled(False)
        self.set_progress(0, 0, busy_label)
        self._thread = QThread()
        self._worker = Pipeline_worker(pipeline, task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.set_progress)
        self._worker.finished.connect(on_finished)
        self._thread.start()

    def _end(self, ok: bool) -> None:
        """워커 스레드 정리 + UI 복구 (편집 재활성·버튼 복구·진행바 상태)."""
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._run_btn.setEnabled(True)
        self._view.set_editable(True)                  # 편집 잠금 해제
        self.set_progress(0, 0, "완료" if ok else "실패")

    def set_progress(self, done: int, total: int, label: str = "") -> None:
        """진행바를 갱신한다 (``total<=0`` 이면 유휴 표시)."""
        if total <= 0:
            self._progress.setRange(0, 1)
            self._progress.setValue(0)
            self._progress.setFormat(label or "대기")
            return
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        self._progress.setFormat(f"{label} : %v / %m" if label else "%v / %m")
