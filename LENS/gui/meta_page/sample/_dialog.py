"""Sampler 창 — tasker 마다 탭 (``+`` 새 tasker · ``x`` 제거) + 탭별 sample 편집 (비모달).

정본(staged ``Dataset_Meta``)에서 이름 붙은 tasker(파생 학습셋)를 빌드·편집한다. 창은 ``QTabWidget``
컨테이너일 뿐이고, 탭 한 칸 = tasker 한 개 = [`_tab`](_tab.py)(``Tasker_tab``: 툴바 + sample 편집 뷰)이
소유한다. 탭바 코너 ``+`` 로 새 tasker 를 만들고, 탭 ``x`` 로 제거한다(``Pipeline.Delete_tasker``). 목록은
``Pipeline.List_taskers()``(레시피 ∪ 실제 폴더)로 복원한다. 메인 진입은 ``app`` 의 ``Sampler…`` 버튼
(비모달, ``get_pipeline`` 주입). class write-back 알림은 ``meta_changed`` 로 상위 meta 뷰에 전파.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QToolButton,
)

from gui.meta_page.sample._tab import Tasker_tab
from gui.widgets import Pop_dialog


class Sampler_dialog(Pop_dialog):
    """파생 tasker 탭 컨테이너 — tasker 마다 탭, 코너 ``+`` 추가 · 탭 ``x`` 제거 (비모달).

    Attributes:
        meta_changed: 어느 탭의 class write-back 으로 정본이 바뀌었을 때 emit (상위 meta 뷰 갱신용).
    """

    meta_changed = Signal()

    def __init__(self, get_pipeline: Callable[[], object | None], parent=None) -> None:
        """Args:
        get_pipeline: 보유 ``Pipeline`` 을 돌려주는 콜백 (없으면 None — Convert/Run 과 동일 패턴).
        """
        super().__init__("Sampler — 파생 tasker", size=(880, 620), parent=parent)
        self._get_pipeline = get_pipeline
        self._build()
        self.reload_taskers()

    def _build(self) -> None:
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self._on_close_tab)
        _add = QToolButton()
        _add.setText("+")
        _add.setToolTip("새 tasker 추가")
        _add.clicked.connect(self._on_new)
        self._tabs.setCornerWidget(_add, Qt.Corner.TopRightCorner)

        # 탭이 0개면 QTabWidget 은 빈 화면 + 코너 버튼도 잘 안 보인다 → 안내 placeholder 로 전환.
        self._empty = QLabel("tasker 가 없습니다.\n탭바의 '+' 또는 아래 '새 tasker' 로 추가하세요.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet("color: #888;")
        self._stack = QStackedWidget()
        self._stack.addWidget(self._empty)             # index 0 — 빈 상태
        self._stack.addWidget(self._tabs)              # index 1 — 탭 있음
        self._set_body(self._stack)

        _new = QPushButton("새 tasker")                # 빈 상태에서도 항상 보이는 추가 버튼
        _new.clicked.connect(self._on_new)
        self._bottom_bar(left=[_new], on_reject=self.accept)

    # ── 탭 목록 ────────────────────────────────────────────────────────────────
    def reload_taskers(self) -> None:
        """``Pipeline.List_taskers()`` 로 탭을 다시 채운다 (레시피 ∪ 실제 폴더)."""
        _pipe = self._get_pipeline()
        while self._tabs.count():                      # 기존 탭 정리 (pipeline 교체·재열림)
            _w = self._tabs.widget(0)
            self._tabs.removeTab(0)
            _w.deleteLater()
        if _pipe is not None:
            _taskers = _pipe.Taskers()
            for _name in _pipe.List_taskers():
                self._add_tab(_name, _taskers.get(_name))
        self._update_view()

    def _add_tab(self, name: str, cfg: dict | None = None) -> Tasker_tab:
        _tab = Tasker_tab(self._get_pipeline, name, cfg)
        _tab.meta_changed.connect(self.meta_changed)
        self._tabs.addTab(_tab, name)
        self._update_view()
        return _tab

    def _update_view(self) -> None:
        """탭 유무에 따라 안내 placeholder ↔ 탭 위젯을 전환한다."""
        self._stack.setCurrentIndex(1 if self._tabs.count() else 0)

    def _tab_index(self, name: str) -> int | None:
        for _i in range(self._tabs.count()):
            if self._tabs.tabText(_i) == name:
                return _i
        return None

    def _on_new(self) -> None:
        """새 tasker 이름을 받아 빈 탭을 만든다 (레시피는 탭의 ``프로필 편집`` 으로, 빌드는 ``▶ sample`` 로)."""
        _pipe = self._get_pipeline()
        if _pipe is None:
            QMessageBox.information(self, "새 tasker", "먼저 dataset_root 를 여세요.")
            return
        _name, _ok = QInputDialog.getText(self, "새 tasker", "tasker 이름 (폴더·레지스트리 key):")
        _name = _name.strip()
        if not _ok or not _name:
            return
        _idx = self._tab_index(_name)                  # 이미 있으면 그 탭으로
        if _idx is not None:
            self._tabs.setCurrentIndex(_idx)
            return
        self._tabs.setCurrentWidget(self._add_tab(_name))

    def _on_close_tab(self, index: int) -> None:
        """탭 ``x`` — 확인 후 tasker 폴더·레시피를 지우고(``Delete_tasker``) 탭을 닫는다."""
        _name = self._tabs.tabText(index)
        if QMessageBox.question(
                self, "tasker 삭제",
                f"tasker '{_name}' 의 폴더·레시피를 삭제합니다. 계속할까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        _pipe = self._get_pipeline()
        if _pipe is not None:
            _pipe.Delete_tasker(_name)
        _w = self._tabs.widget(index)
        self._tabs.removeTab(index)
        _w.deleteLater()
        self._update_view()
