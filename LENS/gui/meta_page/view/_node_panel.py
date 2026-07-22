"""노드 영역 — 선택 stem 의 트리 + 추가/삭제. 역할(``scope``)로 데이터/객체를 가른다.

**두 축은 같은 데이터모델(재귀 ``Data_Ref``)의 다른 표현이다** — geometry(raster leaf)와 객체(attr
컨테이너)는 사용자가 하는 일이 다르다. 그래서 트리를 둘로 나눈다:

- ``leaves`` (데이터) — stem 직속 데이터 leaf(frame·segment·roi). 체크해서 캔버스에 합성한다.
- ``objects`` (객체) — 객체(BRANCH)와 그 attr. 골라서 편집·조준한다.

**객체 하위엔 파일을 못 붙인다** — obj 패널이 storage 추가를 아예 안 내놓으므로(``+속성`` = 인라인만).
그래서 "객체는 payload-free" 가 규약이 아니라 **UI 구조로 강제**된다(geometry 는 stem 레벨 segment 한 장).

추가·삭제는 라이프사이클이라 store 메서드(``Add_leaf``/``Add_branch``/``Delete_node``)를 직접 부른다 —
gui 는 파일이 어디 앉는지 모른다.

**언제 디스크에 쓰나는 payload 가 가른다.** 객체는 payload-free 라 더하고 지우고 합치는 게 전부 메모리
안에서 끝나므로 **명시적 저장까지 미룬다**(취소 = 저장 없이 다시 읽기). 데이터 leaf 는 파일을 낳거나
지우는 일이라 미룰 수 없고, 그래서 사이드카도 그 자리에서 맞춘다 — 안 그러면 없는 파일을 가리키는
서술자가 남는다.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import port

from ._node_tree import Node, Node_tree

# 새로 만들 수 있는 데이터 leaf — raster 는 빈 캔버스로 나서 바로 그릴 수 있다.
_RASTER_TYPES = ("mask", "image")


class _New_leaf_dialog(QDialog):
    """새 데이터 leaf — 이름 + type. raster 면 **빈 mask 로 나서** 곧바로 그릴 수 있다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("데이터 추가")
        _lay = QVBoxLayout(self)
        _form = QFormLayout()

        self._name = QLineEdit()
        self._name.setPlaceholderText("segment")
        _form.addRow("종류 (key)", self._name)

        self._type = QComboBox()
        self._type.addItems(port.Types())
        self._type.setToolTip("mask/image = 빈 캔버스로 나서 그린다 · attr = 인라인 값")
        _form.addRow("type", self._type)

        self._value = QLineEdit()
        self._value.setPlaceholderText("인라인 값 (attr 일 때)")
        _form.addRow("값", self._value)

        _lay.addLayout(_form)
        _btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        _btn.accepted.connect(self.accept)
        _btn.rejected.connect(self.reject)
        _lay.addWidget(_btn)

    def spec(self) -> tuple[str, str, str]:
        return (self._name.text().strip(), self._type.currentText(),
                self._value.text().strip())


