"""tasker 한 개 탭 — 툴바(프로필 편집·▶ sample·▶ split 처리) + 임베드 sample 편집 뷰.

``Sampler_dialog`` 의 ``QTabWidget`` 한 칸 = tasker 한 개. 탭은 **레시피(cfg)를 보유**하고, ``프로필 편집``
이 그 cfg 를 [`_profile`](_profile.py) 다이얼로그로 편집한다(빌더). ``▶ sample`` 이 보유 cfg 로
``Pipeline.Sample`` 을 백그라운드 빌드하고, ``▶ split 처리`` 가 ``Pipeline.Export_tasker`` 로 train/val/test
를 외부 경로에 실체화한다(빌더 ↔ 실행 분리 — ``run`` 갈래와 동형). 본문은 [`_sample_view`](_sample_view.py)
(group→sample 트리 + crop 미리보기 + class 재배정). 무거운 작업은 워커 스레드 + 상태 라벨 + 실행 중 편집
잠금(``Pipeline_worker``). 이후 **분석 호출 버튼**을 툴바에 더할 자리다.
"""

from __future__ import annotations

from collections import Counter
from typing import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui._worker import Pipeline_worker
from gui.meta_page.sample._profile import Tasker_profile_dialog
from gui.meta_page.sample._sample_view import Sample_view
from gui.widgets import Pop_dialog


def _mislabel_text(res, purity: float = 0.6) -> str:
    """형상 클러스터 결과에서 **오분류 후보**(이동 제안)·유사없음을 텍스트로 정리한다.

    각 HDBSCAN 클러스터의 다수 class 를 정답으로 보고(다수 비율 ≥ ``purity``), 다른 class 인 sample 을
    "원본 → 대상" 이동 제안으로 적는다. noise·혼합(다수 비율 < purity)은 '유사 없음'. 유저가 이 텍스트를
    보고 sample 뷰에서 수동 재배정한다(자동 이동 아님). ``res`` 는 ``analysis.mask.shape.ShapeAnalysis``.
    """
    _clusters, _labels, _stems = res.clusters, res.labels, res.stems
    _major: dict[int, tuple[str, float]] = {}
    for _k in set(_clusters.tolist()):
        if _k == -1:
            continue
        _idx = [_i for _i in range(len(_stems)) if _clusters[_i] == _k]
        _cls, _c = Counter(str(_labels[_i]) for _i in _idx).most_common(1)[0]
        _major[_k] = (_cls, _c / len(_idx))
    _moves: list[tuple[str, str, str, int, float]] = []
    _orphans: list[tuple[str, str, str]] = []
    for _i in range(len(_stems)):
        _k, _cls, _st = int(_clusters[_i]), str(_labels[_i]), _stems[_i]
        if _k == -1:
            _orphans.append((_cls, _st, "noise (유사 클러스터 없음)"))
            continue
        _maj, _frac = _major[_k]
        if _cls == _maj:
            continue
        if _frac >= purity:
            _moves.append((_cls, _st, _maj, _k, _frac))
        else:
            _orphans.append((_cls, _st, f"혼합 cluster {_k:02d} 최다 {_maj} {_frac:.0%}"))
    _lines = [f"오분류 후보 (purity≥{purity:.0%})  이동제안 {len(_moves)} / 유사없음 "
              f"{len(_orphans)} / 전체 {len(_stems)}", "=" * 60,
              "", "[이동 제안]  원본class/stem  ->  대상class   (cluster, 다수비율)"]
    _lines += [f"  {_c}/{_s}  ->  {_m}   (c{_k:02d}, {_f:.0%})"
               for _c, _s, _m, _k, _f in sorted(_moves)] or ["  (없음)"]
    _lines += ["", "[유사 없음]  class/stem   (사유)"]
    _lines += [f"  {_c}/{_s}   ({_w})" for _c, _s, _w in sorted(_orphans)] or ["  (없음)"]
    return "\n".join(_lines)

_DEFAULT_CFG: dict = {"task": "classification", "unit": "object",
                      "ratios": {"train": 0.8, "val": 0.1, "test": 0.1},
                      "salt": "", "processes": []}


