"""gui 공용 위젯 구조 검증 — 패키지 분리/이름 승격/중복 list editor 통합 회귀 테스트.

프로젝트 루트(LENS) 에서 실행 (헤드리스 — offscreen 플랫폼을 자동 설정)::

    python gui/test_widgets.py

검증 대상:
  1. import smoke — ``gui.widgets`` 패키지 + 이번에 손댄 gui 모듈이 rename 누락 없이 import 되는지
  2. 공개 API — ``gui.widgets`` 가 public 이름(Path_row/Image_label/drop/List_row …)을 노출하는지
  3. ``List_editor`` 베이스 — dict 직렬화(``to_config``/``load``) 왕복
  4. ``Pair_list_editor`` — list 직렬화(``pairs``/``set_pairs``/``append``) 왕복
  5. 도메인 에디터 — ``_Glob_list_editor``/``_Outputs_editor`` 가 베이스 위에서 왕복되는지
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# PySide6 import 전에 헤드리스 플랫폼 지정 (디스플레이 없이 위젯 생성 가능)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    """프로세스당 하나의 ``QApplication`` 을 보장한다 (위젯 생성 전제)."""
    return QApplication.instance() or QApplication([])


# ── 1. import smoke ──────────────────────────────────────────────────────────

def test_import_widgets_package() -> None:
    import gui.widgets as w
    # 패키지 분리 후에도 공개 이름이 그대로 노출돼야 한다
    for _name in ("Image_label", "Path_row", "Float_slider_row", "Int_slider_row",
                  "drop", "reorder", "List_row", "List_editor", "Pair_list_editor",
                  "Pop_dialog", "make_tree", "set_bold"):
        assert hasattr(w, _name), f"gui.widgets 에 {_name} 없음"


def test_import_touched_modules() -> None:
    # rename/이동이 모든 사용처에 반영됐는지 — NameError/ImportError 로 깨지면 여기서 잡힌다
    import importlib
    for _mod in ("gui._io", "gui._meta_tree", "gui.form", "gui.page",
                 "gui.converter._panel", "gui.run._dialog", "gui.run._flow_card",
                 "gui.run._sequence", "gui.verify._dialog", "gui.verify._editor",
                 "gui.verify._annotation", "gui.verify._draw", "gui.verify._history",
                 "gui.meta_view._idmap", "gui.meta_view._params", "gui.meta_view._view"):
        importlib.import_module(_mod)


def test_tree_utils_module_removed() -> None:
    # value_node/set_bold 이동 — 옛 meta_view/_tree_utils.py 는 더 없어야 한다
    import importlib
    try:
        importlib.import_module("gui.meta_view._tree_utils")
    except ImportError:
        return
    raise AssertionError("gui.meta_view._tree_utils 가 아직 존재한다 (이동 누락)")


def test_pair_editor_not_in_form() -> None:
    # Pair_list_editor 는 widgets 로 이동 — form 에는 더 없어야 한다
    import gui.form as _form
    assert not hasattr(_form, "_Pair_list_editor")


# ── 2. List_editor 베이스 (dict 직렬화 왕복) ──────────────────────────────────

def test_list_editor_dict_roundtrip() -> None:
    from gui.widgets import List_editor, List_row
    from PySide6.QtWidgets import QLineEdit, QHBoxLayout

    class _Row(List_row):
        def __init__(self, key="", spec=None, parent=None):
            super().__init__(parent)
            _l = QHBoxLayout(self)
            self._k = QLineEdit(str(key))
            self._v = QLineEdit(str(spec or ""))
            self._k.textChanged.connect(self.changed)
            _l.addWidget(self._k)
            _l.addWidget(self._v)
            _l.addWidget(self._remove_button())

        def to_config(self):
            return self._k.text().strip(), self._v.text().strip()

    class _Editor(List_editor):
        def _make_row(self, key, spec):
            return _Row(key, spec)

    _app()
    _e = _Editor()
    _e.load({"a": "1", "b": "2"})
    assert _e.to_config() == {"a": "1", "b": "2"}
    # load 는 비우고 다시 채운다 (누적 아님)
    _e.load({"c": "3"})
    assert _e.to_config() == {"c": "3"}
    # 빈 key 행은 직렬화에서 제외
    _e._add_row("", "x")
    assert _e.to_config() == {"c": "3"}


# ── 3. Pair_list_editor (list 직렬화 왕복) ────────────────────────────────────

def test_pair_editor_roundtrip() -> None:
    from gui.widgets import Pair_list_editor
    _app()
    _p = Pair_list_editor("params", kind="path")
    _p.set_pairs([("roi", "/a/roi.png"), ("acc", "/a/acc.npy")])
    assert _p.pairs() == [("roi", "/a/roi.png"), ("acc", "/a/acc.npy")]
    _p.append("extra", "/a/x.png")
    assert ("extra", "/a/x.png") in _p.pairs()
    # 중복 key·순서 허용 (dict 아님)
    _p.set_pairs([("k", "1"), ("k", "2")])
    assert _p.pairs() == [("k", "1"), ("k", "2")]


# ── 4. 도메인 에디터 (베이스 상속 후 왕복) ────────────────────────────────────

def test_glob_editor_roundtrip() -> None:
    from gui.converter._panel import _Glob_list_editor
    _app()
    _g = _Glob_list_editor()
    # pattern 만 → 문자열, 추가 키 → dict (행 to_config 규약)
    _src = {"pose": "*_pose.png", "acc": {"pattern": "*.npy", "type": "array"}}
    _g.load(_src)
    assert _g.to_config() == _src


def test_outputs_editor_roundtrip() -> None:
    from gui.run._flow_card import _Outputs_editor
    _app()
    _o = _Outputs_editor()
    _src = {"segment": {"to": "storage", "format": "png", "dir": "seg"}}
    _o.load(_src)
    assert _o.to_config() == _src
    # 기본값(to=meta, level=object)은 생략돼 빈 spec 으로 직렬화
    _o.load({"bbox": {}})
    assert _o.to_config() == {"bbox": {}}


# ── 5. Pop_dialog / make_tree 베이스 ─────────────────────────────────────────

def test_make_tree() -> None:
    from gui.widgets import make_tree
    from PySide6.QtWidgets import QHeaderView
    _app()
    # headers → 컬럼수 + 라벨 + resize mode + alternating
    _t = make_tree(headers=["k", "v"],
                   resize=[QHeaderView.ResizeToContents, QHeaderView.Stretch],
                   alternating=True)
    assert _t.columnCount() == 2
    assert [_t.headerItem().text(_i) for _i in range(2)] == ["k", "v"]
    assert _t.header().sectionResizeMode(1) == QHeaderView.Stretch
    assert _t.alternatingRowColors() is True
    # hidden → 헤더 숨김, columns 로 컬럼수만 지정
    _h = make_tree(columns=2, hidden=True)
    assert _h.columnCount() == 2 and _h.isHeaderHidden() is True


def test_pop_dialog() -> None:
    from gui.widgets import Pop_dialog
    from PySide6.QtWidgets import QDialogButtonBox, QLabel, QPushButton
    _app()

    class _Dlg(Pop_dialog):
        def __init__(self):
            super().__init__("t", size=(320, 240))
            self.body = QLabel("body")
            self._set_body(self.body)
            self.box = self._bottom_bar(left=[QPushButton("save")],
                                        on_reject=self.reject)

    _d = _Dlg()
    assert _d.windowTitle() == "t"
    assert isinstance(_d.box, QDialogButtonBox)
    # body 가 stretch=1 로 본문에 들어갔는지 (레이아웃에 위젯 존재)
    assert _d.body.parent() is _d


# ── 6. Main_page (폴더 분리 + 프로필 요약 라벨) ──────────────────────────────

def test_main_page_profile_label() -> None:
    from gui.page import Main_page
    _app()
    _p = Main_page()
    assert "없음" in _p._profile_label.text()                 # 초기: 프로필 없음
    _p._flows = [{"name": "chroma"}, {"object_type": "separate"}]
    _p._update_profile_label()
    _t = _p._profile_label.text()
    assert "2 flow" in _t and "chroma" in _t and "separate" in _t


# ── 7. verify 분해 (Edit_history 스택 — Qt 무관 순수 로직) ─────────────────────

def test_edit_history() -> None:
    from gui.verify._history import Edit_history
    _v = {"n": 0}
    _applied: list = []
    _h = Edit_history(lambda: _v["n"], lambda s: _applied.append(s))
    _h.reset()                       # 스냅샷 [0]
    _v["n"] = 1; _h.commit()         # [0,1]
    _v["n"] = 2; _h.commit()         # [0,1,2], idx=2
    _h.undo();  assert _applied[-1] == 1
    _h.undo();  assert _applied[-1] == 0
    _h.undo();  assert _applied[-1] == 0          # 맨 앞 → no-op (적용 변화 없음)
    _h.redo();  assert _applied[-1] == 1
    # undo 후 commit 하면 redo 꼬리가 잘린다
    _v["n"] = 9; _h.commit()         # idx=1 에서 [0,1,9]
    _h.redo();  assert _applied[-1] == 1          # 더 갈 곳 없음(끝) → 변화 없음


def main() -> int:
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
