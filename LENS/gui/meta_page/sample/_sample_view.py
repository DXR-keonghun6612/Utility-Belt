"""tasker 하나의 sample 편집 뷰(임베드 위젯) — group→sample 트리 + crop 미리보기 + class 재배정.

파생 ``Sample_Set``(``pipeline.Load_sample(name)``)을 읽어 트리로 보여준다. 작업 store 는 split 없는 단일
버킷(``WORKING``)이라 트리는 task 서브구조 2단이다 — classification=class→sample, detection=image→object.
sample 은 정본의 투영이라 미리보기는 **crop payload(있으면)** 또는 **정본 프레임 역참조**로 그린다.

**class 재배정**은 트리에서 **여러 sample 을 동시에 선택**해 한 class 로 보낸다. 대상 class 후보는 정본
params 의 **id_map**(+ 미분류 ``__unclassified__``)이며 검색 다이얼로그로 고른다. 재배정은 인라인 attr
write-back(정본 obj 의 ``class_id`` 수정, [[project_sample_tasker_layer]]) + 그 sample 을 새 class 폴더로
옮기는 부분 재파생이고, **재배정 로그**(``{stem: [처음class, 마지막class]}``)를 tasker 폴더 yaml 에 남긴다.
geometry(mask)는 여기서 안 건드린다(Stem_editor 소유). ``Tasker_tab`` 이 이 위젯을 호스트한다.
"""

from __future__ import annotations

from typing import Callable

from python_toolbox.file import Read_from, Write_to

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.constant import UNCLASSIFIED
from core.data import handler, store_io
from core.data.handler import Data_Ref
from core.data.sample import WORKING
from core.data.schema import Attr, Set_attr
from gui.meta_page.sample._class_picker import Class_picker
from gui.meta_page.edit._overlay import load_base_images, merge_bases
from gui.widgets import Image_label

_ROLE = Qt.ItemDataRole.UserRole   # sample 항목 식별 (group, sample_id)
_LOG_FILE = "reassign_log.yaml"    # tasker 폴더 재배정 로그 ({stem: [처음, 마지막]})


