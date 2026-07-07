"""object 한 개의 값(class_id/obj_id/bbox)을 편집하는 폼.

``_Annotation_panel`` 의 트리 노드마다 임베드돼, 선택한 object 의 속성을 직접 편집한다.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from core.data.handler import Data_Ref
from core.data.schema import Attr, Set_attr

from gui.verify._helpers import _bbox_of


class _Ann_edit_form(QWidget):
    """object 하나의 값(class_id/obj_id/bbox)을 편집하는 폼.

    값이 바뀌면 ``changed`` (다시 그리기) 를, obj_id 가 바뀌면 ``renamed`` 를 emit 한다(실제 재키잉은
    상위 패널이 한다 — obj_id 는 부모 info 의 key). 실제 값이 바뀐 편집마다 ``edited`` 도 emit 해 상위가
    실행취소 이력을 남긴다. bbox 편집은 ``info["bbox"]`` Data_Ref 의 인라인 값을 직접 갱신한다.
    """

    changed = Signal()
    edited  = Signal()
    renamed = Signal(str)

    def __init__(self, obj: Data_Ref, obj_id: str, classes: list[str],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._obj = obj
        self._bbox_ref = obj.info.get("bbox")

        self._form = QFormLayout(self)
        self._form.setContentsMargins(6, 6, 6, 6)

        # class_id (편집 가능 콤보)
        _cls_val = Attr(obj, "class_id")
        self._cls = QComboBox()
        self._cls.setEditable(True)
        self._cls.addItems(sorted(set(classes) | {_cls_val}))
        self._cls.setCurrentText(_cls_val)
        self._cls.currentTextChanged.connect(self._set_cls)
        self._form.addRow("class_id", self._cls)

        # obj_id (부모 info 의 key — 표시만; 실제 재키잉은 renamed 시그널로 패널이 함)
        self._obj_id = QLineEdit(obj_id)
        self._obj_id.textChanged.connect(self._set_obj_id)
        self._form.addRow("obj_id", self._obj_id)

        # bbox (있을 때만 — 없으면 그림으로 그린 뒤 set_bbox_values 가 행을 만든다)
        self._bbox_spins: list[QSpinBox] = []
        _bbox = _bbox_of(obj)
        if _bbox is not None:
            self._build_bbox_row(_bbox)

    def _build_bbox_row(self, values) -> None:
        """x0/y0/x1/y1 스핀 4개 행을 폼에 추가한다 (최초 1회).

        Args:
            values: 초기값 ``[x0, y0, x1, y1]``.
        """
        _row = QHBoxLayout()
        for _i, _label in enumerate(("x0", "y0", "x1", "y1")):
            _sp = QSpinBox()
            _sp.setRange(0, 100000)
            _sp.setValue(int(values[_i]))
            _sp.setPrefix(f"{_label} ")
            _sp.valueChanged.connect(self._set_bbox)
            self._bbox_spins.append(_sp)
            _row.addWidget(_sp)
        _w = QWidget()
        _w.setLayout(_row)
        self._form.addRow("bbox", _w)

    def set_bbox_values(self, values) -> None:
        """그림 편집 결과를 스핀에 반영한다 (없던 bbox면 행을 새로 만든다).

        Args:
            values: ``[x0, y0, x1, y1]``.
        """
        self._bbox_ref = self._obj.info.get("bbox")
        if not self._bbox_spins:
            self._build_bbox_row(values)
            return
        for _sp, _v in zip(self._bbox_spins, values):
            _sp.blockSignals(True)
            _sp.setValue(int(_v))
            _sp.blockSignals(False)

    def _set_cls(self, text: str) -> None:
        Set_attr(self._obj, "class_id", text)
        self.edited.emit()

    def _set_obj_id(self, text: str) -> None:
        self.renamed.emit(text)          # 실제 재키잉(부모 info key)은 상위 패널이 처리
        self.edited.emit()

    def _set_bbox(self) -> None:
        if self._bbox_ref is not None:
            self._bbox_ref.info["value"] = [_sp.value() for _sp in self._bbox_spins]
        self.changed.emit()
        self.edited.emit()
