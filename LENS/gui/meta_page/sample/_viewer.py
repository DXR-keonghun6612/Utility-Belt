"""tasker별 sample 뷰어 — split→class→sample 트리 + crop 미리보기 + class write-back (비모달).

파생 ``Sample_Set``(``pipeline.Load_sample(name)``)을 읽어 트리로 보여준다. sample 은 정본의 투영이라
미리보기는 **crop payload(있으면)** 또는 **정본 프레임 역참조**(source_stem→meta)로 그린다. class 편집은
**인라인 attr write-back** — 정본 obj 의 ``class_id`` 를 고치고([[project_sample_tasker_layer]]) 그 sample
하나만 새 class 폴더로 옮기는 **부분 재파생**이다(crop 픽셀은 그대로, 폴더만 이동 — 전체 재빌드 없음).
geometry(mask)는 여기서 안 건드린다(Stem_editor 소유).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.data import handler, store_io
from core.data.handler import Data_Ref
from core.data.schema import Attr, Set_attr
from gui.meta_page.verify._overlay import load_base_images, merge_bases
from gui.widgets import Image_label, Pop_dialog

_ROLE = Qt.ItemDataRole.UserRole   # sample 항목 식별 (split, group, sample_id)


class Sample_viewer(Pop_dialog):
    """tasker 하나의 sample 트리 + crop 미리보기 + class 재배정 (write-back).

    Attributes:
        meta_changed: class write-back 으로 정본이 바뀌었을 때 emit (상위 meta 뷰 갱신용).
    """

    meta_changed = Signal()

    def __init__(self, get_pipeline: Callable[[], object | None], name: str, parent=None) -> None:
        super().__init__(f"Sample 뷰어 — {name}", size=(920, 600), parent=parent)
        self._get_pipeline = get_pipeline
        self._name = name
        self._sset = None
        self._task = "classification"
        self._build()
        self.reload()

    def _build(self) -> None:
        _split = QSplitter(Qt.Orientation.Horizontal)

        # ── 좌: 트리 ─────────────────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["sample", "수"])
        self._tree.setColumnWidth(0, 260)
        self._tree.currentItemChanged.connect(self._on_select)
        _split.addWidget(self._tree)

        # ── 우: 미리보기 + 정보 + class 재배정 ───────────────────────────────
        _right = QWidget()
        _rl = QVBoxLayout(_right)
        _rl.setContentsMargins(4, 4, 4, 4)
        self._img = Image_label("sample 을 선택하세요")
        _rl.addWidget(self._img, stretch=1)
        self._info = QLabel("")
        self._info.setStyleSheet("color: #888;")
        self._info.setWordWrap(True)
        _rl.addWidget(self._info)
        _cls_row = QHBoxLayout()
        _cls_row.addWidget(QLabel("class"))
        self._class = QComboBox()
        self._class.setEditable(True)
        _cls_row.addWidget(self._class, stretch=1)
        self._assign_btn = QPushButton("재배정")
        self._assign_btn.setToolTip("정본 obj 의 class_id 를 고치고 이 sample 을 새 class 로 옮긴다 (부분 재파생)")
        self._assign_btn.clicked.connect(self._on_reassign)
        _cls_row.addWidget(self._assign_btn)
        _rl.addLayout(_cls_row)
        _split.addWidget(_right)
        _split.setStretchFactor(1, 1)
        _split.setSizes([320, 600])
        self._set_body(_split)

        self._bottom_bar(on_reject=self.accept)

    # ── 채우기 ─────────────────────────────────────────────────────────────────
    def reload(self, keep: tuple | None = None) -> None:
        """tasker 의 ``Sample_Set`` 을 다시 읽어 트리를 채운다 (``keep`` = 유지할 (split, group, sid))."""
        _pipe = self._get_pipeline()
        self._tree.clear()
        if _pipe is None:
            return
        self._sset = _pipe.Load_sample(self._name)
        self._task = _pipe.Taskers().get(self._name, {}).get("task", "classification")
        self._assign_btn.setEnabled(self._task == "classification")
        _target = None
        for _split in self._sset.CATEGORIES:
            _bucket = self._sset.Bucket(_split)
            _n = sum(len(_g.info) for _g in _bucket.values())
            _snode = QTreeWidgetItem([_split, str(_n)])
            self._tree.addTopLevelItem(_snode)
            for _gkey, _gstem in sorted(_bucket.items()):
                _gnode = QTreeWidgetItem([_gkey, str(len(_gstem.info))])
                _snode.addChild(_gnode)
                for _sid in sorted(_gstem.info):
                    _it = QTreeWidgetItem([_sid, ""])
                    _it.setData(0, _ROLE, (_split, _gkey, _sid))
                    _gnode.addChild(_it)
                    if keep is not None and (_split, _gkey, _sid) == keep:
                        _target = _it
            _snode.setExpanded(True)
        self._refresh_class_options()
        if _target is not None:
            self._tree.setCurrentItem(_target)

    def _refresh_class_options(self) -> None:
        """편집 콤보의 class 후보를 tasker 전 class(group key) 로 채운다 (편집 가능 — 새 class 입력)."""
        _classes = sorted({
            _g for _split in self._sset.CATEGORIES for _g in self._sset.Bucket(_split)
        }) if self._sset is not None else []
        _cur = self._class.currentText()
        self._class.blockSignals(True)
        self._class.clear()
        self._class.addItems(_classes)
        self._class.setEditText(_cur)
        self._class.blockSignals(False)

    # ── 선택 → 미리보기 ─────────────────────────────────────────────────────────
    def _on_select(self, item: QTreeWidgetItem | None, _prev=None) -> None:
        _id = item.data(0, _ROLE) if item is not None else None
        if _id is None:                                 # split/group 노드 — 미리보기 비움
            self._img.clear_image("sample 을 선택하세요")
            self._info.setText("")
            return
        _split, _group, _sid = _id
        _ref = self._sample_ref(_split, _group, _sid)
        if _ref is None:
            return
        self._class.setEditText(Attr(_ref, "class_id") or _group)
        self._show_preview(_split, _sid, _ref)
        _src = Attr(_ref, "source_stem")
        _obj = Attr(_ref, "source_obj")
        _has_crop = "crop" in _ref.info
        self._info.setText(
            f"[{_split}]  class={Attr(_ref, 'class_id') or _group}\n"
            f"source: {_src}" + (f" · obj {_obj}" if _obj else "")
            + ("  ·  crop 실체화됨" if _has_crop else "  ·  crop 없음(정본 프레임 역참조)"))

    def _show_preview(self, split: str, sid: str, ref: Data_Ref) -> None:
        """crop payload(있으면) 또는 정본 프레임(역참조)을 미리보기에 그린다."""
        _crop = ref.info.get("crop")
        if _crop is not None:
            _arr = handler.Load(self._sset.Category_root(split), sid, "crop", _crop)
            if _arr is not None:
                self._img.set_image(_arr)
                return
        _pipe = self._get_pipeline()
        _src = Attr(ref, "source_stem")
        _meta = _pipe.meta if _pipe is not None else None
        if _meta is not None and _src and _meta.Has(_src):
            _img = merge_bases(list(load_base_images(_meta, _src).values()))
            if _img is not None:
                self._img.set_image(_img)
                return
        self._img.clear_image("미리보기 없음 (crop·정본 프레임 모두 없음)")

    def _sample_ref(self, split: str, group: str, sid: str) -> Data_Ref | None:
        """트리 식별자로 live sample stem 을 찾는다 (reload 후에도 stale 없이)."""
        if self._sset is None:
            return None
        _grp = self._sset.Bucket(split).get(group)
        return _grp.info.get(sid) if _grp is not None else None

    # ── class 재배정 (write-back + 부분 재파생) ────────────────────────────────
    def _on_reassign(self) -> None:
        _item = self._tree.currentItem()
        _id = _item.data(0, _ROLE) if _item is not None else None
        if _id is None:
            return
        _split, _old_class, _sid = _id
        _new_class = self._class.currentText().strip()
        if not _new_class or _new_class == _old_class:
            return
        _pipe = self._get_pipeline()
        _ref = self._sample_ref(_split, _old_class, _sid)
        if _pipe is None or _ref is None:
            return
        if not self._writeback_class(_pipe, _ref, _new_class):
            return
        self._move_sample(_split, _old_class, _sid, _new_class, _ref)   # 부분 재파생
        self.reload(keep=(_split, _new_class, _sid))
        self.meta_changed.emit()

    def _writeback_class(self, pipe, ref: Data_Ref, new_class: str) -> bool:
        """정본 obj(source 역참조)의 ``class_id`` 를 고치고 그 stem 사이드카만 저장한다 (인라인 attr only)."""
        _src = Attr(ref, "source_stem")
        _obj = Attr(ref, "source_obj")
        _frame = pipe.meta.Get(_src) if _src else None
        if _frame is None:
            QMessageBox.warning(self, "재배정", f"정본에서 source stem '{_src}' 를 찾지 못했습니다.")
            return False
        _target = _frame.info.get(_obj) if _obj else _frame
        if _target is None:
            QMessageBox.warning(self, "재배정", f"source obj '{_obj}' 를 찾지 못했습니다.")
            return False
        Set_attr(_target, "class_id", new_class)      # 정본 write-back (인라인 attr)
        store_io.Save_item(pipe.meta, _src)
        return True

    def _move_sample(self, split: str, old_class: str, sid: str,
                     new_class: str, ref: Data_Ref) -> None:
        """sample stem 하나를 old_class→new_class 로 옮긴다 — crop 파일 이동 + class attr + 사이드카.

        crop 픽셀은 class 와 무관하게 동일하므로 재-crop 없이 폴더만 옮긴다(부분 재파생). crop 이 있으면
        payload 를 새 class dir 로 다시 떨구고(옛 파일 삭제), sample stem 의 class_id attr 를 갱신한다.
        """
        _sroot = self._sset.Category_root(split)
        _old_stem = self._sset.Bucket(split)[old_class]
        _old_stem.info.pop(sid, None)
        _crop = ref.info.get("crop")
        if _crop is not None:                          # crop 파일을 새 class dir 로 이동
            _arr = handler.Load(_sroot, sid, "crop", _crop)
            handler.Delete(_sroot, sid, "crop", _crop)
            ref.info["crop"] = handler.Save(
                _sroot, sid, "crop",
                Data_Ref(type="image", format="png", info={"dir": new_class}), _arr)
        Set_attr(ref, "class_id", new_class)
        _new_stem = self._sset.Bucket(split).setdefault(new_class, Data_Ref(type="stem", info={}))
        _new_stem.info[sid] = ref
        store_io.Save_item(self._sset, new_class)      # 두 class 사이드카만 (증분)
        if _old_stem.info:
            store_io.Save_item(self._sset, old_class)
        else:                                          # 빈 class 는 사이드카·버킷에서 제거
            store_io.Drop(self._sset, split, old_class)
            self._sset.Bucket(split).pop(old_class, None)