class Sample_view(QWidget):
    """tasker 하나의 group→sample 트리 + crop 미리보기 + 다중선택 class 재배정 (write-back) 위젯.

    Attributes:
        meta_changed: class write-back 으로 정본이 바뀌었을 때 emit (상위 meta 뷰 갱신용).
    """

    meta_changed = Signal()

    def __init__(self, get_pipeline: Callable[[], object | None], name: str, parent=None) -> None:
        super().__init__(parent)
        self._get_pipeline = get_pipeline
        self._name = name
        self._sset = None
        self._task = "classification"
        self._editable = True
        self._build()
        self.reload()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _split = QSplitter(Qt.Orientation.Horizontal)

        # ── 좌: 툴바(전부 접기) + 트리 (group → sample, 다중선택) ──────────────
        _left = QWidget()
        _ll = QVBoxLayout(_left)
        _ll.setContentsMargins(0, 0, 0, 0)
        _tb = QHBoxLayout()
        self._collapse_btn = QPushButton("전부 접기")
        self._collapse_btn.setToolTip("모든 class(group) 노드를 접는다 — class 가 많을 때 개관")
        self._collapse_btn.clicked.connect(lambda: self._tree.collapseAll())
        _expand_btn = QPushButton("전부 펴기")
        _expand_btn.clicked.connect(lambda: self._tree.expandAll())
        _tb.addWidget(self._collapse_btn)
        _tb.addWidget(_expand_btn)
        _tb.addStretch(1)
        _ll.addLayout(_tb)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["sample", "수"])
        self._tree.setColumnWidth(0, 260)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_menu)
        self._tree.currentItemChanged.connect(self._on_select)
        _ll.addWidget(self._tree, stretch=1)
        _split.addWidget(_left)

        # ── 우: 미리보기 + 정보 + 재배정 ─────────────────────────────────────
        _right = QWidget()
        _rl = QVBoxLayout(_right)
        _rl.setContentsMargins(4, 4, 4, 4)
        self._img = Image_label("sample 을 선택하세요")
        _rl.addWidget(self._img, stretch=1)
        self._info = QLabel("")
        self._info.setStyleSheet("color: #888;")
        self._info.setWordWrap(True)
        _rl.addWidget(self._info)
        _hint = QLabel("트리에서 sample 을 (다중)선택하고 우클릭 → class 재배정")
        _hint.setStyleSheet("color: #888;")
        _hint.setWordWrap(True)
        _rl.addWidget(_hint)
        _split.addWidget(_right)
        _split.setStretchFactor(1, 1)
        _split.setSizes([320, 600])
        _lay.addWidget(_split, stretch=1)

    # ── Public ─────────────────────────────────────────────────────────────────
    def set_editable(self, editable: bool) -> None:
        """편집 잠금 토글 — 잠그면 재배정(우클릭 메뉴)만 막고 트리 보기·미리보기는 유지한다."""
        self._editable = editable

    # ── 채우기 ─────────────────────────────────────────────────────────────────
    def reload(self, keep: tuple | None = None) -> None:
        """tasker 의 ``Sample_Set`` 을 다시 읽어 트리를 채운다 (``keep`` = 유지할 (group, sid))."""
        _pipe = self._get_pipeline()
        self._tree.clear()
        if _pipe is None:
            return
        self._sset = _pipe.Load_sample(self._name)
        self._task = _pipe.Taskers().get(self._name, {}).get("task", "classification")
        _target = None
        for _group, _gstem in sorted(self._sset.Bucket(WORKING).items()):
            _gnode = QTreeWidgetItem([_group, str(len(_gstem.info))])
            self._tree.addTopLevelItem(_gnode)
            for _sid in sorted(_gstem.info):
                _it = QTreeWidgetItem([_sid, ""])
                _it.setData(0, _ROLE, (_group, _sid))
                _gnode.addChild(_it)
                if keep is not None and (_group, _sid) == keep:
                    _target = _it
            _gnode.setExpanded(True)
        if _target is not None:
            self._tree.setCurrentItem(_target)

    # ── 선택 → 미리보기 ─────────────────────────────────────────────────────────
    def _on_select(self, item: QTreeWidgetItem | None, _prev=None) -> None:
        _id = item.data(0, _ROLE) if item is not None else None
        if _id is None:                                 # group 노드 — 미리보기 비움
            self._img.clear_image("sample 을 선택하세요")
            self._info.setText("")
            return
        _group, _sid = _id
        _ref = self._sample_ref(_group, _sid)
        if _ref is None:
            return
        self._show_preview(_sid, _ref)
        _src = Attr(_ref, "source_stem")
        _obj = Attr(_ref, "source_obj")
        _has_crop = "crop" in _ref.info
        self._info.setText(
            f"class={Attr(_ref, 'class_id') or _group}\n"
            f"source: {_src}" + (f" · obj {_obj}" if _obj else "")
            + ("  ·  crop 실체화됨" if _has_crop else "  ·  crop 없음(정본 프레임 역참조)"))

    def _show_preview(self, sid: str, ref: Data_Ref) -> None:
        """crop payload(있으면) 또는 정본 프레임(역참조)을 미리보기에 그린다."""
        _crop = ref.info.get("crop")
        if _crop is not None:
            _arr = handler.Load(self._sset.Category_root(WORKING), sid, "crop", _crop)
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

    def _sample_ref(self, group: str, sid: str) -> Data_Ref | None:
        """트리 식별자로 live sample stem 을 찾는다 (reload 후에도 stale 없이)."""
        if self._sset is None:
            return None
        _grp = self._sset.Bucket(WORKING).get(group)
        return _grp.info.get(sid) if _grp is not None else None

    # ── class 재배정 (우클릭 메뉴 + 다중선택 + id_map picker + write-back + 로그) ──
    def _on_menu(self, pos) -> None:
        """트리 우클릭 — 선택(또는 우클릭) sample 들을 class 재배정하는 메뉴를 연다."""
        if not self._editable or self._task != "classification":
            return
        _targets = [_it.data(0, _ROLE) for _it in self._tree.selectedItems()
                    if _it.data(0, _ROLE) is not None]         # leaf 만 (group 노드 제외)
        _at = self._tree.itemAt(pos)
        _at_id = _at.data(0, _ROLE) if _at is not None else None
        if _at_id is not None and _at_id not in _targets:      # 선택 밖 항목 우클릭 → 그것만
            _targets = [_at_id]
        if not _targets:
            return
        _menu = QMenu(self)
        _a = QAction(f"class 재배정…  ({len(_targets)})", _menu)
        _a.triggered.connect(lambda _c=False, t=list(_targets): self._reassign(t))
        _menu.addAction(_a)
        _menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _reassign(self, targets: list) -> None:
        """``targets``((group, sid) 목록)를 id_map picker 로 고른 class 로 일괄 재배정 + 로그."""
        _pipe = self._get_pipeline()
        if _pipe is None:
            return
        _cands = sorted(set(_pipe.Id_map()) | {UNCLASSIFIED})   # id_map class + 미분류
        _picker = Class_picker(_cands, parent=self)
        if not _picker.exec():
            return
        _new = _picker.selected()
        if not _new:
            return
        _entries: list[tuple[str, str, str]] = []          # (sid, 원본class, 새class)
        for _old_class, _sid in targets:
            if _new == _old_class:
                continue
            _ref = self._sample_ref(_old_class, _sid)
            if _ref is None or not self._writeback_class(_pipe, _ref, _new):
                continue
            self._move_sample(_old_class, _sid, _new, _ref)    # 부분 재파생
            _entries.append((_sid, _old_class, _new))
        if not _entries:
            return
        self._log_reassign(_pipe, _entries)
        self.reload(keep=(_new, _entries[-1][0]))
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

    def _move_sample(self, old_class: str, sid: str, new_class: str, ref: Data_Ref) -> None:
        """sample stem 하나를 old_class→new_class 로 옮긴다 — crop 파일 이동 + class attr + 사이드카.

        crop 픽셀은 class 와 무관하게 동일하므로 재-crop 없이 폴더만 옮긴다(부분 재파생). crop 이 있으면
        payload 를 새 class dir 로 다시 떨구고(옛 파일 삭제), sample stem 의 class_id attr 를 갱신한다.
        """
        _sroot = self._sset.Category_root(WORKING)
        _old_stem = self._sset.Bucket(WORKING)[old_class]
        _old_stem.info.pop(sid, None)
        _crop = ref.info.get("crop")
        if _crop is not None:                          # crop 파일을 새 class dir 로 이동
            _arr = handler.Load(_sroot, sid, "crop", _crop)
            handler.Delete(_sroot, sid, "crop", _crop)
            ref.info["crop"] = handler.Save(
                _sroot, sid, "crop",
                Data_Ref(type="image", format="png", info={"dir": new_class}), _arr)
        Set_attr(ref, "class_id", new_class)
        _new_stem = self._sset.Bucket(WORKING).setdefault(new_class, Data_Ref(type="stem", info={}))
        _new_stem.info[sid] = ref
        store_io.Save_item(self._sset, new_class)      # 두 class 사이드카만 (증분)
        if _old_stem.info:
            store_io.Save_item(self._sset, old_class)
        else:                                          # 빈 class 는 사이드카·버킷에서 제거
            store_io.Drop(self._sset, WORKING, old_class)
            self._sset.Bucket(WORKING).pop(old_class, None)

    def _log_reassign(self, pipe, entries: list[tuple[str, str, str]]) -> None:
        """재배정 로그를 tasker 폴더 yaml 에 남긴다 — ``{sid: [처음class, 마지막class]}``.

        stem(sample id) 당 한 엔트리다: 처음 재배정이면 ``[원본, 새]`` 로 만들고, 이미 있으면 **처음은
        유지하고 마지막만** 새 class 로 갱신한다(누적 재배정의 원본→최종을 한 줄로 보존).
        """
        _path = pipe.Tasker_root(self._name).parent / _LOG_FILE
        _log: dict = {}
        if _path.exists():
            _ok, _d = Read_from(_path)
            if _ok and isinstance(_d, dict):
                _log = _d
        for _sid, _old, _new in entries:
            if isinstance(_log.get(_sid), list) and len(_log[_sid]) == 2:
                _log[_sid][1] = _new                   # 처음 유지, 마지막 갱신
            else:
                _log[_sid] = [_old, _new]
        Write_to(_path, _log)
