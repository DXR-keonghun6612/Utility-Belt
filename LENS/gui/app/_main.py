"""메인 페이지 — dataset_meta 중심, 보유 ``Pipeline`` 한 개로 구동 (레이아웃·흐름은 gui/README).

Convert·Run·staging(``Move``)·편집 저장·meta 가져오기(``Merge``)·내보내기(``Export``)가 모두 이
하나의 Pipeline 을 거친다. converter/flows 는 통째로 묶지 않고 섹션별로 주입한다
(``set_converter`` / ``Run(flows=…)``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import Pipeline, Pipeline_config
from core.data import store_io
from core.data.meta import ANNOTATION_FILE, Dataset_Meta
from gui.app._meta_ops import Meta_ops
from gui.meta_page.view import Meta_view
from gui.meta_page.convert._dialog import _Converter_dialog
from gui.meta_page.run import Run_dialog
from gui.meta_page.sample import Sampler_dialog
from gui.widgets import Path_row


def _flow_label(flow: dict) -> str:
    """flow config 한 개를 요약 표시할 이름 — ``name`` 우선, 없으면 ``object_type``."""
    return str(flow.get("name") or flow.get("object_type") or "flow")


class Main_page(QWidget):
    """LENS 메인 페이지 — staging dataset_meta 중심, 보유 ``Pipeline`` 한 개로 구동."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pipeline: Pipeline | None = None      # 보유 Pipeline (meta 단일 소스)
        self._flows: list = []                      # flow 프로필 (레시피, 빌더가 소유 UI)
        self._converter_cfg: dict = {}              # converter 레시피 (다이얼로그가 소유 UI)
        self._converter_dlg: _Converter_dialog | None = None   # 비모달 창 (열려 있으면 보유)
        self._flow_dlg: Run_dialog | None = None               # 비모달 창 (열려 있으면 보유)
        self._sampler_dlg: Sampler_dialog | None = None        # 비모달 Sampler 창 (tasker 탭 컨테이너)
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(8, 8, 8, 8)
        _lay.setSpacing(6)

        # 버튼 크기 통일 — 동일 최소폭 + 툴팁/콜백을 한 곳에서 (제각각 방지).
        _BTN_W = 130

        def _btn(text: str, tip: str, slot) -> QPushButton:
            _b = QPushButton(text)
            _b.setToolTip(tip)
            _b.setMinimumWidth(_BTN_W)
            _b.clicked.connect(slot)
            return _b

        # ── convert 한 줄: dataset_root(뷰어) + Converter… ────────────────────
        # 값은 Converter 창에서만 편집한다 — 여기선 현재 root 표시 + ↺(디스크 재로드)뿐.
        _convert = QHBoxLayout()
        self._root_edit = Path_row(
            "dataset_root", placeholder="Converter 창에서 dataset_root 설정",
            mode="dir", refresh=True, read_only=True)
        self._root_edit.committed.connect(self._open_root)
        _convert.addWidget(self._root_edit, stretch=1)
        _convert.addWidget(_btn(
            "Converter…", "raw → 초기 dataset_meta 생성 (부트스트랩)", self._open_converter))
        _lay.addLayout(_convert)

        # ── flow 한 줄: flow_profile · run · 현재 프로필 요약 ──────────────────
        # 프로필 요약은 진행바 위(버튼 줄)에 둔다 — 진행바 아래는 눈에 잘 안 띈다.
        _flow = QHBoxLayout()
        _flow.addWidget(_btn(
            "flow_profile 가져오기", "flow 시퀀스(프로필) 빌더 — 편집 + 저장/불러오기",
            self._open_flow_profile))
        self._run_btn = _btn(
            "▶ run", "현재 프로필을 보유 dataset 위에서 실행 (→ modified)", self._on_run)
        _flow.addWidget(self._run_btn)
        self._profile_label = QLabel()
        self._profile_label.setStyleSheet("color: #888;")
        self._profile_label.setToolTip("현재 보유한 flow 프로필 (flow_profile 가져오기로 설정)")
        _flow.addWidget(self._profile_label, stretch=1)
        _lay.addLayout(_flow)

        # ── 진행바: 자체 줄(가독성) ───────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setFormat("대기")
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        _lay.addWidget(self._progress)
        self._update_profile_label()

        # ── 본문: Meta_view (stem 목록 + 편집기 + id_map/params) ───────────────
        self._meta_view = Meta_view()
        # 백그라운드 meta 연산(run·전이·삭제 + 진행바 + 실행 중 편집잠금)은 Meta_ops 소유.
        self._ops = Meta_ops(self._meta_view, self._progress, self._run_btn, self)
        self._meta_view.transition_requested.connect(
            lambda to_state, stems: self._ops.transition(self._pipeline, stems, to_state))
        self._meta_view.remove_requested.connect(
            lambda stems: self._ops.remove(self._pipeline, stems))
        _lay.addWidget(self._meta_view, stretch=1)

        # ── 하단: meta 가져오기 | annotation 생성 ─────────────────────────────
        _bottom = QHBoxLayout()
        _bottom.addWidget(_btn(
            "meta 가져오기", "다른 dataset_meta 를 골라 상태 보존해 들인다 (빈 host=로드, 충돌은 질의)",
            self._on_import_meta))
        _bottom.addWidget(_btn(
            "전부 비우기", "보유 세션(dataset_root·converter·flows·meta 뷰)을 모두 비운다 (디스크는 보존)",
            self._on_clear_all))
        _bottom.addWidget(_btn(
            "Sampler…", "정본(staged) → 파생 학습셋(tasker) 빌드 + tasker별 sample 뷰어",
            self._open_sampler))
        _bottom.addStretch()
        _bottom.addWidget(_btn(
            "annotation 생성", "commit 된 프레임만 뭉친 clean dataset(annotation) 생성·내보내기",
            self._export_annotation))
        _lay.addLayout(_bottom)

    # ── Pipeline 보유 (dataset_root 기준) ──────────────────────────────────────

    def _open_root(self) -> None:
        """dataset_root 로 Pipeline 을 (재)생성하고 본문에 연결한다 (빈 root 면 해제)."""
        _root = self._root_edit.text().strip()
        if not _root:
            self._pipeline = None
            self._meta_view.set_pipeline(None)
            return
        _conv = self._converter_cfg.get("converter", {})
        self._pipeline = Pipeline(Pipeline_config(
            dataset_root=_root, converter=_conv, flows=self._flows))
        self._meta_view.set_pipeline(self._pipeline)

    def _set_root(self, root: str) -> None:
        """Converter 창이 확정한 dataset_root 를 뷰어에 반영하고 Pipeline 을 (재)생성한다."""
        self._root_edit.setText(root)
        self._open_root()

    # ── converter (레시피, 비모달 창) ───────────────────────────────────────────

    def _open_converter(self) -> None:
        """Converter 창을 비모달로 띄운다 (Convert 는 보유 Pipeline 에서 돈다 — ``get_pipeline`` 주입)."""
        if self._converter_dlg is not None:                # 이미 열려 있으면 앞으로
            self._converter_dlg.raise_()
            self._converter_dlg.activateWindow()
            return
        _dlg = _Converter_dialog(
            self._converter_cfg, root=self.dataset_root(), set_root=self._set_root,
            get_pipeline=lambda: self._pipeline, parent=self)
        _dlg.panel.convert_done.connect(self._meta_view.refresh)   # 보유 Pipeline in-place 갱신 반영
        _dlg.panel.convert_done.connect(_dlg.accept)       # 변환 완료 → 창 자동 닫기
        _dlg.finished.connect(self._on_converter_closed)
        self._converter_dlg = _dlg
        _dlg.show()

    def _on_converter_closed(self, _result: int) -> None:
        """Converter 창이 닫히면 converter 레시피를 회수하고 참조를 비운다."""
        if self._converter_dlg is not None:
            self._converter_cfg = self._converter_dlg.export_config()
            self._converter_dlg.deleteLater()
            self._converter_dlg = None

    # ── flow 프로필 (레시피, 비모달 창) ─────────────────────────────────────────

    def _open_flow_profile(self) -> None:
        """flow 빌더 창을 비모달로 띄운다 — 메인 창과 독립적으로 움직인다.

        창이 닫힐 때 현재 프로필을 회수해 보유한다 (``_on_flow_closed``).
        """
        if self._flow_dlg is not None:                     # 이미 열려 있으면 앞으로
            self._flow_dlg.raise_()
            self._flow_dlg.activateWindow()
            return
        _dlg = Run_dialog(self._flows, parent=self)
        _dlg.finished.connect(self._on_flow_closed)
        self._flow_dlg = _dlg
        _dlg.show()

    def _on_flow_closed(self, _result: int) -> None:
        """flow 빌더 창이 닫히면 현재 프로필을 회수하고 참조를 비운다."""
        if self._flow_dlg is not None:
            self._flows = self._flow_dlg.flows()
            self._flow_dlg.deleteLater()
            self._flow_dlg = None
            self._update_profile_label()

    def _update_profile_label(self) -> None:
        """현재 보유 flow 프로필을 요약 라벨에 반영한다 (flow_profile 가져오기 후 호출)."""
        if not self._flows:
            self._profile_label.setText("현재 프로필: 없음")
            return
        _names = " → ".join(_flow_label(_f) for _f in self._flows)
        self._profile_label.setText(f"현재 프로필: {len(self._flows)} flow — {_names}")

    # ── sampler (파생 tasker 탭 창, 비모달) ────────────────────────────────────

    def _open_sampler(self) -> None:
        """Sampler 창(tasker 마다 탭 = 툴바 + sample 편집 뷰)을 비모달로 띄운다 (보유 Pipeline 위에서)."""
        if self._sampler_dlg is not None:                  # 이미 열려 있으면 앞으로
            self._sampler_dlg.raise_()
            self._sampler_dlg.activateWindow()
            return
        _dlg = Sampler_dialog(get_pipeline=lambda: self._pipeline, parent=self)
        _dlg.meta_changed.connect(self._meta_view.refresh)  # class write-back → meta 뷰 갱신
        _dlg.finished.connect(self._on_sampler_closed)
        self._sampler_dlg = _dlg
        _dlg.show()

    def _on_sampler_closed(self, _result: int) -> None:
        if self._sampler_dlg is not None:
            self._sampler_dlg.deleteLater()
            self._sampler_dlg = None

    # ── run (보유 Pipeline + 현재 프로필; 워커·전이·삭제는 Meta_ops 소유) ──────────

    def _on_run(self) -> None:
        """현재 프로필을 보유 Pipeline 위에서 실행한다 (검증 후 Meta_ops 위임)."""
        if self._ops.busy:
            return
        if self._pipeline is None:
            QMessageBox.information(self, "run", "dataset_root 를 먼저 여세요.")
            return
        if not self._flows:
            QMessageBox.information(
                self, "run", "flow 프로필이 비어 있습니다 (flow_profile 가져오기).")
            return
        self._ops.run(self._pipeline, self._flows)

    def _export_annotation(self) -> None:
        """staged 프레임을 뭉친 annotation 을 dataset root 에 생성한다 (store ``Gather`` 직접 호출).

        데이터 라이프사이클은 ``store_io`` 자유함수가 소유하므로 여긴 ``store_io.Gather`` 를 직접 부른다 —
        대상 범주(staged)와 파일명(``ANNOTATION_FILE``)만 정하고 경로 안내.
        """
        if self._pipeline is None:
            QMessageBox.information(self, "annotation 생성", "먼저 dataset_root 를 여세요.")
            return
        _path = store_io.Gather(self._pipeline.meta, ["staged"], ANNOTATION_FILE)
        QMessageBox.information(self, "annotation 생성", f"생성했습니다:\n{_path}")

    # ── 외부 meta 가져오기 (다른 dataset_meta 를 상태 보존해 들임) ─────────────────

    def _on_import_meta(self) -> None:
        """dataset_meta 폴더를 골라 상태 보존해 들인다.

        ``store_io.Restore`` 는 디렉터리(dataset root)를 받아 사이드카(``.meta/*.json``)를 복원한다 —
        폴더를 고른다. host 없음 -> 그 폴더를 그대로 연다(Pipeline 이 로드). host 있음 -> 충돌 질의 후
        현재 root 로 복사 병합(``Merge``). 어느 쪽이든 meta 는 in-place 갱신(뷰 stale 방지).
        """
        _dir = QFileDialog.getExistingDirectory(self, "가져올 dataset_meta 폴더 선택")
        if not _dir:
            return
        _other = store_io.Restore(Dataset_Meta, _dir)        # 폴더 복원 — root = 그 폴더 (Restore 계약)
        _n = sum(len(_other.Bucket(_s)) for _s in _other.STATES)
        if _n == 0:
            QMessageBox.information(self, "meta 가져오기", "그 폴더에서 가져올 프레임을 찾지 못했습니다.")
            return
        if self._pipeline is None:                        # host 없음 → 그 폴더를 그대로 연다
            self._set_root(_other.root)                   # Pipeline 이 그 폴더의 meta 를 로드
            self._meta_view.refresh()
            return
        _conf = self._pipeline.meta.Conflicts(_other)
        _mode = store_io.SKIP
        if _conf:
            _ans = self._ask_import_conflict(_conf)
            if _ans is None:                              # 취소
                return
            _mode = _ans
        store_io.Merge(self._pipeline.meta, _other, mode=_mode)
        self._meta_view.refresh()
        _note = ("" if _mode == store_io.SKIP
                 else f" (충돌 {len(_conf)}개는 {_mode} — '{Dataset_Meta.DEFAULT_CATEGORY}' 로 되돌림)")
        QMessageBox.information(
            self, "meta 가져오기", f"{_n}개 프레임을 가져왔습니다.{_note}")

    def _ask_import_conflict(self, conf: list[str]) -> str | None:
        """충돌 stem 목록을 보여주고 병합 mode 를 묻는다 (취소면 None).

        셋을 명시적으로 가른다 — 예전엔 "건너뛰기"를 눌러도 범주가 같으면 내부 병합이 일어났다.
        """
        _line = (f"중복 stem {len(conf)}개: " + ", ".join(conf[:8])
                 + (" …" if len(conf) > 8 else ""))
        _box = QMessageBox(self)
        _box.setWindowTitle("meta 가져오기 — 충돌")
        _box.setText(
            _line
            + "\n\n건너뛰기 = host 기존 유지 (상태 보존)"
            + "\n덮어쓰기 = other 것으로 통째 교체"
            + "\n병합 = host 에 없는 객체·값만 들임"
            + f"\n\n덮어쓰기·병합은 내용이 바뀌므로 해당 stem 이 '{Dataset_Meta.DEFAULT_CATEGORY}' 로 되돌아갑니다.")
        _skip  = _box.addButton("건너뛰기", QMessageBox.RejectRole)
        _ow    = _box.addButton("덮어쓰기", QMessageBox.AcceptRole)
        _merge = _box.addButton("병합", QMessageBox.ApplyRole)
        _cancel = _box.addButton("취소", QMessageBox.DestructiveRole)
        _box.exec()
        _clicked = _box.clickedButton()
        if _clicked is _cancel:
            return None
        return {_skip: store_io.SKIP, _ow: store_io.OVERWRITE, _merge: store_io.MERGE}[_clicked]

    def _on_clear_all(self) -> None:
        """보유 세션(root·converter·flows·Pipeline·뷰·창)을 전부 비운다 — 디스크는 건드리지 않는다."""
        _ans = QMessageBox.question(
            self, "전부 비우기",
            "보유 세션(dataset_root·converter·flows·meta 뷰)을 비웁니다.\n"
            "디스크의 데이터 파일은 그대로 보존됩니다. 계속할까요?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if _ans != QMessageBox.Yes:
            return
        if self._converter_dlg is not None:               # 열린 창도 함께 닫기 (finished→참조 정리)
            self._converter_dlg.close()
        if self._flow_dlg is not None:
            self._flow_dlg.close()
        if self._sampler_dlg is not None:
            self._sampler_dlg.close()
        for _v in list(self._sample_viewers):             # 열린 sample 뷰어 (WA_DeleteOnClose)
            _v.close()
        self._pipeline = None
        self._converter_cfg = {}
        self._flows = []
        self._root_edit.setText("")
        self._meta_view.set_pipeline(None)
        self._update_profile_label()
        self._ops.set_progress(0, 0, "대기")

    # ── Public API ────────────────────────────────────────────────────────────

    def dataset_root(self) -> str:
        """현재 입력된 dataset_root 경로 문자열을 반환한다."""
        return self._root_edit.text().strip()

    def meta(self):
        """현재 보유 ``Dataset_Meta`` (Pipeline 없으면 None)를 반환한다."""
        return self._pipeline.meta if self._pipeline is not None else None