class Tasker_tab(QWidget):
    """tasker 한 개 — 레시피 보유 + 빌드/내보내기 툴바 + 임베드 sample 편집 뷰.

    Attributes:
        meta_changed: 이 탭의 class write-back 으로 정본이 바뀌었을 때 emit (상위 forward 용).
    """

    meta_changed = Signal()

    def __init__(self, get_pipeline: Callable[[], object | None], name: str,
                 cfg: dict | None = None, parent=None) -> None:
        """Args:
        get_pipeline: 보유 ``Pipeline`` 을 돌려주는 콜백 (없으면 None).
        name: tasker 이름 (폴더·레지스트리 key = 탭 제목).
        cfg: 초기 레시피 (등록된 taskers.yaml 항목; 없으면 기본값).
        """
        super().__init__(parent)
        self._get_pipeline = get_pipeline
        self._name = name
        self._cfg = dict(cfg) if cfg else dict(_DEFAULT_CFG)
        self._thread: QThread | None = None
        self._worker: Pipeline_worker | None = None
        self._analysis = None                          # 마지막 형상 분석 결과 (ShapeAnalysis)
        self._dialogs: list = []                        # 비모달 결과 dialog 참조 (GC 방지)
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(4, 4, 4, 4)
        _lay.setSpacing(4)

        # ── 툴바 ─────────────────────────────────────────────────────────────
        _bar = QHBoxLayout()
        self._profile_btn = QPushButton("프로필 편집")
        self._profile_btn.setToolTip("이 tasker 의 sample 레시피(task/unit/ratios/salt/processes) 편집")
        self._profile_btn.clicked.connect(self._on_profile)
        self._run_btn = QPushButton("▶ sample")
        self._run_btn.setToolTip("현재 레시피로 tasker 를 (재)빌드 — staged 정본에서 파생 (split 없는 작업 store)")
        self._run_btn.clicked.connect(self._on_run)
        self._export_btn = QPushButton("▶ split 처리")
        self._export_btn.setToolTip("작업 store 를 train/val/test 로 갈라 외부 경로에 실체화 (내보내기)")
        self._export_btn.clicked.connect(self._on_export)
        self._analyze_btn = QPushButton("분석")
        self._analyze_btn.setToolTip("작업 버킷(mask)에 형상 임베딩·클러스터 분석 → 요약·오분류 후보를 텍스트로 표시")
        self._analyze_btn.clicked.connect(self._on_analyze)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #888;")
        _bar.addWidget(self._profile_btn)
        _bar.addWidget(self._run_btn)
        _bar.addWidget(self._export_btn)
        _bar.addWidget(self._analyze_btn)
        _bar.addWidget(self._status, stretch=1)
        _lay.addLayout(_bar)

        # ── 본문: sample 편집 뷰 ─────────────────────────────────────────────
        self._view = Sample_view(self._get_pipeline, self._name)
        self._view.meta_changed.connect(self.meta_changed)
        _lay.addWidget(self._view, stretch=1)

    # ── 프로필 편집 (레시피 빌더) ───────────────────────────────────────────────
    def _on_profile(self) -> None:
        """레시피 빌더를 열어 이 탭의 cfg 를 편집한다 (닫을 때 cfg 회수 — run 이 flows() 회수하는 패턴)."""
        _dlg = Tasker_profile_dialog(self._cfg, self)
        _dlg.exec()
        self._cfg = _dlg.cfg()

    # ── 빌드 (Pipeline.Sample 백그라운드) ──────────────────────────────────────
    def _on_run(self) -> None:
        if self._thread is not None:
            return
        _pipe = self._get_pipeline()
        if _pipe is None or not str(_pipe.root).strip():
            self._status.setText("dataset_root 미설정")
            return
        from core.store.sample.export import TASKS
        _spec = TASKS.get(self._cfg.get("task", ""))
        if _spec is not None and _spec.unit == "object" and not self._cfg.get("processes"):
            self._status.setText("classification 은 crop 체인이 필요합니다 — 프로필에서 process 를 추가하세요"
                                 " (detection/segmentation 은 정본 역참조라 체인 없이도 됨)")
            return
        self._set_busy(True)
        self._status.setText("빌드 중…")

        def _task(_progress) -> None:             # Sample 은 progress 콜백을 안 받는다 (무시)
            _pipe.Sample(self._name, self._cfg)

        # finished 는 bound method 로 연결 (lambda 는 DirectConnection→자기 스레드 wait 크래시).
        self._start_worker(_pipe, _task, self._on_build_done)

    def _on_build_done(self, ok: bool, info: str) -> None:
        self._status.setText("빌드 완료" if ok else f"실패: {info.splitlines()[-1]}")
        self._end_worker()
        if ok:
            self._view.reload()

    # ── 내보내기 (split 처리 — Pipeline.Export_tasker 백그라운드) ────────────────
    def _on_export(self) -> None:
        if self._thread is not None:
            return
        _pipe = self._get_pipeline()
        if _pipe is None:
            self._status.setText("dataset_root 미설정")
            return
        _dest = QFileDialog.getExistingDirectory(self, "split 산출물을 내보낼 위치 선택")
        if not _dest:
            return
        from core.store.sample.export import Formats_for
        _task = self._cfg.get("task", "classification")
        _formats = Formats_for(_task)
        if not _formats:
            self._status.setText(f"task '{_task}' 에 내보내기 format 이 없습니다")
            return
        if len(_formats) > 1:                          # 여러 레이아웃 → 고른다 (기본이 맨 앞)
            _fmt, _ok = QInputDialog.getItem(
                self, "내보내기 format", f"{_task} 레이아웃:", _formats, 0, False)
            if not _ok:
                return
        else:
            _fmt = _formats[0]
        self._set_busy(True)
        self._status.setText(f"split 처리 중… ({_fmt})")
        self._pending_dest = _dest

        def _task_fn(_progress) -> None:
            _pipe.Export_tasker(self._name, _dest, format=_fmt)

        self._start_worker(_pipe, _task_fn, self._on_export_done)

    def _on_export_done(self, ok: bool, info: str) -> None:
        self._status.setText(f"내보냄: {self._pending_dest}/{self._name}"
                             if ok else f"실패: {info.splitlines()[-1]}")
        self._end_worker()

    # ── 형상 분석 (작업 버킷 mask → 텍스트 dialog 2개) ─────────────────────────
    def _on_analyze(self) -> None:
        if self._thread is not None:
            return
        _pipe = self._get_pipeline()
        if _pipe is None:
            self._status.setText("dataset_root 미설정")
            return
        _root = _pipe.Tasker_root(self._name)
        if not _root.exists():
            self._status.setText("먼저 ▶ sample 로 빌드하세요")
            return
        self._set_busy(True)
        self._status.setText("분석 중…")

        def _task(_progress) -> None:
            # 무거운 deps(umap/hdbscan/sklearn)는 지연 import 로 격리. analysis 는 추후 리팩토링 대상.
            from core.process.analysis.mask.shape import analyze
            self._analysis = analyze(_root)

        self._start_worker(_pipe, _task, self._on_analyze_done)

    def _on_analyze_done(self, ok: bool, info: str) -> None:
        self._end_worker()
        if not ok or self._analysis is None:
            self._status.setText(f"분석 실패: {info.splitlines()[-1]}" if info else "분석 실패")
            return
        from core.process.analysis.mask.shape import format_report
        _report = format_report(self._analysis)
        _mis = _mislabel_text(self._analysis)
        _pipe = self._get_pipeline()
        if _pipe is not None:                          # task 폴더({root}/sample/{name})에 리포트 저장
            _dir = _pipe.Tasker_root(self._name).parent
            (_dir / "shape_report.txt").write_text(_report, encoding="utf-8")
            (_dir / "mislabel_candidates.txt").write_text(_mis, encoding="utf-8")
            self._status.setText(f"분석 완료 (저장: {_dir}/shape_report.txt)")
        else:
            self._status.setText("분석 완료")
        self._show_text("형상 임베딩 요약", _report)
        self._show_text("오분류 후보 (수동 재배정 참고)", _mis, dx=40, dy=40)

    def _show_text(self, title: str, text: str, *, dx: int = 0, dy: int = 0) -> None:
        """읽기 전용 텍스트 dialog 를 비모달로 띄운다 (분석 결과 표시 — 유저가 보고 수동 재배정)."""
        _dlg = Pop_dialog(title, size=(560, 520), parent=self)
        _te = QPlainTextEdit()
        _te.setReadOnly(True)
        _te.setPlainText(text)
        _te.setStyleSheet("font-family: monospace;")
        _dlg._set_body(_te)
        _dlg._bottom_bar(on_reject=_dlg.accept)
        _dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        _dlg.finished.connect(lambda _r, d=_dlg: self._dialogs.remove(d) if d in self._dialogs else None)
        if dx or dy:
            _dlg.move(_dlg.x() + dx, _dlg.y() + dy)
        self._dialogs.append(_dlg)
        _dlg.show()

    # ── 워커 수명 (빌드·내보내기 공통) ──────────────────────────────────────────
    def _start_worker(self, pipe, task, on_done) -> None:
        self._thread = QThread()
        self._worker = Pipeline_worker(pipe, task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(on_done)
        self._thread.start()

    def _end_worker(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        """작업 중 툴바·편집 잠금 (데이터 변형 중 편집 끼어들기 방지 — 뷰 보기는 유지)."""
        for _b in (self._profile_btn, self._run_btn, self._export_btn, self._analyze_btn):
            _b.setEnabled(not busy)
        self._view.set_editable(not busy)
