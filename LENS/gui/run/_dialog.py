"""flow 프로필 빌더 다이얼로그 — ``Flow_sequence`` + 저장/불러오기 (실행 없음, 설계는 README)."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from gui._io import load_dict, save_dict
from gui.run._sequence import Flow_sequence
from gui.widgets import Pop_dialog


class Run_dialog(Pop_dialog):
    """flow 시퀀스(프로필) 빌더 — 편집 + 저장/불러오기 (실행 없음)."""

    def __init__(self, flows: list | None = None, parent=None) -> None:
        """다이얼로그를 구성한다.

        Args:
            flows: 복원할 flow config 리스트 (메인이 보유 중인 현재 프로필).
            parent: 부모 위젯.
        """
        super().__init__("flow 프로필 — 빌더", size=(720, 560), parent=parent)

        self._sequence = Flow_sequence()
        self._sequence.load(flows or [])
        self._set_body(self._sequence)

        _save = QPushButton("flow 저장")
        _save.clicked.connect(self._on_save)
        _load = QPushButton("불러오기")
        _load.clicked.connect(self._on_load)
        self._bottom_bar(left=[_save, _load], on_reject=self.accept)

    def flows(self) -> list:
        """현재 편집된 flow config 리스트를 반환한다 (메인이 닫을 때 읽어 보유)."""
        return self._sequence.to_config()

    def _on_save(self) -> None:
        save_dict(self, "flows.yaml", {"flows": self._sequence.to_config()})

    def _on_load(self) -> None:
        _, _d = load_dict(self)
        if _d is not None:
            self._sequence.load(_d.get("flows", []))
