"""id_map 편집기 — params 트리에서 ``id_map`` 을 더블클릭하면 뜨는 표 편집 창.

**params 항목마다 편집 동선이 다르다.** roi 같은 raster 는 캔버스에서 그리는 게 맞지만 id 표는 목록
연산(합치기·지우기·더하기)이라 캔버스에 얹을 게 없다 — 그래서 [수정]의 "편집기로 조준" 대신 전용 창을
연다. 어느 params 가 어느 창을 여는지는 [`_params_panel`](_params_panel.py) 이 정한다.

## 편집은 쌓이고, 적용은 한 번이다

지우기·합치기는 **표만의 일이 아니다** — 그 번호를 든 라벨이 전 stem 에 흩어져 있어서, 한 번의 편집이
수만 개 사이드카를 건드린다. 그래서 창 안에서는 표(``Id_map``)와 ``remap`` 만 메모리로 쌓고, 디스크는
[적용]이 한 번에 친다(실제 실행은 백그라운드 — ``Meta_ops``). 창을 닫으면 쌓은 건 그냥 버려진다.

## 셋의 뜻

- **추가** — 표 끝에 붙는다(번호 = 현재 최대 + 1).
- **삭제** — 표에서 빼고 그 라벨은 **미분류(no_label)로 돌아간다**. 객체가 사라지는 게 아니라 분류
  근거만 걷힌다.
- **병합** — 흡수될 것들은 **목록에서 고르고**, 통합될 하나는 **따로 고른다**(객체 병합처럼 "가장 작은
  번호가 이긴다"로 자동 결정하지 않는다 — 이름이 곧 사람이 읽는 정체라 어느 쪽으로 합칠지가 자동으로
  안 정해진다).

삭제·병합은 **번호를 압축한다** — 빈 자리 뒤가 한 칸씩 당겨지므로 손대지 않은 class 의 번호도 바뀐다
(`core.format.id_map` 이 규칙을 소유). 그 이동 내역은 창이 따로 안 나른다: 쌓인 ``remap`` 이 이미
`{옛 번호: 새 번호}` 전부라, 이력(`from,to,ct` CSV)은 적용 때 `Pipeline` 이 거기서 만든다.

## 사라진 것을 목록에서 지우지 않는다

합치거나 지운 항목을 그냥 빼면 **[적용] 전에 무엇이 어디로 갔는지가 사라진다.** 그래서 목적지 **밑에
접어** 남기고 `적용 후` 칸에 갈 곳을 적는다. 그 줄의 **번호는 비운다** — 압축이 뒤를 당겨 그 자리가 이미
없어졌기 때문이고, 남겨 두면 살아 있는 번호와 헷갈린다. 목적지는 `remap` 에서 읽으므로 사슬(B→A 뒤 A→C)도
저절로 따라간다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.constant import UNCLASSIFIED_ID
from core.format.id_map import Compose, Id_map
from gui.widgets import Class_picker, Pop_dialog, make_tree

_ROLE = Qt.ItemDataRole.UserRole


class Id_map_dialog(Pop_dialog):
    """id 표 편집 — 목록 + 검색 + 추가/삭제/병합. ``exec()`` 후 :meth:`result_edit` 로 결과.

    Attributes:
        table: 편집 중인 표 (제자리에서 고쳐진다 — 취소하면 그냥 버린다).
    """

    def __init__(self, doc: dict | None, stats: tuple | None = None, parent=None) -> None:
        """Args:
        doc:   정본 params 의 id_map 문서 (호출번호 키 dict).
        stats: ``((표본 수, 겹침), 제안들)`` — 분석 산출물에서 온 **관찰과 제안**. 없으면 표만 보인다.
        """
        super().__init__("id_map 편집", size=(680, 700), parent=parent)
        (self._counts, self._overlap), self._hints = stats if stats else (({}, {}), [])
        self.table = Id_map.Restore(doc)
        # 읽을 수 없어 버려진 줄 — 적용하면 파일에서 **사라지므로** 세어 두고 알린다(편집으로 안 변한다).
        self._dropped = len(doc or {}) - len(self.table.entries)
        self._remap: dict[int, int] = {}
        # 표에서 빠졌지만 **적용 전까지 목록에 남겨 보여줄** 것들 — `{원래 번호: 그때의 이름}`.
        # 원래 번호를 키로 잡는 건 `_remap` 의 키 공간이 그것이라서다(합성이 목적지를 계속 최신으로 끌고 간다).
        self._removed: dict[int, str] = {}
        self._origin = {id(_e): _e.id_num for _e in self.table.entries}   # 편집 전 번호 (객체 정체성으로)
        self._build()
        self._reload()

    # ── 결과 ──────────────────────────────────────────────────────────────────
    def result_edit(self) -> tuple[Id_map, dict[int, int]]:
        """``(새 표, remap)`` — 상위가 그대로 ``Pipeline.Apply_class_map`` 에 넘긴다."""
        return self.table, dict(self._remap)

    # ── 구성 ──────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        _w = QWidget()
        _l = QVBoxLayout(_w)
        _l.setContentsMargins(0, 0, 0, 0)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("이름·번호 검색…")
        self._filter.textChanged.connect(self._populate)
        _l.addWidget(self._filter)

        self._tree = make_tree(headers=["번호", "이름", "표본", "부속", "적용 후"],
                               resize=[QHeaderView.ResizeToContents,
                                       QHeaderView.Stretch,
                                       QHeaderView.ResizeToContents,
                                       QHeaderView.ResizeToContents,
                                       QHeaderView.ResizeToContents],
                               alternating=True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        _l.addWidget(self._tree, stretch=1)

        if self._hints:
            _l.addWidget(QLabel("정리 제안 — **후보일 뿐이다.** 겹친다는 건 '같은 물건' 이 아니라 "
                                "'이 잣대로 안 갈린다' 는 뜻이다"))
            self._hint_list = QListWidget()
            self._hint_list.setMaximumHeight(120)
            self._hint_list.itemDoubleClicked.connect(self._on_hint)
            for _h in self._hints:
                _mark = "◆ 강함" if _h.level == "strong" else "◇ 약함"
                _it = QListWidgetItem(
                    f"{_mark}   {' + '.join(self._label_of(_c) for _c in _h.classes)}   "
                    f"n={_h.n:,}   {_h.why}")
                _it.setData(Qt.ItemDataRole.UserRole, _h)
                _it.setToolTip("더블클릭 = 이 둘을 목록에서 고른다 (합칠지는 직접 정한다)")
                self._hint_list.addItem(_it)
            _l.addWidget(self._hint_list)

        _tool = QHBoxLayout()
        self._add_btn = QPushButton("+ 추가")
        self._add_btn.setToolTip("새 class 를 더한다 — 번호는 늘 max+1 (지운 번호는 재사용 안 한다)")
        self._add_btn.clicked.connect(self._on_add)
        self._del_btn = QPushButton("✕ 삭제")
        self._del_btn.setToolTip("고른 class 를 표에서 뺀다 — 그 라벨은 미분류(no_label)로 돌아간다")
        self._del_btn.clicked.connect(self._on_delete)
        self._merge_btn = QPushButton("⧉ 병합…")
        self._merge_btn.setToolTip("고른 class 들을 하나로 합친다 — 통합될 class 는 따로 고른다")
        self._merge_btn.clicked.connect(self._on_merge)
        for _b in (self._add_btn, self._del_btn, self._merge_btn):
            _tool.addWidget(_b)
        _tool.addStretch(1)
        _l.addLayout(_tool)

        self._status = QLabel()
        self._status.setWordWrap(True)
        _l.addWidget(self._status)

        self._set_body(_w)
        _box = self._bottom_bar(buttons=QDialogButtonBox.StandardButton.Apply
                                | QDialogButtonBox.StandardButton.Cancel,
                                on_reject=self.reject)
        self._apply_btn = _box.button(QDialogButtonBox.StandardButton.Apply)
        self._apply_btn.setText("적용")
        self._apply_btn.clicked.connect(self._on_apply)

    # ── 표시 ──────────────────────────────────────────────────────────────────
    def _reload(self) -> None:
        self._populate(self._filter.text())
        self._sync_status()

    def _populate(self, text: str = "") -> None:
        """살아 있는 항목 + 그 아래에 **접혀 들어갈 것들**을 함께 그린다.

        사라진 항목을 목록에서 그냥 빼면 무엇이 어디로 갔는지가 [적용] 전에 사라진다. 그래서 목적지 밑에
        **번호를 비운 채** 남기고 ``적용 후`` 칸에 갈 곳을 적는다 — 번호를 비우는 건 그 자리가 이미 없어져서다
        (압축이 뒤를 당겼다). 이 줄들은 고를 수 없다(다음 편집의 대상이 아니다).
        """
        _t = text.strip().lower()
        self._tree.clear()
        _folded = self._folded()
        for _e in self.table.Sorted():
            _kids = _folded.get(_e.id_num, [])
            if _t and not self._hit(_t, _e.id_name, _e.id_num) \
                    and not any(self._hit(_t, _n, _o) for _o, _n in _kids):
                continue
            _extra = " · ".join(f"{_k}={_v}" for _k, _v in _e.extra.items())
            _item = QTreeWidgetItem(self._tree,
                                    [str(_e.id_num), _e.id_name, self._samples(_e.id_num),
                                     _extra, ""])
            _item.setData(0, _ROLE, _e.id_num)
            _item.setToolTip(2, self._overlap_tip(_e.id_num))
            for _old, _name in _kids:
                _kid = QTreeWidgetItem(_item, ["", f"{_name} (원래 {_old})", "", "",
                                               f"→ {_e.id_name}({_e.id_num})"])
                _kid.setDisabled(True)          # 이미 없는 것 — 다음 편집의 대상이 될 수 없다
        for _dest, _kids in _folded.items():    # 목적지가 표에 없다 — 있으면 안 되지만 숨기지는 않는다
            if self.table.Get(_dest) is None:
                for _old, _name in _kids:
                    QTreeWidgetItem(self._tree, ["", f"{_name} (원래 {_old})", "", "",
                                                 f"→ ?({_dest})"]).setDisabled(True)
        self._tree.expandAll()

    def _label_of(self, num) -> str:
        """class **번호** → ``이름(번호)`` — 관찰·제안이 드는 것은 번호고 사람이 아는 것은 이름이다."""
        _e = self.table.Get(int(num)) if str(num).lstrip("-").isdigit() else None
        return f"{_e.id_name}({num})" if _e is not None else str(num)

    def _samples(self, num: int) -> str:
        """그 class 를 쓰는 표본 수 — **관찰이다.** 0 이라고 지울 것이 아니라 아직 못 찍은 것일 수 있다.

        **번호로 찾는다.** 표본이 든 것은 ``class_id`` 라 관찰(:func:`~core.analysis.class_usage`)의
        키가 번호 문자열이다 — 이름으로 찾으면 전부 0 이 나와 "아무 객체도 없다" 로 읽힌다.
        """
        if not self._counts:
            return ""
        return f"{self._counts.get(str(num), 0):,}"

    def _overlap_tip(self, num: int) -> str:
        """겹침 요약 — 그 class 의 표본 중 몇 건이 어느 class 와 같은 type 에 들었나 (많은 순)."""
        _row = self._overlap.get(str(num)) or {}
        if not _row:
            return ""
        _top = sorted(_row.items(), key=lambda _kv: -_kv[1])[:6]
        return ("같은 type 에 든 표본 (이 class 기준):\n"
                + "\n".join(f"  {self._label_of(_o)}  {_n:,}" for _o, _n in _top))

    def _on_hint(self, item) -> None:
        """제안 더블클릭 → 그 두 class 를 목록에서 **고르기만** 한다 (합치기는 사람이 누른다).

        제안이 든 것은 **번호**라 줄의 번호(``_ROLE``)와 맞춘다 — 이름 칸과 맞추면 늘 빗나간다.
        """
        _h = item.data(Qt.ItemDataRole.UserRole)
        _want = {str(_c) for _c in getattr(_h, "classes", ())}
        self._filter.clear()
        self._tree.clearSelection()
        for _i in range(self._tree.topLevelItemCount()):
            _it = self._tree.topLevelItem(_i)
            if str(_it.data(0, _ROLE)) in _want:
                _it.setSelected(True)
                self._tree.scrollToItem(_it)

    def _folded(self) -> dict[int, list[tuple[int, str]]]:
        """``{목적지 번호: [(원래 번호, 이름)…]}`` — 적용 대기 중인 병합·삭제를 목적지별로 묶는다.

        목적지는 ``_remap`` 에서 읽는다 — 합성이 사슬(B→A 뒤 A→C)과 압축 이동을 이미 반영해 두므로
        여기서 되짚을 게 없다.

        **없으면 미분류가 아니라 제자리다** — ``remap`` 은 옮길 필요가 없는 것을 생략하므로(``Compose`` 가
        ``옛 == 새``를 떨군다), 빠진 키는 "그 번호 그대로"라는 뜻이다. 실제로 그런다: A(1)를 C 로 합쳤는데
        압축이 C 를 1 로 당기면 라벨값 1 은 안 움직이고 뜻만 A → C 로 바뀐다.
        """
        _out: dict[int, list[tuple[int, str]]] = {}
        for _old, _name in sorted(self._removed.items()):
            _out.setdefault(self._remap.get(_old, _old), []).append((_old, _name))
        return _out

    @staticmethod
    def _hit(text: str, name: str, num: int) -> bool:
        return text in name.lower() or text in str(num)

    def _sync_status(self) -> None:
        """대기 중인 편집을 한 줄로 — 적용이 **무엇을 건드리는지**가 눌리기 전에 보여야 한다."""
        _msg = [f"{len(self.table.entries)} 항목"]
        if self._dropped > 0:
            _msg.append(f"⚠ 읽을 수 없는 줄 {self._dropped} 개 — 적용하면 파일에서 사라진다")
        if self._remap:
            _to_none = sum(1 for _v in self._remap.values() if _v == UNCLASSIFIED_ID)
            _msg.append(f"대기: 번호 {len(self._remap)} 개 재배정"
                        + (f" (미분류로 {_to_none} 개)" if _to_none else ""))
        self._status.setText("  ·  ".join(_msg))
        self._apply_btn.setEnabled(True)

    def _selected(self) -> list[int]:
        return [_it.data(0, _ROLE) for _it in self._tree.selectedItems()
                if _it.data(0, _ROLE) is not None]

    def _choices(self, exclude: set[int] | None = None) -> dict[str, str]:
        """``Class_picker`` 용 ``{이름: 번호}`` — 값이 문자열인 건 picker 규약이다."""
        return {_e.id_name: str(_e.id_num) for _e in self.table.Sorted()
                if not exclude or _e.id_num not in exclude}

    # ── 편집 셋 — 표를 고치고 remap 을 쌓는다 ───────────────────────────────────
    def _edit(self, fn) -> None:
        """편집 하나를 적용하고 remap 을 **합성**해 쌓는다 — 실패는 그대로 드러낸다(표는 안 바뀐다).

        합성이 필요한 이유: 5 를 3 으로 합친 뒤 3 을 지우면 5 도 미분류로 가야 한다(``Compose``).

        표에서 빠진 항목은 :attr:`_removed` 에 담아 목록에 계속 보인다 — **객체 정체성**으로 가려낸다.
        번호로 비교하면 압축이 번호를 옮긴 뒤라 누가 빠졌는지 알 수 없다.
        """
        _before = {id(_e): _e for _e in self.table.entries}
        try:
            _remap = fn()
        except ValueError as _e:
            QMessageBox.warning(self, "id_map 편집", str(_e))
            return
        _alive = {id(_e) for _e in self.table.entries}
        for _key, _entry in _before.items():
            if _key not in _alive and _key in self._origin:   # 이번에 안 뺀 것·새로 더했다 뺀 것은 제외
                self._removed[self._origin[_key]] = _entry.id_name
        if _remap:
            self._remap = Compose(self._remap, _remap)
        self._reload()

    def _label(self, id_num: int) -> str:
        """``이름(번호)`` — 확인 문구에서 쓰는 표기 (편집 **전**에 불러야 이름이 맞다)."""
        _e = self.table.Get(id_num)
        return f"{_e.id_name}({id_num})" if _e is not None else f"?({id_num})"

    def _on_add(self) -> None:
        _dlg = _Add_class_dialog(self)
        if not _dlg.exec():
            return
        _name, _category = _dlg.result_spec()

        def _add() -> dict[int, int]:
            self.table.Add(_name, {"category_id": _category})
            return {}                       # 추가는 기존 라벨이 가리키는 걸 안 바꾼다 → remap 없음
        self._edit(_add)

    def _on_delete(self) -> None:
        _ids = self._selected()
        if not _ids:
            return
        self._edit(lambda: self.table.Delete(_ids))

    def _on_merge(self) -> None:
        """고른 것들을 흡수 대상으로, 통합될 하나는 **따로** 고른다 (후보에서 흡수 대상은 뺀다)."""
        _ids = self._selected()
        if not _ids:
            QMessageBox.information(self, "병합", "합칠 class 를 목록에서 고르세요.")
            return
        _picker = Class_picker(self._choices(exclude=set(_ids) | {UNCLASSIFIED_ID}),
                               title=f"병합 — {len(_ids)} 개를 흡수할 class 선택", parent=self)
        if not _picker.exec():
            return
        _into = _picker.selected()
        if _into is None:
            return
        self._edit(lambda: self.table.Merge(int(_into), _ids))

    # ── 적용 ──────────────────────────────────────────────────────────────────
    def _on_apply(self) -> None:
        """적용 전에 **무엇이 움직이는지** 한 번 묻는다 — 되돌리기가 없는 dataset-wide 변경이라서다."""
        if QMessageBox.question(
                self, "id_map 적용",
                f"표를 {len(self.table.entries)} 항목으로 바꾸고, "
                f"번호 {len(self._remap)} 개를 쓰는 전 stem 의 라벨을 다시 씁니다.\n\n"
                "삭제·병합은 뒤의 번호를 당기므로 손대지 않은 class 의 번호도 바뀝니다 "
                "— 기존 체크포인트는 그 지점부터 다시 학습해야 합니다.\n"
                "정본에 바로 쓰이고 [되돌리기]로 취소되지 않습니다. 계속할까요?") \
                != QMessageBox.StandardButton.Yes:
            return
        self.accept()


class _Add_class_dialog(Pop_dialog):
    """새 class 입력 — 이름 + 부속 칸. **번호는 안 받는다**(표가 max+1 로 정한다)."""

    def __init__(self, parent=None) -> None:
        super().__init__("class 추가", parent=parent)
        _w = QWidget()
        _form = QFormLayout(_w)
        self._name = QLineEdit()
        self._name.setPlaceholderText("10D132000NT9")
        _form.addRow("이름", self._name)
        self._category = QSpinBox()
        self._category.setRange(0, 1 << 20)
        self._category.setToolTip("상위 분류 — LENS 는 값을 만들지 않고 나르기만 한다")
        _form.addRow("category_id", self._category)
        self._set_body(_w)
        self._bottom_bar(buttons=QDialogButtonBox.StandardButton.Ok
                         | QDialogButtonBox.StandardButton.Cancel,
                         on_accept=self.accept, on_reject=self.reject)

    def result_spec(self) -> tuple[str, int]:
        """``(이름, category_id)``."""
        return self._name.text().strip(), self._category.value()
