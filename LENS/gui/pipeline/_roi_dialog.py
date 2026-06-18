"""ROI 다이얼로그 — 샘플 프레임 위에 다각형을 그려 배경 ROI 마스크를 만든다.

share 블록의 "ROI 그리기" 버튼이 연다. 첫 dataloader 의 첫 프레임을 샘플로 띄우고,
좌클릭으로 다각형 꼭짓점을 찍어 채운 마스크를 PNG 로 저장한 뒤 그 경로를 돌려준다.
호출부(share 블록)는 이 경로를 `share.images` 의 (bg_roi, path) 로 주입한다.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from core.dataloader._base import FRAME_KEY
from core.dataloader.build import Build_reader
from gui.widgets import _bgr_to_pixmap


def Load_sample_frame(dl_meta: dict) -> np.ndarray | None:
    """dataloader meta 로 reader 를 만들어 첫 source 의 첫 프레임(BGR)을 로드한다.

    Args:
        dl_meta: Dataloader_config.Serialize() 형식의 meta dict.

    Returns:
        BGR 이미지 ndarray. 로드 가능한 프레임이 없으면 None.
    """
    _reader = Build_reader(dl_meta)
    for _src in dl_meta.get("sources", []):
        for _meta in _reader.Scan(Path(_src)):
            _path = _meta.data_path.get(FRAME_KEY)
            if _path is None:
                continue
            _img = cv2.imread(str(_path), cv2.IMREAD_COLOR)
            if _img is not None:
                return _img
    return None


class _PolyCanvas(QLabel):
    """프레임을 fit 배율로 띄우고 좌클릭으로 다각형 꼭짓점을 모으는 캔버스.

    좌클릭=점 추가, 우클릭=마지막 점 취소. 점은 소스 픽셀 좌표로 저장하고,
    클릭 좌표는 표시 배율로 역변환한다.
    """

    changed = Signal()

    def __init__(
        self, frame_bgr: np.ndarray, max_w: int = 960, max_h: int = 680, parent=None
    ) -> None:
        super().__init__(parent)
        self._img = frame_bgr
        _h, _w = frame_bgr.shape[:2]
        self._scale = min(max_w / _w, max_h / _h, 1.0)
        self._disp = (max(1, int(_w * self._scale)), max(1, int(_h * self._scale)))
        self._pts: list[tuple[int, int]] = []

        self.setFixedSize(*self._disp)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._render()

    # ── public API ───────────────────────────────────────────────────────────

    def undo(self) -> None:
        if self._pts:
            self._pts.pop()
            self._render()
            self.changed.emit()

    def clear_points(self) -> None:
        if self._pts:
            self._pts.clear()
            self._render()
            self.changed.emit()

    def point_count(self) -> int:
        return len(self._pts)

    def mask(self) -> np.ndarray | None:
        """3점 이상이면 채운 binary 마스크(H, W; 0/255)를 반환, 아니면 None."""
        if len(self._pts) < 3:
            return None
        _h, _w = self._img.shape[:2]
        _m = np.zeros((_h, _w), np.uint8)
        cv2.fillPoly(_m, [np.array(self._pts, np.int32)], 255)
        return _m

    # ── internals ────────────────────────────────────────────────────────────

    def _render(self) -> None:
        _vis = self._img.copy()
        if self._pts:
            _arr = np.array(self._pts, np.int32)
            if len(self._pts) >= 2:
                cv2.polylines(_vis, [_arr], len(self._pts) >= 3, (0, 255, 0), 2)
            for _p in self._pts:
                cv2.circle(_vis, _p, 4, (0, 0, 255), -1)
        _pix = _bgr_to_pixmap(_vis).scaled(
            *self._disp, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(_pix)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            _x = int(event.position().x() / self._scale)
            _y = int(event.position().y() / self._scale)
            self._pts.append((_x, _y))
            self._render()
            self.changed.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            self.undo()


class Roi_dialog(QDialog):
    """다각형 클릭으로 ROI 마스크를 만드는 모달 다이얼로그."""

    def __init__(self, frame_bgr: np.ndarray, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("배경 ROI 그리기")
        self._canvas = _PolyCanvas(frame_bgr)
        self._build()
        self._canvas.changed.connect(self._sync)
        self._sync()

    def _build(self) -> None:
        _root = QVBoxLayout(self)

        _info = QLabel("좌클릭: 꼭짓점 추가   ·   우클릭: 마지막 점 취소   ·   3점 이상이면 채운 마스크 생성")
        _info.setStyleSheet("color: #8aa;")
        _root.addWidget(_info)

        _scroll = QScrollArea()
        _scroll.setWidgetResizable(False)
        _scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _scroll.setWidget(self._canvas)
        _root.addWidget(_scroll, stretch=1)

        _btns = QHBoxLayout()
        self._count_lbl = QLabel()
        _btns.addWidget(self._count_lbl)
        _btns.addStretch(1)

        _undo = QPushButton("되돌리기")
        _undo.clicked.connect(self._canvas.undo)
        _clear = QPushButton("초기화")
        _clear.clicked.connect(self._canvas.clear_points)
        _cancel = QPushButton("취소")
        _cancel.clicked.connect(self.reject)
        self._ok = QPushButton("확인")
        self._ok.clicked.connect(self.accept)
        for _b in (_undo, _clear, _cancel, self._ok):
            _btns.addWidget(_b)
        _root.addLayout(_btns)

    def _sync(self) -> None:
        _n = self._canvas.point_count()
        self._count_lbl.setText(f"점 {_n}개")
        self._ok.setEnabled(_n >= 3)

    def mask(self) -> np.ndarray | None:
        return self._canvas.mask()

    @classmethod
    def Get_mask(cls, frame_bgr: np.ndarray, parent=None) -> np.ndarray | None:
        """다이얼로그를 띄워 마스크를 받는다. 취소 시 None."""
        _dlg = cls(frame_bgr, parent)
        if _dlg.exec() == QDialog.DialogCode.Accepted:
            return _dlg.mask()
        return None
