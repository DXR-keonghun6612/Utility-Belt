"""라벨 + 경로 입력 + 탐색(📁) 버튼을 한 줄로 묶은 재사용 입력 행."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)


class Path_row(QWidget):
    """라벨 + 경로 입력 + 탐색(📁) 버튼을 한 줄로 묶은 재사용 위젯.

    ``mode`` 에 따라 디렉터리(``'dir'``) 또는 파일(``'file'``) 선택 다이얼로그를 띄운다.
    ``refresh`` 가 True면 ↺ 버튼이 추가된다. 경로 확정(편집 완료·탐색·새로고침)마다
    ``committed`` 를 emit한다.

    Attributes:
        committed: 경로가 확정될 때 emit하는 시그널.
    """

    committed = Signal()

    def __init__(
        self,
        label: str,
        placeholder: str = "",
        mode: str = "dir",
        refresh: bool = False,
        file_filter: str = "",
        read_only: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """행을 구성한다.

        Args:
            label: 좌측 라벨 텍스트.
            placeholder: 입력칸 placeholder.
            mode: ``'dir'`` 이면 디렉터리, ``'file'`` 이면 파일 선택.
            refresh: True면 ↺ 새로고침 버튼을 추가한다.
            file_filter: ``mode == 'file'`` 일 때 다이얼로그 필터 (예: ``"YAML (*.yaml *.yml)"``).
            read_only: True면 뷰어로만 동작한다 — 직접 편집·탐색(📁) 불가, 값은
                ``setText`` 로만 바뀐다 (refresh 버튼은 그대로 ``committed`` 를 emit).
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._mode = mode
        self._filter = file_filter

        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.addWidget(QLabel(label))

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        if read_only:
            self._edit.setReadOnly(True)
        else:
            self._edit.editingFinished.connect(self.committed)
        _lay.addWidget(self._edit, stretch=1)

        if not read_only:
            _browse = QToolButton()
            _browse.setText("📁")
            _browse.setToolTip("디렉터리 선택" if mode == "dir" else "파일 선택")
            _browse.clicked.connect(self._browse)
            _lay.addWidget(_browse)

        if refresh:
            _refresh = QToolButton()
            _refresh.setText("↺")
            _refresh.setToolTip("새로고침")
            _refresh.clicked.connect(self.committed)
            _lay.addWidget(_refresh)

    def _browse(self) -> None:
        if self._mode == "file":
            _p, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", self._filter)
        else:
            _p = QFileDialog.getExistingDirectory(self, "디렉터리 선택")
        if _p:
            self._edit.setText(_p)
            self.committed.emit()

    def text(self) -> str:
        """현재 입력된 경로 문자열을 반환한다."""
        return self._edit.text()

    def setText(self, value: str) -> None:  # noqa: N802 — QLineEdit API 관례 유지
        """경로 문자열을 설정한다 (시그널은 발생시키지 않음).

        Args:
            value: 설정할 경로 문자열.
        """
        self._edit.setText(value)
