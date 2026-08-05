"""tasker 하나의 sample 편집 뷰(임베드 위젯) — class 트리 + crop 미리보기 + class 재배정.

파생 ``Sample_Set``(``pipeline.Load_sample(name)``)을 읽어 보여준다. store 의 **범주는 split**(train/val/
test)이고 sample 이 곧 item 이다. **class 는 구조가 아니라 sample 의 ``class_id`` attr** 이므로, 트리의
class 그룹은 **표시용 group-by** 일 뿐 저장 구조가 아니다(split 은 컬럼으로 보인다).

sample 은 정본의 순수 역참조라 미리보기는 **crop payload(있으면)** 또는 **정본 프레임**으로 그린다.

**class 재배정 = attr 갱신 두 줄이다.** class 가 경로에 안 들어가므로 **파일이 안 움직인다** — 옛 모델은
class 가 폴더라 재배정이 crop 재저장 + 옛 파일 삭제 + 노드 이동 + 사이드카 2개 rewrite 였다. 지금은
sample 의 ``class_id`` attr 를 고치고(파생) 정본 obj 의 ``class_id`` 도 고친다(write-back). **재배정
로그**(``{sid: [처음class, 마지막class]}``)는 tasker 폴더 yaml 에 남긴다.

geometry(mask)는 여기서 안 건드린다(정본 뷰의 ``Data_view`` 소유). ``Tasker_tab`` 이 이 위젯을 호스트한다.
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

import cv2
import numpy as np

from core.constant import UNCLASSIFIED_ID
from core.schema import Data_Ref
from gui.widgets import Class_picker
from gui.widgets import Image_label

_ROLE = Qt.ItemDataRole.UserRole   # sample 항목 식별 (sample_id — split 무관 유일 key)
_LOG_FILE = "reassign_log.yaml"    # tasker 폴더 재배정 로그 ({sid: [처음, 마지막]})


def _merged_base(meta, stem: str) -> np.ndarray | None:
    """정본 stem 의 ``image`` leaf 들을 평균 블렌딩한 base BGR — crop 없을 때 미리보기용.

    **화이트리스트다** — base 가 될 자격은 `image` 도메인에만 있다. 한때 `segmap` 만 제외하는
    블랙리스트였는데, 그 도메인이 사라지면서(라벨맵→객체 mask) 조건이 아무것도 안 걸러 프레임 레벨
    `mask` 가 base 에 섞였다. 도메인이 늘 때 조용히 새는 쪽은 블랙리스트다.

    payload 는 ``meta.Load(stem, key)`` 에 요청한다(경로는 store 가 안다). 없으면 None.
    """
    _frame = meta.Find(stem)
    if _frame is None:
        return None
    _imgs: list[np.ndarray] = []
    for _key, _ref in _frame.Leaves().items():
        if _ref.format[:1] != ("image",):               # base 가 될 자격은 image 도메인에만
            continue
        _val = meta.Load(stem, _key)
        if isinstance(_val, np.ndarray) and _val.ndim >= 2:
            _imgs.append(_val if _val.ndim == 3 else cv2.cvtColor(_val, cv2.COLOR_GRAY2BGR))
    if not _imgs:
        return None
    if len(_imgs) == 1:
        return _imgs[0]
    _h, _w = _imgs[0].shape[:2]
    _acc = np.zeros((_h, _w, 3), np.float32)
    for _im in _imgs:
        _acc += (cv2.resize(_im, (_w, _h)) if _im.shape[:2] != (_h, _w) else _im).astype(np.float32)
    return (_acc / len(_imgs)).astype(np.uint8)


class Sample_view(QWidget):
    """tasker 하나의 group→sample 트리 + crop 미리보기 + 다중선택 class 재배정 (write-back) 위젯.

    Attributes:
        meta_changed: class write-back 으로 정본이 바뀌었을 때 emit (상위 meta 뷰 갱신용).
        stem_focus_requested: frame 뷰(detection·seg)에서 stem 을 고르면 emit — 메인 meta 뷰어를
            그 정본 프레임으로 조준한다(정본 뷰어가 이미 객체·segment 를 그린다).
    """

    meta_changed = Signal()
    stem_focus_requested = Signal(str)

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
        self._tree.setHeaderLabels(["sample", "split"])   # class 는 그룹 노드 (attr group-by)
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
        self._hint = QLabel("트리에서 sample 을 (다중)선택하고 우클릭 → class 재배정")
        self._hint.setStyleSheet("color: #888;")
        self._hint.setWordWrap(True)
        _rl.addWidget(self._hint)
        _split.addWidget(_right)
        _split.setStretchFactor(1, 1)
        _split.setSizes([320, 600])
        _lay.addWidget(_split, stretch=1)

    # ── Public ─────────────────────────────────────────────────────────────────
    def set_editable(self, editable: bool) -> None:
        """편집 잠금 토글 — 잠그면 재배정(우클릭 메뉴)만 막고 트리 보기·미리보기는 유지한다."""
        self._editable = editable

    # ── 채우기 ─────────────────────────────────────────────────────────────────
    def reload(self, keep: str | None = None) -> None:
        """tasker 의 ``Sample_Set`` 을 다시 읽어 트리를 채운다 (``keep`` = 유지할 sample id).

        **뷰 모양은 task 가 가른다** — 파생이 새 도메인을 만드나(classification=per-object crop)로 갈린다:
        crop 은 sample 이 소유한 새 데이터라 class-그룹 트리 + 재배정이 맞고, detection·seg 는 정본 프레임
        재표현(참조)이라 frame 마다 객체가 달라 class-그룹이 안 맞는다 → split→stem 목록 + 정본 뷰어 조준.
        """
        _pipe = self._get_pipeline()
        self._tree.clear()
        if _pipe is None:
            return
        self._sset = _pipe.Load_sample(self._name)
        self._task = _pipe.Taskers().get(self._name, {}).get("task", "classification")

        if self._task == "classification":
            self._tree.setHeaderLabels(["sample", "split"])   # class 는 그룹 노드 (attr group-by)
            self._hint.setText("트리에서 sample 을 (다중)선택하고 우클릭 → class 재배정")
            self._reload_by_class(keep)
        else:
            self._tree.setHeaderLabels(["stem (정본 프레임)", "split"])
            self._hint.setText("stem 을 고르면 메인 meta 뷰어가 그 정본 프레임으로 조준한다 — 객체·segment 는 거기서 편집")
            self._reload_by_split(keep)

    def _reload_by_class(self, keep: str | None) -> None:
        """classification — class(attr) 그룹 → sample. 저장 구조는 split 이고 class 는 표시용 group-by 다."""
        _by_class: dict[str, list[tuple[str, str]]] = {}          # class 이름 → [(sid, split)]
        _names = self._class_names()                              # 저장은 번호, 표시는 이름
        for _split in self._sset.CATEGORIES:
            for _sid, _ref in self._sset.Bucket(_split).items():
                _cls = _names.get(_ref.Attr("class_id") or str(UNCLASSIFIED_ID), "?")
                _by_class.setdefault(_cls, []).append((_sid, _split))

        _target = None
        for _cls, _items in sorted(_by_class.items()):
            _gnode = QTreeWidgetItem([_cls, str(len(_items))])
            self._tree.addTopLevelItem(_gnode)
            for _sid, _split in sorted(_items):
                _it = QTreeWidgetItem([_sid, _split])
                _it.setData(0, _ROLE, _sid)
                _gnode.addChild(_it)
                if keep is not None and _sid == keep:
                    _target = _it
            _gnode.setExpanded(True)
        if _target is not None:
            self._tree.setCurrentItem(_target)

    def _reload_by_split(self, keep: str | None) -> None:
        """detection·seg — split → stem(정본 프레임) 목록. class-그룹이 아니다(frame 마다 객체가 달라 안 맞음).

        sample 은 정본 순수 역참조라 여기선 편집하지 않는다 — stem 선택이 메인 meta 뷰어를 조준한다.
        """
        _target = None
        for _split in self._sset.CATEGORIES:
            _items = sorted(self._sset.Bucket(_split).items())
            _snode = QTreeWidgetItem([_split, str(len(_items))])
            self._tree.addTopLevelItem(_snode)
            for _sid, _ref in _items:
                _it = QTreeWidgetItem([_ref.Attr("source_stem") or _sid, _split])
                _it.setData(0, _ROLE, _sid)
                _snode.addChild(_it)
                if keep is not None and _sid == keep:
                    _target = _it
            _snode.setExpanded(True)
        if _target is not None:
            self._tree.setCurrentItem(_target)

    # ── 선택 → 미리보기 ─────────────────────────────────────────────────────────
    def _on_select(self, item: QTreeWidgetItem | None, _prev=None) -> None:
        _sid = item.data(0, _ROLE) if item is not None else None
        if _sid is None:                                # class 그룹 노드 — 미리보기 비움
            self._img.clear_image("sample 을 선택하세요")
            self._info.setText("")
            return
        _ref = self._sample_ref(_sid)
        if _ref is None:
            return
        self._show_preview(_sid, _ref)
        if self._task != "classification":              # frame 뷰 — 메인 meta 뷰어로 조준(여기선 편집 안 함)
            _stem = _ref.Attr("source_stem") or _sid
            self.stem_focus_requested.emit(_stem)
            self._info.setText(f"정본 프레임 '{_stem}'  ·  split={self._sset.Category_of(_sid)}\n"
                               "메인 뷰어에서 객체·segment 를 편집하세요 (여기선 참조만)")
            return
        _src = _ref.Attr("source_stem")
        _obj = _ref.Attr("source_obj")
        _has_crop = _ref.Get("crop") is not None
        self._info.setText(
            f"class={self._class_names().get(_ref.Attr('class_id') or str(UNCLASSIFIED_ID), '?')}"
            f"  ·  split={self._sset.Category_of(_sid)}\n"
            f"source: {_src}" + (f" · obj {_obj}" if _obj else "")
            + ("  ·  crop 실체화됨" if _has_crop else "  ·  crop 없음(정본 프레임 역참조)"))

    def _show_preview(self, sid: str, ref: Data_Ref) -> None:
        """crop payload(있으면) 또는 정본 프레임(역참조)을 미리보기에 그린다."""
        _arr = self._sset.Load(sid, "crop")             # 경로는 store 가 파생 (split 무관)
        if _arr is not None:
            self._img.set_image(_arr)
            return
        _pipe = self._get_pipeline()
        _src = ref.Attr("source_stem")
        _meta = _pipe.meta if _pipe is not None else None
        if _meta is not None and _src and _meta.Has(_src):
            _img = _merged_base(_meta, _src)
            if _img is not None:
                self._img.set_image(_img)
                return
        self._img.clear_image("미리보기 없음 (crop·정본 프레임 모두 없음)")

    def _sample_ref(self, sid: str) -> Data_Ref | None:
        """sample id 로 live sample 을 찾는다 — split 이 어디든 store 가 안다 (reload 후에도 stale 없이)."""
        return None if self._sset is None else self._sset.Find(sid)

    # ── class 재배정 (우클릭 메뉴 + 다중선택 + id_map picker + write-back + 로그) ──
    def _on_menu(self, pos) -> None:
        """트리 우클릭 — 선택(또는 우클릭) sample 들을 class 재배정하는 메뉴를 연다."""
        if not self._editable or self._task != "classification":
            return
        _targets = [_it.data(0, _ROLE) for _it in self._tree.selectedItems()
                    if _it.data(0, _ROLE) is not None]         # sample 만 (class 그룹 제외)
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

    def _reassign(self, targets: list[str]) -> None:
        """``targets``(sample id 목록)를 id_map picker 로 고른 class 로 일괄 재배정 + 로그.

        **파일은 안 움직인다** — class 가 경로에 안 들어가므로(attr) 재배정은 attr 갱신뿐이다:
        파생 sample 의 ``class_id`` + 정본 obj 의 ``class_id``(write-back). split 도 안 바뀐다
        (split 은 빌드가 정한 데이터셋 정체성이라 class 와 독립이다).
        """
        _pipe = self._get_pipeline()
        if _pipe is None:
            return
        _picker = Class_picker(_pipe.Class_choices(), parent=self)   # 미분류(no_label, 0)도 후보다
        if not _picker.exec():
            return
        _new = _picker.selected()
        if _new is None:
            return
        _entries: list[tuple[str, int, int]] = []          # (sid, 원본class_id, 새class_id)
        for _sid in targets:
            _ref = self._sample_ref(_sid)
            if _ref is None:
                continue
            _old = _ref.Attr("class_id") or UNCLASSIFIED_ID
            if _new == _old:
                continue
            if not self._writeback_class(_pipe, _ref, _new):   # 정본 (실패하면 파생도 안 건드린다)
                continue
            _ref.Set_attr("class_id", _new)                    # 파생 — 이게 재배정의 전부다
            self._sset.Save(_sid)                              # 그 sample 사이드카만 (증분)
            _entries.append((_sid, _old, _new))
        if not _entries:
            return
        self._log_reassign(_pipe, _entries)
        self.reload(keep=_entries[-1][0])
        self.meta_changed.emit()

    def _class_names(self) -> dict[str, str]:
        """표시용 ``{class_id: 이름}`` — 저장된 건 번호뿐이라 이름은 정본 id_map 에서 얻는다."""
        _pipe = self._get_pipeline()
        return _pipe.Class_names() if _pipe is not None else {}

    def _writeback_class(self, pipe, ref: Data_Ref, new_class: int) -> bool:
        """정본 obj(source 역참조)의 ``class_id`` 를 고치고 그 stem 사이드카만 저장한다 (인라인 attr only)."""
        _src = ref.Attr("source_stem")
        _obj = ref.Attr("source_obj")
        _frame = pipe.meta.Find(_src) if _src else None
        if _frame is None:
            QMessageBox.warning(self, "재배정", f"정본에서 source stem '{_src}' 를 찾지 못했습니다.")
            return False
        _target = _frame.Get(_obj) if _obj else _frame
        if _target is None:
            QMessageBox.warning(self, "재배정", f"source obj '{_obj}' 를 찾지 못했습니다.")
            return False
        _target.Set_attr("class_id", new_class)      # 정본 write-back (인라인 attr)
        pipe.meta.Save(_src)
        return True

    def _log_reassign(self, pipe, entries: list[tuple[str, int, int]]) -> None:
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
