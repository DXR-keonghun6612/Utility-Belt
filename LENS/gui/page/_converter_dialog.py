"""Converter 다이얼로그 (부트스트랩: raw → 초기 dataset_meta) — ``Converter_panel`` wrapper."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from gui._io import load_dict, save_dict
from gui.converter import Converter_panel
from gui.widgets import Path_row, Pop_dialog


class _Converter_dialog(Pop_dialog):
    """raw → 초기 ``Dataset_Meta`` 변환 설정 다이얼로그 (``Converter_panel`` wrapper)."""

    def __init__(self, initial: dict, root: str, set_root: Callable[[str], None],
                 get_pipeline: Callable[[], object | None], parent=None) -> None:
        super().__init__("Converter — raw → dataset_meta", size=(720, 560), parent=parent)

        # Convert 는 메인이 보유한 Pipeline 위에서 돈다 — 패널에 그 Pipeline getter 를 넘긴다.
        self.panel = Converter_panel(get_pipeline=get_pipeline)
        self.panel.load(initial or {})

        # dataset_root 의 유일한 편집 지점 — 확정하면 메인(뷰어)으로 값을 밀어준다.
        self._root_row = Path_row(
            "dataset_root", placeholder="Dataset_Meta 루트 디렉터리", mode="dir")
        self._root_row.setText(root)
        self._root_row.committed.connect(
            lambda: set_root(self._root_row.text().strip()))

        # 첫 줄: dataset_root | datasource_format 콤보 (나란히).
        _top = QHBoxLayout()
        _top.addWidget(self._root_row, stretch=1)
        _top.addWidget(QLabel("datasource_format"))
        _top.addWidget(self.panel.format_combo())
        self._lay.addLayout(_top)
        self._set_body(self.panel)

        _save = QPushButton("converter 설정 저장")
        _save.clicked.connect(lambda: save_dict(self, "converter.yaml", self.export_config()))
        _load = QPushButton("불러오기")
        _load.clicked.connect(self._on_load)
        # status_label·run_button 은 Close 옆(우측)에, 저장/불러오기는 좌측에.
        self._bottom_bar(left=[_save, _load],
                         extra=[self.panel.status_label(), self.panel.run_button()],
                         on_reject=self.accept)

    def _on_load(self) -> None:
        _, _d = load_dict(self)
        if _d is not None:
            self.panel.load(_d)

    def export_config(self) -> dict:
        """현재 converter 설정을 ``{"converter": {...}}`` dict로 돌려준다."""
        return self.panel.to_config()
