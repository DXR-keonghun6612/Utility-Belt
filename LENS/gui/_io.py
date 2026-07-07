"""파일 선택 다이얼로그 + dict 직렬화 (포맷은 확장자로 ``python_toolbox`` 가 디스패치)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from python_toolbox.file import Read_from, Write_to

_FILTER = "config (*.yaml *.yml *.json)"   # 포맷은 확장자가 정한다 (toolbox 디스패치)


def save_dict(parent: QWidget, default_name: str, payload: dict,
              *, file_filter: str = _FILTER) -> None:
    """``payload`` 를 사용자가 고른 경로에 저장한다 (취소 시 무시; 포맷=확장자)."""
    _p, _ = QFileDialog.getSaveFileName(parent, "저장", default_name, file_filter)
    if _p:
        Write_to(Path(_p), payload)


def load_dict(parent: QWidget,
              *, file_filter: str = _FILTER) -> tuple[Path | None, dict | None]:
    """파일을 골라 dict 로 읽는다 (취소/실패 시 ``(None, None)``; 포맷=확장자)."""
    _p, _ = QFileDialog.getOpenFileName(parent, "불러오기", "", file_filter)
    if not _p:
        return None, None
    _ok, _d = Read_from(Path(_p))
    return (Path(_p), _d) if _ok and isinstance(_d, dict) else (None, None)
