"""메인 본문 — stem 목록 + 임베드 편집기 + id_map/params (``Pipeline`` 구동). 설계는 README."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.data import store_io
from gui.meta_page.view._idmap import Idmap_panel
from gui.meta_page.view._params import Params_panel
from gui.meta_page.view._stem_list import Stem_list
from gui.meta_page.verify import Stem_editor, Stem_edit_dialog


class Meta_view(QWidget):
    """staging 본문 — stem 목록 + 임베드 편집기 + id_map/params (``Pipeline`` 구동).

    Attributes:
        meta_changed: id_map 등 meta 내용이 편집돼 영속됐을 때 emit (상위 알림용).
        transition_requested: 대량 stem 전이 요청 ``(to_state, [stem…])`` — 상위가 백그라운드로 실행.
        remove_requested: 대량 stem 삭제 요청 ``[stem…]`` — 상위가 백그라운드로 실행.
    """

    meta_changed         = Signal()
    transition_requested = Signal(str, list)
    remove_requested     = Signal(list)

    def __init__(self, pipeline=None, parent=None) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._editable = True                          # 편집 잠금 (백그라운드 작업 중엔 보기만)
        self._editor: Stem_editor | None = None
        # 비모달 팝아웃 다이얼로그 참조 — GC 로 사라지지 않게 보관한다.
        self._dialogs: list[Stem_edit_dialog] = []
        self._build()
        # Tab 을 가로채 stem 목록 ↔ object 트리 사이로만 포커스를 토글한다 (그 둘 중
        # 하나에 포커스가 있을 때만 — 그 외 위젯은 기본 Tab 순회를 그대로 둔다).
        QApplication.instance().installEventFilter(self)

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)

        # ── 좌: stem 목록 ────────────────────────────────────────────────────
        self._stem_list = Stem_list()
        self._stem_list.selected.connect(self._on_select)
        self._stem_list.to_state_requested.connect(self._move_many)
        self._stem_list.delete_requested.connect(self._delete_many)
        self._stem_list.popout_requested.connect(self._popout)

        # ── 가운데: 편집기 자리 (선택 stem 으로 채움) ─────────────────────────
        self._holder = QWidget()
        self._holder_lay = QVBoxLayout(self._holder)
        self._holder_lay.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel("stem 을 선택하세요")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._holder_lay.addWidget(self._placeholder)

        # ── 우: id_map | params ──────────────────────────────────────────────
        self._idmap = Idmap_panel()
        self._idmap.changed.connect(self._on_meta_edited)
        self._params = Params_panel()
        _side = QSplitter(Qt.Orientation.Vertical)
        _side.addWidget(self._idmap)
        _side.addWidget(self._params)
        _side.setSizes([200, 300])

        _split = QSplitter(Qt.Orientation.Horizontal)
        _split.addWidget(self._stem_list)
        _split.addWidget(self._holder)
        _split.addWidget(_side)
        _split.setStretchFactor(1, 1)
        _split.setSizes([250, 700, 280])
        _lay.addWidget(_split, stretch=1)

    # ── Public API ────────────────────────────────────────────────────────────
    def set_pipeline(self, pipeline) -> None:
        """구동 ``Pipeline`` 을 갈아끼우고 본문을 갱신한다 (meta 정체성이 바뀌므로 편집기 폐기)."""
        self._pipeline = pipeline
        self._drop_editor()
        self.refresh()

    def set_editable(self, editable: bool) -> None:
        """편집 잠금을 토글한다 — 잠그면 보기(목록 클릭·줌·팝아웃)는 유지하고 수정만 막는다.

        상위(``Main_page``)가 백그라운드 워커(전이·Convert·Run) 실행 중 호출한다. 데이터가 워커에서
        변형되는 동안 편집(값 수정·저장·전이/삭제·id_map)이 끼어들지 못하게 막되, stem 을 계속
        보고 검토할 수 있게 한다 (과거처럼 뷰 전체를 얼리지 않는다).
        """
        self._editable = editable
        self._stem_list.set_editable(editable)
        self._idmap.set_editable(editable)
        if self._editor is not None:
            self._editor.set_editable(editable)
        for _dlg in self._dialogs:
            _dlg.set_editable(editable)

    def refresh(self, keep: str | None = None) -> None:
        """현재 ``pipeline.meta`` 로 목록·id_map·params 를 다시 채운다.

        Args:
            keep: 갱신 후 선택을 유지할 stem (None 이면 편집 중이던 stem 유지 시도).
        """
        _meta = self._meta()
        if _meta is None:
            self.clear()
            return
        if keep is None:
            keep = self._editor._stem if self._editor is not None else ""
        self._idmap.load({})   # TODO(sample): id_map 은 sample 소유 — sample 복구 후 연결
        self._params.load(_meta.params)
        self._stem_list.load(_meta, keep=keep)   # → selected 시그널이 본문을 맞춘다

    def clear(self) -> None:
        """본문을 비운다."""
        self._idmap.clear()
        self._params.clear()
        self._stem_list.clear()

    # ── Tab: stem 목록 ↔ object 트리 토글 ──────────────────────────────────────
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """Tab/Shift+Tab 을 가로채 목록↔트리 사이로만 포커스를 토글한다 (둘 중 하나가 포커스일 때만)."""
        if (event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                and self._toggle_pair_focus()):
            return True
        return super().eventFilter(obj, event)

    def _toggle_pair_focus(self) -> bool:
        """포커스가 stem 목록/object 트리 중 하나에 있으면 반대쪽으로 옮긴다 (옮겼으면 True)."""
        if self._editor is None or not self._editor.isVisible():
            return False
        if self._stem_list.list_has_focus():
            self._editor.focus_objects()
            return True
        if self._editor.objects_have_focus():
            self._stem_list.focus_list()
            return True
        return False

    # ── 내부 ────────────────────────────────────────────────────────────────
    def _meta(self):
        return self._pipeline.meta if self._pipeline is not None else None

    def _on_select(self, stem: str) -> None:
        """목록 선택이 바뀌면 그 stem 을 편집기에 띄운다 (없으면 placeholder)."""
        _meta = self._meta()
        if not stem or _meta is None or not _meta.Has(stem):
            self._show_placeholder()
            return
        if self._editor is None:
            self._editor = Stem_editor(_meta, stem)
            self._editor.saved.connect(self._on_editor_saved)
            self._editor.set_editable(self._editable)   # 현재 잠금 상태 반영 (작업 중 새로 뜬 편집기)
            self._holder_lay.addWidget(self._editor, stretch=1)
        else:
            self._editor.load_stem(stem)
        self._placeholder.setVisible(False)
        self._editor.setVisible(True)

    def _show_placeholder(self) -> None:
        if self._editor is not None:
            self._editor.setVisible(False)
        self._placeholder.setVisible(True)

    def _drop_editor(self) -> None:
        """임베드 편집기를 폐기한다 (pipeline/meta 정체성이 바뀔 때)."""
        if self._editor is not None:
            self._holder_lay.removeWidget(self._editor)
            self._editor.deleteLater()
            self._editor = None

    def _move_many(self, to_state: str, stems: list) -> None:
        """대량 전이 요청을 상위로 올린다 — 실제 이동은 백그라운드(UI 멈춤·상태 꼬임 방지).

        대량 이동은 payload 파일 이동이라 느려 UI 가 "응답 없음"으로 보였다. 상위(`Main_page`)가 워커로
        돌리며 진행바에 표시하고 그동안 편집을 차단한다. 완료 후 `apply_transition` 으로 목록을 동기화.
        """
        if self._pipeline is None or not stems:
            return
        self.transition_requested.emit(to_state, stems)

    def _delete_many(self, stems: list) -> None:
        """대량 삭제 요청을 상위로 올린다 — 관련 팝아웃만 먼저 닫고(빠름) 실제 삭제는 백그라운드."""
        if self._pipeline is None or not stems:
            return
        for _dlg in list(self._dialogs):                 # 그 stem 팝아웃 창 닫기 (즉시)
            if _dlg._stem in stems:
                _dlg.close()
        self.remove_requested.emit(stems)

    def apply_transition(self, to_state: str, stems: list) -> None:
        """백그라운드 전이 완료 후 목록·편집기·팝아웃을 **한 번의 refresh** 로 재동기화한다.

        stem 마다 증분 갱신(``update_state``)은 리스트 전체 재스캔 + `_renumber`(전 항목 재기록)라 O(n²)
        → 2만 건이면 폭발한다(파일 이동보다 이게 병목이었음). 통째로 다시 그리면 O(n)(19k도 <1s). 편집기는
        refresh 가 선택 유지로 재로드하고, 팝아웃(소수)만 따로 갱신한다.
        """
        self.refresh()
        for _dlg in list(self._dialogs):
            _dlg.reload()

    def apply_removal(self, stems: list) -> None:
        """백그라운드 삭제 완료 후 목록을 **한 번의 refresh** 로 재동기화한다 (팝아웃은 요청 시 이미 닫음)."""
        self.refresh()

    def _on_editor_saved(self, stem: str) -> None:
        """편집 저장 반영 — 그 stem 사이드카만 기록 + 그 stem 만 재동기화 (목록 전체 재로드 안 함)."""
        if self._pipeline is not None:
            store_io.Save_item(self._pipeline.meta, stem)  # 그 stem 사이드카 하나만 (즉시)
        if self._editor is not None and self._editor._stem == stem:
            self._editor.reload()               # 그 stem 하나 (압축 obj_id/segment 동기화)
        self._reload_popouts(stem)
        self._stem_list.focus_list()            # 저장 후 목록에 포커스 → 화살표로 다음 stem
        self.meta_changed.emit()

    def _on_meta_edited(self) -> None:
        """id_map 편집 반영 — top 메타만 즉시 영속화하고 알린다."""
        if self._pipeline is not None:
            store_io.Save_top(self._pipeline.meta)
        self.meta_changed.emit()

    def _popout(self, stem: str) -> None:
        """선택 stem 을 별도 창으로 띄운다 (비모달, 비교/병행 검수)."""
        _meta = self._meta()
        if _meta is None or not _meta.Has(stem):
            return
        _dlg = Stem_edit_dialog(_meta, stem, self)
        _dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        _dlg.set_editable(self._editable)               # 작업 중 팝아웃도 보기 전용으로
        _dlg.saved.connect(self._on_editor_saved)
        _dlg.finished.connect(lambda _result, d=_dlg: self._forget_dialog(d))
        self._dialogs.append(_dlg)
        _dlg.show()

    def _reload_popouts(self, stem: str) -> None:
        """같은 stem 을 보는 팝아웃 창을 meta 기준으로 다시 읽힌다."""
        for _dlg in list(self._dialogs):
            if _dlg._stem == stem:
                _dlg.reload()

    def _forget_dialog(self, dlg: Stem_edit_dialog) -> None:
        if dlg in self._dialogs:
            self._dialogs.remove(dlg)