class Node_panel(QWidget):
    """노드 트리 + 추가/삭제 툴바 (``scope`` 로 데이터/객체 역할).

    Attributes:
        changed: 노드가 추가/삭제됨 — 상위가 재합성하고 저장 대기로 표시한다.
        raster_edited: 라벨맵을 제자리에서 고쳤다 ``(Node, raster)`` — 객체 삭제·병합이 라벨을 옮긴 것.
            디스크엔 아직 안 썼다(상위의 명시적 저장이 flush 한다) — `Data_view` 의 캔버스 편집과 같은 길.
    """

    changed       = Signal()
    raster_edited = Signal(object, object)

    def __init__(self, scope: str, get_store: Callable[[], object | None],
                 get_key: Callable[[], str], parent=None) -> None:
        """Args:
        scope:       ``leaves`` (데이터) 또는 ``objects`` (객체).
        get_store:   정본 store (없을 수 있다).
        get_key:     지금 열린 item(stem) key.
        """
        super().__init__(parent)
        self._scope = scope
        self._get_store = get_store
        self._get_key = get_key
        self._editable = True
        self._buttons: list[QPushButton] = []

        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(2)

        _tool = QHBoxLayout()
        if scope == "objects":
            self._add_button(_tool, "+ 객체", "빈 객체를 더한다 (obj_id = 다음 순번)", self.add_object)
            self._add_button(_tool, "+ 속성", "선택한 객체에 인라인 attr 을 더한다 (파일 아님)",
                             self._add_attr)
            self._add_button(_tool, "⧉ 병합",
                             "고른 객체들을 하나로 — 라벨을 합치고 bbox 는 합집합 "
                             "(class 는 가장 작은 obj_id 것이 이긴다)  [M]", self.merge_selected)
        else:
            self._add_button(_tool, "+ 데이터",
                             "stem 레벨 데이터 leaf — mask/image 는 **빈 라스터** 로 나서 바로 그린다",
                             self._add_leaf)
        self._add_button(_tool, "✕ 삭제", "선택한 노드를 지운다 (payload 파일까지)", self.delete_selected)
        _tool.addStretch(1)
        _lay.addLayout(_tool)

        self.tree = Node_tree(scope)
        _lay.addWidget(self.tree, stretch=1)

    def _add_button(self, tool, text: str, tip: str, slot) -> None:
        _b = QPushButton(text)
        _b.setToolTip(tip)
        _b.clicked.connect(slot)
        tool.addWidget(_b)
        self._buttons.append(_b)

    # ── Public ────────────────────────────────────────────────────────────────
    def load(self, store, key: str) -> None:
        self.tree.load(store, key)

    def clear(self) -> None:
        self.tree.clear()

    def set_editable(self, editable: bool) -> None:
        self._editable = editable
        for _b in self._buttons:
            _b.setEnabled(editable)
        self.tree.set_editable(editable)

    # ── 어디에 붙일까 ─────────────────────────────────────────────────────────
    def _stem_path(self) -> tuple | None:
        """선택 stem 의 컨테이너 경로 (``(범주, stem)``) — 데이터 leaf·객체는 여기 직속에 붙는다."""
        _store, _key = self._get_store(), self._get_key()
        if _store is None or not _key:
            return None
        return _store.Item_path(_key)

    def _canvas_size(self) -> tuple[int, int] | None:
        """새 raster 의 크기 — 이 stem 의 이미지 leaf 에서 가져온다 (없으면 못 만든다)."""
        _store, _key = self._get_store(), self._get_key()
        _item = _store.Find(_key) if (_store and _key) else None
        if _item is None:
            return None
        for _name, _ref in _item.Leaves().items():
            _val = _store.Load(_key, _name)
            if isinstance(_val, np.ndarray) and _val.ndim >= 2:
                return _val.shape[:2]
        return None

    # ── 추가 / 삭제 ───────────────────────────────────────────────────────────
    def add_object(self) -> None:
        """객체를 stem 직속에 더한다 — **빈 ``class_id`` attr 을 달고 나온다**(Split_objects 와 같은 모양).

        그래야 새 객체도 곧바로 인스펙터에서 id_map 콤보로 class 를 고를 수 있다(mask·bbox 는 캔버스에서).
        """
        _store = self._get_store()
        _path = self._stem_path()
        if _store is None or _path is None or not self._editable:
            return
        _name = _store.Add_branch(_path)
        _obj = _store.tree.At(_path + (_name,))
        if _obj is not None:
            _obj.Set_attr("class_id", "")
        self.load(_store, self._get_key())
        self.changed.emit()

    def _add_attr(self) -> None:
        """선택한 객체에 인라인 문자열 값을 더한다 — 값은 인스펙터에서 편집."""
        _store = self._get_store()
        _node: Node | None = self.tree.current_node()
        if _store is None or not self._editable:
            return
        if _node is None or _node.is_leaf:
            QMessageBox.information(self, "속성 추가", "먼저 객체를 고르세요.")
            return
        _name, _ok = QInputDialog.getText(self, "속성 추가", "attr 이름 (예: class_id)")
        _name = _name.strip()
        if not _ok or not _name:
            return
        _parent = _store.tree.At(_node.path + (_node.name,))
        if _parent is None:
            return
        _parent.Set_attr(_name, "")
        self.load(_store, self._get_key())
        self.changed.emit()

    def _add_leaf(self) -> None:
        """stem 직속에 데이터 leaf 를 더한다 (raster = 빈 mask, attr = 인라인 값)."""
        _store = self._get_store()
        _path = self._stem_path()
        if _store is None or _path is None or not self._editable:
            return
        _dlg = _New_leaf_dialog(self)
        if not _dlg.exec():
            return
        _name, _type, _value = _dlg.spec()
        if not _name:
            QMessageBox.warning(self, "데이터 추가", "종류(key)를 입력하세요.")
            return

        try:
            if _type in _RASTER_TYPES:
                _size = self._canvas_size()
                if _size is None:
                    QMessageBox.warning(
                        self, "데이터 추가",
                        "크기를 잡을 이미지가 없습니다 — 이 stem 에 이미지가 먼저 있어야 합니다.")
                    return
                _store.Add_leaf(_path, _name,                  # 빈 payload 는 port 가 낸다 (표현 지식)
                                {"to": "storage", "type": _type, "format": "png"},
                                port.Blank(_type, size=_size))
            else:
                _store.tree.At(_path).Set_attr(_name, _value)
        except Exception as _e:                                 # 조용히 삼키지 않는다
            QMessageBox.critical(self, "데이터 추가", str(_e))
            return

        _store.Save(self._get_key())            # 파일이 생겼으니 서술자도 지금 맞춘다
        self.load(_store, self._get_key())
        self.changed.emit()

    def delete_selected(self) -> None:
        """선택 노드를 지운다 — **객체는 메모리에서만**(저장 전엔 디스크 그대로), leaf 는 파일까지.

        이 비대칭은 payload 가 정한다: 객체는 payload-free 라 지워도 지울 파일이 없어 저장까지 미룰 수
        있고(취소 = 다시 읽기), 데이터 leaf 는 파일을 지우는 일이라 미룰 수 없다 — 그래서 사이드카도
        그 자리에서 맞춰 둔다(안 그러면 없는 파일을 가리키는 서술자가 남는다).

        **확인은 묻지 않는다** — 매번 뜨면 라벨링 동선이 끊긴다. 객체는 다시 읽기로 복원되고, leaf 는
        지워도 '빈 라스터'로 다시 그리면 되니(재생성이 복구다), 되돌릴 수 없음이 확인창을 정당화하지 못한다.
        """
        _store = self._get_store()
        _node: Node | None = self.tree.current_node()
        if _store is None or _node is None or not self._editable:
            return
        _object = self._is_object(_store, _node)
        _key = self._get_key()
        if _object:                                            # 객체 = 컨테이너 (mask 도 그 안 자식이라 함께 pop)
            _store.Remove_object(_key, _node.name)
        else:
            _store.Delete_node(_node.path, _node.name)         # leaf·객체 안 attr
            _store.Save(_key)                                  # 파일이 사라졌으니 서술자도 지금 맞춘다
        self.load(_store, _key)
        self.changed.emit()

    def merge_selected(self) -> None:
        """고른 객체들을 하나로 — 생존자는 **가장 작은 obj_id**, 그 class 가 이긴다.

        확인은 묻지 않는다 — 결과는 **저장 전까지 메모리**라 잘못 합쳤으면 다시 읽기로 복원된다(매번
        물으면 라벨링 동선이 끊긴다). 어느 class 로 합쳐졌는지는 병합 뒤 **인스펙터**가 보인다(생존자
        = 가장 작은 obj_id). 둘 미만이면 병합이 성립하지 않아 **조용히 no-op**.
        """
        _store, _key = self._get_store(), self._get_key()
        if _store is None or not _key or not self._editable:
            return
        _objs = [_n for _n in self.tree.selected_nodes() if self._is_object(_store, _n)]
        if len(_objs) < 2:
            return                                             # 둘 미만은 병합 불가 (경고 안 띄운다)

        _ids = sorted((_n.name for _n in _objs), key=int)
        _into, _others = _ids[0], _ids[1:]
        try:
            _store.Merge_objects(_key, _into, _others)         # bbox·mask 합집합 + 컨테이너 pop (검증 포함)
        except KeyError as _e:                                 # 조용히 삼키지 않는다
            QMessageBox.critical(self, "객체 병합", str(_e))
            return
        self.load(_store, _key)
        self.tree.select_name(_into)                           # 생존자로 조준이 따라간다 (그 class 를 인스펙터가 보인다)
        self.changed.emit()

    def _is_object(self, store, node: Node) -> bool:
        """이 노드가 stem 직속 객체(BRANCH)인가 — 그래야 segment 라벨을 함께 지운다(정본 전용)."""
        return (self._scope == "objects" and not node.is_leaf
                and node.path == store.Item_path(self._get_key())
                and hasattr(store, "Remove_object"))
