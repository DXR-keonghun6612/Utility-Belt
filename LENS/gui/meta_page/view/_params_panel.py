"""params 영역 — dataset-wide 값의 트리 + 추가/삭제.

**stem 이 아니다.** 범주에도 안 속하고 stem 축도 없어 목록에 끼워 넣지 않는다 — 화면에서도 축이 다르다
(stem 을 바꿔도 params 는 그대로 있고, 그 raster 는 어느 stem 위에든 겹쳐 볼 수 있다).

트리 자체는 [`_node_tree.py`](_node_tree.py) 의 재귀 렌더러를 그대로 쓴다 — params 도 같은 `Data_Ref` 다.
여기가 더하는 건 **추가/삭제**뿐이고, 그건 라이프사이클이라 store 메서드(``Import_param``/``Delete_param``)를
직접 부른다(경로는 store 가 안다).
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import port
from core.schema import Data_Ref

from ._node_tree import Node_tree


class _Add_dialog(QDialog):
    """params 항목 추가 — 파일이면 ``type`` 을 고르고, 값이면 그대로 인라인."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("params 추가")
        _lay = QVBoxLayout(self)
        _form = QFormLayout()

        self._name = QLineEdit()
        self._name.setPlaceholderText("roi")
        _form.addRow("종류 (key)", self._name)

        self._kind = QComboBox()
        self._kind.addItems(["파일", "값 (인라인)", "빈 라스터"])
        self._kind.currentTextChanged.connect(self._sync)
        _form.addRow("종류", self._kind)

        _row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setPlaceholderText("/path/to/roi.png")
        _browse = QPushButton("📁")
        _browse.setFixedWidth(36)
        _browse.clicked.connect(self._browse)
        _row.addWidget(self._path)
        _row.addWidget(_browse)
        self._path_row = QWidget()
        self._path_row.setLayout(_row)
        _form.addRow("파일", self._path_row)

        self._type = QComboBox()
        self._type.addItems(port.Types())
        self._type.setToolTip("핸들러 — 확장자로 추론하지 않는다 "
                              "(png 는 image 일 수도 segmap 일 수도 있다)")
        _form.addRow("type", self._type)

        self._value = QLineEdit()
        self._value.setPlaceholderText("값")
        _form.addRow("값", self._value)

        _lay.addLayout(_form)
        _btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        _btn.accepted.connect(self.accept)
        _btn.rejected.connect(self.reject)
        _lay.addWidget(_btn)
        self._sync()

    def _sync(self, *_a) -> None:
        _txt = self._kind.currentText()
        _is_file = _txt == "파일"
        _is_blank = _txt == "빈 라스터"
        self._path_row.setVisible(_is_file)
        self._type.setVisible(_is_file or _is_blank)      # 빈 라스터도 handler(segmap/image) 필요
        self._value.setVisible(not _is_file and not _is_blank)

    def _browse(self) -> None:
        _p, _ = QFileDialog.getOpenFileName(self, "dataset-wide 파일 선택")
        if _p:
            self._path.setText(_p)

    def result_spec(self) -> tuple[str, str, str, str]:
        """``(name, kind, path_or_value, type)`` — kind 는 ``file``/``value``/``blank``."""
        _kind = {"파일": "file", "값 (인라인)": "value", "빈 라스터": "blank"}[self._kind.currentText()]
        _payload = self._path if _kind == "file" else self._value
        return (self._name.text().strip(), _kind, _payload.text().strip(),
                self._type.currentText())


