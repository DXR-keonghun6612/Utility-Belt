"""stem 팝아웃 편집 다이얼로그 — ``Stem_editor`` 를 그대로 띄우는 얇은 wrapper (저장/닫기만)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialogButtonBox

_SAVE = QDialogButtonBox.StandardButton.Save

from core.data.meta import Dataset_Meta
from gui.meta_page.edit._editor import Stem_editor
from gui.widgets import Pop_dialog


class Stem_edit_dialog(Pop_dialog):
    """stem 한 장을 팝아웃해 편집하는 비모달 다이얼로그 (``Stem_editor`` wrapper).

    Attributes:
        saved: 저장이 ``meta`` 에 반영됐을 때 저장된 stem 이름과 함께 emit.
    """

    saved = Signal(str)

    def __init__(self, meta: Dataset_Meta, stem: str, parent=None) -> None:
        super().__init__(f"검수 / 편집 — {stem}", size=(1000, 640), parent=parent)
        # 비모달 — 띄운 뒤에도 메인 창·다른 팝아웃을 독립적으로 다룰 수 있게 한다.
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)

        self.editor = Stem_editor(meta, stem)
        self.editor.saved.connect(self._on_saved)

        self._set_body(self.editor)
        self._buttons = self._bottom_bar(
            buttons=QDialogButtonBox.Save | QDialogButtonBox.Close,
            on_accept=self.editor.save, on_reject=self.reject)

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 토글 — 편집기를 보기 전용으로 두고 저장 버튼을 막는다 (백그라운드 작업 중)."""
        self.editor.set_editable(editable)
        self._buttons.button(_SAVE).setEnabled(editable)

    @property
    def _stem(self) -> str:
        """현재 편집 중인 stem (호출 측이 같은 stem 창 식별·재로드에 쓴다)."""
        return self.editor._stem

    def _on_saved(self, stem: str) -> None:
        self.setWindowTitle(f"검수 / 편집 — {stem}")
        self.saved.emit(stem)

    def reload(self) -> None:
        """meta 갱신 반영 — 편집기를 현재 stem 으로 다시 읽는다 (미저장 편집은 버려진다)."""
        self.editor.reload()