class Params_panel(QWidget):
    """params 트리 + [수정]/추가/삭제 툴바.

    **params 는 전역(dataset-wide)이라 조심스럽게 다룬다** — 선택만으론 편집하지 않고, 명시적 [수정]에서만
    편집기를 그 값으로 조준한다(무심코 칠하면 전 stem 에 파급). 그래서 raster 기본 시각화도 꺼둔다.

    Attributes:
        changed: params 가 추가/삭제돼 저장됨 — 상위가 뷰를 갱신한다.
        edit_requested: [수정] 눌림 ``(Node)`` — 상위가 그 값을 편집기/인스펙터로 연다.
    """

    changed        = Signal()
    edit_requested = Signal(object)

    def __init__(self, get_store: Callable[[], object | None],
                 get_size: Callable[[], tuple[int, int] | None] | None = None,
                 parent=None) -> None:
        """Args:
        get_store: 정본 store (없을 수 있다).
        get_size:  빈 라스터를 만들 크기 (H, W) — 현재 stem 이미지에서 (없으면 못 만든다).
        """
        super().__init__(parent)
        self._get_store = get_store
        self._get_size = get_size or (lambda: None)
        self._editable = True

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(2)

        _tool = QHBoxLayout()
        self._edit_btn = QPushButton("✎ 수정")
        self._edit_btn.setToolTip("선택한 params 값을 편집한다 — raster(roi)는 원본 위에서 캔버스 편집")
        self._edit_btn.setEnabled(False)                  # 선택이 있어야 켠다 (전역이라 명시적 편집만)
        self._edit_btn.clicked.connect(self._on_edit)
        self._add_btn = QPushButton("+ 추가")
        self._add_btn.setToolTip("dataset-wide 값을 더한다 (파일 · 인라인 값 · 빈 라스터)")
        self._add_btn.clicked.connect(self._add)
        self._del_btn = QPushButton("✕ 삭제")
        self._del_btn.setToolTip("선택한 params 항목을 지운다 (payload 파일까지)")
        self._del_btn.clicked.connect(self._delete)
        _tool.addWidget(self._edit_btn)
        _tool.addWidget(self._add_btn)
        _tool.addWidget(self._del_btn)
        _tool.addStretch(1)
        _lay.addLayout(_tool)

        self.tree = Node_tree(check_default=False)         # 전역이라 기본 시각화 OFF (stem 마다 방해)
        self.tree.selected.connect(self._on_select)
        _lay.addWidget(self.tree, stretch=1)

    # ── Public ────────────────────────────────────────────────────────────────
    def load(self, store) -> None:
        """params 서브트리를 채운다."""
        self.tree.load(store, store.PARAMS)

    def clear(self) -> None:
        self.tree.clear()

    def set_editable(self, editable: bool) -> None:
        """편집 잠금 — 보기·체크는 유지하고 수정/추가/삭제만 막는다."""
        self._editable = editable
        self._edit_btn.setEnabled(editable and self.tree.current_node() is not None)
        self._add_btn.setEnabled(editable)
        self._del_btn.setEnabled(editable)
        self.tree.set_editable(editable)

    # ── 수정 (선택 후 명시적으로만) ─────────────────────────────────────────────
    def _on_select(self, node) -> None:
        """선택이 바뀌면 [수정] 가용성만 갱신한다 — **선택만으론 편집기를 조준하지 않는다**(전역이라)."""
        self._edit_btn.setEnabled(self._editable and node is not None)

    def _on_edit(self) -> None:
        _node = self.tree.current_node()
        if _node is not None and self._editable:
            self.edit_requested.emit(_node)

    # ── 추가 / 삭제 (라이프사이클 = store 소유) ─────────────────────────────────
    def _add(self) -> None:
        _store = self._get_store()
        if _store is None or not self._editable:
            return
        _dlg = _Add_dialog(self)
        if not _dlg.exec():
            return
        _name, _kind, _val, _type = _dlg.result_spec()
        if not _name:
            QMessageBox.warning(self, "params 추가", "종류(key)를 입력하세요.")
            return
        try:
            if _kind == "file":
                if not _val:
                    QMessageBox.warning(self, "params 추가", "파일을 선택하세요.")
                    return
                _store.Import_param(_name, _val, type=_type)      # payload 복사 + 등록
            elif _kind == "blank":                                # 빈 라스터 — 캔버스에서 그린다
                _size = self._get_size()
                if _size is None:
                    QMessageBox.warning(
                        self, "params 추가",
                        "크기를 잡을 stem 이미지가 없습니다 — stem 을 먼저 여세요.")
                    return
                _store.Add_leaf((_store.PARAMS,), _name,           # 빈 payload 는 port 가 낸다
                                {"to": "storage", "type": _type, "format": "png"},
                                port.Blank(_type, size=_size))
            else:
                _store.Set_param(_name, Data_Ref(format=("", "str"), info={"value": _val}))
        except Exception as _e:                                   # 조용히 삼키지 않는다
            QMessageBox.critical(self, "params 추가", str(_e))
            return
        _store.Save()
        self.load(_store)
        self.changed.emit()

    def _delete(self) -> None:
        _store = self._get_store()
        _node = self.tree.current_node()
        if _store is None or _node is None or not self._editable:
            return
        if len(_node.path) != 1:                                  # params 직속만 (중첩은 값 안쪽)
            QMessageBox.information(self, "params 삭제", "params 직속 항목만 지울 수 있습니다.")
            return
        if QMessageBox.question(
                self, "params 삭제",
                f"'{_node.name}' 을 지웁니다 (payload 파일까지). 계속할까요?") \
                != QMessageBox.StandardButton.Yes:
            return
        _store.Delete_param(_node.name)
        _store.Save()
        self.load(_store)
        self.changed.emit()
