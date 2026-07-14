"""gui surface 검증 — **실제로 그려지는가**. 산문이 아니라 실행으로 지킨다.

gui 는 core 의 도메인 타입(`Data_Ref`·`Dataset_Meta`)을 **여러 위젯이 직접** 쓴다(단일 seam 이 없다 —
[`TODO.md`](TODO.md)). 그래서 core API 가 바뀌면 파급이 한 곳에 모이지 않고, **grep sweep 은 패턴에 없던
호출을 놓친다** — 실제로 `meta.params` 가 그렇게 살아남아 root 를 여는 순간 죽었다.

**컴파일도 import 도 그걸 못 잡는다.** 죽은 API 는 그 줄이 *실행될 때* 터진다. 그래서 여기서는 offscreen
으로 **모든 surface 를 실제로 띄우고 핵심 경로를 태운다.** 이 파일이 통과하는 한 gui 는 뜬다.

실행: ``python gui/test_surfaces.py`` (또는 pytest 가 있으면 ``pytest gui/test_surfaces.py``).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from core import Pipeline, Pipeline_config
from core.constant import MODIFIED, STAGED
from core.process.func.mask.instance import Erase, Merge_into

_CONVERTER = {"globs": {"frame": {"pattern": "img_*", "ext": "png", "type": "image"}}}
_FLOWS = [{
    "object_type": "extract", "unit": "frame",
    "processes": [
        {"object_type": "detect_edge"},
        {"object_type": "fill_edge"},
        {"object_type": "split_objects",
         "outputs": {"segment": {"to": "storage", "level": "frame", "type": "segmap"}}},
    ],
}]
_SAMPLE = {"unit": "object", "task": "classification",
           "processes": [{"object_type": "frame_crop"}]}

_STATE: dict = {}


def _pipe() -> Pipeline:
    """정본·파생이 다 찬 Pipeline (모듈당 1회) — **두 범주를 섞어** 둔다.

    상태 뱃지·범주별 경로 파생을 다 태우려면 modified/staged 가 함께 있어야 한다.
    """
    if "pipe" in _STATE:
        return _STATE["pipe"]
    _STATE["app"] = QApplication.instance() or QApplication([])
    _tmp = Path(tempfile.mkdtemp(prefix="lens_gui_test_"))
    _STATE["tmp"] = _tmp
    _raw, _ds = _tmp / "raw", _tmp / "ds"
    _raw.mkdir(parents=True)
    for _i in range(3):
        _img = np.zeros((90, 120, 3), np.uint8)
        cv2.rectangle(_img, (12 + _i, 12), (50 + _i, 50), (230, 230, 230), -1)
        cv2.rectangle(_img, (80, 55), (110, 80), (210, 210, 210), -1)
        cv2.imwrite(str(_raw / f"img_{_i:03d}.png"), _img)

    _p = Pipeline(Pipeline_config(
        dataset_root=str(_ds), converter={**_CONVERTER, "sources": [str(_raw)]},
        flows=_FLOWS, sample=_SAMPLE))
    _p.Convert()
    _p.Run()
    for _s in list(_p.meta.Bucket(MODIFIED)):
        _p.meta.Move(_s, STAGED)
    _p.meta.Move(sorted(_p.meta.Bucket(STAGED))[0], MODIFIED)   # 범주를 섞는다
    _p.Sample("cls")
    _STATE["pipe"] = _p
    return _p


# ── surface 들 ────────────────────────────────────────────────────────────────

def test_main_page_opens_root() -> None:
    """root 열기 → meta 뷰 refresh (stem 목록 + params 패널). `meta.params` 가 여기서 터졌었다."""
    from gui.app._main import Main_page
    _p = _pipe()
    _m = Main_page()
    _m._set_root(str(_p.root))
    assert _m._pipeline is not None


def test_meta_view_refresh() -> None:
    """stem 목록(3-상태 뱃지) + params 패널이 실제로 채워진다."""
    from gui.meta_page.view._view import Meta_view
    _p = _pipe()
    _v = Meta_view(lambda: _p)
    _v.set_pipeline(_p)
    _v.refresh()


def _flush_segment(pipe, stem: str, segment) -> None:
    """라벨맵을 디스크에 쓰고 사이드카를 저장한다 — **명시적 저장이 하는 일**(gui `_flush` 와 같은 길).

    객체 편집(`Remove_object`·`Merge_objects`)은 메모리만 고치므로, 디스크를 보는 검증은 이걸 거쳐야
    한다. 저장을 안 하면 디스크는 그대로다 — 그게 "다시 읽기로 되돌린다"가 성립하는 이유다.
    """
    _item = pipe.meta.Find(stem)
    _ref = _item.Get("segment")
    _spec = {"to": "storage", "type": _ref.format[0]}
    if len(_ref.format) > 1 and _ref.format[1]:
        _spec["format"] = _ref.format[1]
    _item.Push("segment", pipe.meta.Route(pipe.meta.Item_path(stem), "segment", _spec, segment))
    pipe.meta.Save(stem)


def _object_items(tree):
    """트리 최상위 중 객체(BRANCH) 아이템들 — 라벨링 대상."""
    from PySide6.QtCore import Qt
    _out = []
    for _i in range(tree.topLevelItemCount()):
        _it = tree.topLevelItem(_i)
        _n = _it.data(0, Qt.ItemDataRole.UserRole)
        if _n is not None and not _n.is_leaf:
            _out.append((_it, _n))
    return _out


def test_mask_editor_singleton() -> None:
    """**앱에 하나뿐인 편집기**가 객체를 조준해 그 라벨로 칠한다 — 워크플로를 실행으로 지킨다.

    객체를 고르면 그 라벨(obj_id+1)로만 칠해지고(남의 라벨은 안 건드린다), undo 로 돌아오고, stem 을
    넘어가면 조준이 풀린다(옛 라스터를 계속 칠하지 않는다).
    """
    from gui.meta_page.view._view import Meta_view
    _p = _pipe()
    _v = Meta_view(lambda: _p)
    _v.set_pipeline(_p)

    _stem = sorted(_p.meta.Bucket(STAGED))[0]
    _v._on_stem(_stem)
    _objs = _object_items(_v._obj_tree)          # 객체는 이제 별도 obj 트리에 산다(데이터 vs 객체 축 분리)
    assert _objs, "split_objects 가 객체를 안 냈다 — 조준할 대상이 없다"

    _data = _v._data
    _canvas = _data._canvas
    _editor = _data._editor
    _seg = _data.segment_node()
    assert _seg is not None, "segment 가 체크돼 있어야 조준한다"

    # 첫 객체를 조준 → 그 라벨로만 칠한다.
    _item0, _node0 = _objs[0]
    _v._obj_tree.setCurrentItem(_item0)
    _t = _editor.target()
    assert _t is not None and _t.paint == int(_node0.name) + 1, "조준 라벨 = obj_id+1"

    _label = _t.paint
    _other = _label + 1 if _label == 1 else _label - 1
    _before_other = int((_seg.value == _other).sum())
    _editor.set_tool("paint")
    _editor.set_tool("brush")
    _canvas.mouse_pressed.emit(20, 20)
    _canvas.mouse_moved.emit(60, 60)
    _canvas.mouse_released.emit(60, 60)
    assert int((_seg.value == _label).sum()) > 0, "조준한 라벨로 칠해지지 않았다"
    assert int((_seg.value == _other).sum()) == _before_other, "다른 객체의 라벨을 건드렸다"

    # undo 로 되돌아온다.
    _painted = int((_seg.value == _label).sum())
    _editor.undo()
    assert int((_seg.value == _label).sum()) < _painted, "undo 가 안 먹었다"

    # bbox 드래그 → 그 객체의 attr 이 된다.
    _editor.set_tool("bbox")
    _canvas.mouse_pressed.emit(10, 10)
    _canvas.mouse_moved.emit(70, 60)
    _canvas.mouse_released.emit(70, 60)
    assert _node0.ref.Get("bbox") is not None, "bbox 드래그가 attr 을 안 만들었다"
    assert _editor.tool("mode") == "view", "상자를 그린 뒤엔 보기로 돌아와야 한다(핸들 조작)"

    # stem 을 넘어가면 조준이 풀린다.
    _stem2 = sorted(_p.meta.Bucket(STAGED))[1]
    _v._on_stem(_stem2)
    assert _editor.target() is None, "stem 이 바뀌었는데 옛 라스터를 계속 겨눈다"


def test_editor_handles_and_pick() -> None:
    """복원된 인터랙션 — **핸들로 상자를 고치고**, **캔버스 클릭으로 객체를 고른다**(+ undo 가 상자도 든다).

    상자를 새로 그리지 않고 코너를 끌어 줄일 수 있어야 하고(옛 편집기의 기능), 그 변경은 되돌려져야 한다
    — 픽셀만 이력에 담으면 상자 편집이 조용히 안 되돌아간다.
    """
    from gui.meta_page.view._view import Meta_view
    _p = _pipe()
    _v = Meta_view(lambda: _p)
    _v.set_pipeline(_p)
    _v._on_stem(sorted(_p.meta.Bucket(STAGED))[1])

    _objs = _object_items(_v._obj_tree)
    assert _objs, "조준할 객체가 없다"
    _editor, _canvas = _v._data._editor, _v._data._canvas
    _item0, _node0 = _objs[0]
    _v._obj_tree.setCurrentItem(_item0)

    # 상자를 그린다 → 그 코너를 끌어 줄인다 (보기 모드의 핸들).
    _editor.set_tool("bbox")
    _canvas.mouse_pressed.emit(20, 20)
    _canvas.mouse_moved.emit(80, 70)
    _canvas.mouse_released.emit(80, 70)
    _drawn = list(_node0.ref.Get("bbox").info["value"])
    assert _drawn == [20.0, 20.0, 80.0, 70.0]

    _canvas.mouse_pressed.emit(20, 20)               # 좌상 코너를 잡고
    _canvas.mouse_moved.emit(40, 35)                 # 안쪽으로 끈다 (반대 코너 고정)
    _canvas.mouse_released.emit(40, 35)
    assert list(_node0.ref.Get("bbox").info["value"]) == [40.0, 35.0, 80.0, 70.0], "코너 핸들이 안 먹었다"

    _editor.undo()                                   # 상자 편집도 이력에 있다
    assert list(_node0.ref.Get("bbox").info["value"]) == _drawn, "undo 가 상자를 안 되돌렸다"

    # 캔버스 클릭 → 그 상자를 든 객체가 트리에서 선택된다 (편집기는 좌표만 주고 상위가 답한다).
    _v._obj_tree.setCurrentItem(_v._obj_tree.invisibleRootItem().child(0))
    _picked: list = []
    _v._data.object_picked.connect(lambda _n, _add: _picked.append((_n, _add)))
    _canvas.mouse_pressed.emit(60, 50)               # 상자 한가운데
    _canvas.mouse_released.emit(60, 50)
    assert _picked and _picked[0][0] is _node0, "캔버스에서 고른 객체가 안 잡혔다"
    assert _editor.target().name == f"객체 {_node0.name}", "고른 객체로 조준이 안 옮겨졌다"

    # 라벨 오버레이 — 상자에 obj_id 를 적는다 (끄면 안 적는다).
    assert any(_text for _, _, _text in _v._data._boxes()), "라벨 표시가 켜졌는데 이름이 안 온다"
    _editor._labels_btn.setChecked(False)
    assert not any(_text for _, _, _text in _v._data._boxes()), "라벨 표시를 껐는데 이름이 온다"


def test_canvas_multi_select_toggles() -> None:
    """캔버스 Shift+클릭 = **선택 토글** — 모아서 바로 병합(`M`)하고, 잘못 집은 건 다시 눌러 뺀다.

    트리로 손이 가지 않게 하는 게 요점이라, 빼는 길이 없으면 잘못 집었을 때 처음부터 다시 골라야 한다.
    """
    from gui.meta_page.view._view import Meta_view
    _p = _pipe()
    _v = Meta_view(lambda: _p)
    _v.set_pipeline(_p)
    _v._on_stem(sorted(_p.meta.Bucket(MODIFIED))[0])

    _objs = _object_items(_v._obj_tree)
    if len(_objs) < 2:
        return
    _tree = _v._obj_tree
    (_i0, _n0), (_i1, _n1) = _objs[0], _objs[1]

    _tree.select_node(_n0)                                   # 캔버스에서 하나 고른 상태
    _tree.select_node(_n1, additive=True)                    # Shift+클릭 → 선택에 더한다
    assert {_n.name for _n in _tree.selected_nodes()} == {_n0.name, _n1.name}, "Shift 가 안 더해졌다"

    _tree.select_node(_n1, additive=True)                    # 같은 것을 다시 Shift+클릭 → 뺀다
    assert {_n.name for _n in _tree.selected_nodes()} == {_n0.name}, "Shift 재클릭이 선택을 안 뺐다"
    assert _tree.current_node().name == _n0.name, "뺀 객체를 계속 겨누고 있다 (선택이 아닌데)"


def test_converter_panel_recipe_roundtrip() -> None:
    """raw glob 레시피 주입 → config 왕복 (레시피는 UI 소유)."""
    from gui.meta_page.convert import Converter_panel
    _p = _pipe()
    _panel = Converter_panel(lambda: _p)
    _panel.load({**_CONVERTER, "sources": [str(_p.root)]})
    assert isinstance(_panel.to_config(), dict)


def test_run_dialog_flow_roundtrip() -> None:
    """flow 프로필 → 카드 → config 왕복 (표현이 바뀌어도 config 계약은 고정)."""
    from gui.meta_page.run import Run_dialog
    _pipe()
    assert len(Run_dialog(_FLOWS).flows()) == len(_FLOWS)


def test_sampler_dialog() -> None:
    """tasker 탭 + Sample_view — class group-by 트리(구조가 아니라 attr)."""
    from gui.meta_page.sample import Sampler_dialog
    _p = _pipe()
    Sampler_dialog(lambda: _p)


def test_reassign_moves_no_file() -> None:
    """class 재배정은 **attr 갱신뿐** — class 가 경로에 없으므로 crop 파일이 안 움직인다."""
    from gui.meta_page.sample._sample_view import Sample_view
    _p = _pipe()
    _v = Sample_view(lambda: _p, "cls")
    _root = _p.Tasker_root("cls")
    _before = sorted(_f.name for _f in _root.rglob("*.png"))

    _sset = _p.Load_sample("cls")
    _sid = next(_k for _c in _sset.CATEGORIES for _k in _sset.Bucket(_c))
    _ref = _v._sample_ref(_sid)
    assert _ref is not None
    assert _v._writeback_class(_p, _ref, "widget")            # 정본 write-back
    _ref.Set_attr("class_id", "widget")
    _v._sset.Save(_sid)

    assert _p.Load_sample("cls").Find(_sid).Attr("class_id") == "widget"
    assert sorted(_f.name for _f in _root.rglob("*.png")) == _before, "재배정이 파일을 움직였다"


def test_remove_object_clears_label() -> None:
    """객체 삭제 = 컨테이너 pop + **그 obj 의 segment 라벨 0** — 유령 mask 를 안 남긴다(obj_id↔라벨 정합).

    그리고 **메모리에서만** 일어난다 — 디스크는 명시적 저장까지 그대로다(취소 = 저장 없이 다시 읽기).
    공유 pipeline 을 건드리므로 다른 테스트가 쓰지 않는 staged 마지막 stem 에서 태운다.
    """
    _p = _pipe()
    _stem = sorted(_p.meta.Bucket(STAGED))[-1]
    _item = _p.meta.Find(_stem)
    _objs = sorted(_item.Branches())
    assert len(_objs) >= 2, "split_objects 가 객체 2개(라벨 1·2)를 안 냈다"
    _oid, _keep = _objs[0], _objs[1]
    _label, _other = int(_oid) + 1, int(_keep) + 1

    _seg = _p.meta.Load(_stem, "segment")
    assert _seg is not None and int((_seg == _label).sum()) > 0, "지우기 전 라벨이 있어야 한다"

    Erase(_seg, _oid)                                  # 호출 측이 든 라벨맵을 제자리에서 고친다 (func)
    _p.meta.Remove_object(_stem, _oid)                 # 컨테이너 pop (store)

    assert not _p.meta.Find(_stem).Has(_oid), "객체 컨테이너가 안 지워졌다"
    assert int((_seg == _label).sum()) == 0, "지운 객체의 라벨이 유령으로 남았다"
    assert int((_seg == _other).sum()) > 0, "남의 라벨(구멍 아님)을 건드렸다"
    assert int((_p.meta.Load(_stem, "segment") == _label).sum()) > 0, \
        "저장도 안 했는데 디스크가 바뀌었다 — 그러면 '다시 읽기'로 되돌릴 수 없다"

    _flush_segment(_p, _stem, _seg)                    # 명시적 저장
    assert int((_p.meta.Load(_stem, "segment") == _label).sum()) == 0, "저장했는데 디스크가 그대로다"


def test_explicit_save_cycle() -> None:
    """편집은 대기(dirty)만 하고, **명시적 저장**이 flush + 정렬 + dirty 해제를 한다 (auto-save 아님).

    modified[0] 을 쓴다(다른 테스트가 이 객체를 안 건드림).
    """
    from gui.meta_page.view._view import Meta_view
    _p = _pipe()
    _v = Meta_view(lambda: _p)
    _v.set_pipeline(_p)
    _stem = sorted(_p.meta.Bucket(MODIFIED))[0]
    _v._on_stem(_stem)
    assert not _v._dirty and not _v._save_btn.isEnabled(), "선택만으로 저장 대기면 안 된다"

    _objs = _object_items(_v._obj_tree)
    assert _objs, "modified stem 에 객체가 없다 — 편집을 태울 대상이 없다"
    _v._obj_tree.setCurrentItem(_objs[0][0])          # 객체 조준
    _d = _v._data
    _d._editor.set_tool("bbox")
    _d._canvas.mouse_pressed.emit(8, 8)
    _d._canvas.mouse_moved.emit(60, 50)
    _d._canvas.mouse_released.emit(60, 50)            # bbox 편집 → 대기
    assert _v._dirty and _v._save_btn.isEnabled(), "편집했는데 저장 대기가 아니다 (auto-save 흔적?)"

    _v._on_save()
    assert not _v._dirty and not _v._save_btn.isEnabled(), "저장 후 대기가 안 풀렸다"
    _ids = sorted(_p.meta.Find(_stem).Branches(), key=int)
    assert _ids == [str(_i) for _i in range(len(_ids))], f"저장이 obj_id 를 압축 안 했다: {_ids}"


def test_new_object_has_class_id() -> None:
    """``+객체`` 로 만든 객체도 ``class_id`` 를 달고 나온다 — 바로 인스펙터에서 class 를 고를 수 있게."""
    from gui.meta_page.view._view import Meta_view
    _p = _pipe()
    _v = Meta_view(lambda: _p)
    _v.set_pipeline(_p)
    _stem = sorted(_p.meta.Bucket(MODIFIED))[0]
    _v._on_stem(_stem)
    _before = set(_p.meta.Find(_stem).Branches())
    _v._obj_panel.add_object()
    _new = set(_p.meta.Find(_stem).Branches()) - _before
    assert len(_new) == 1, "객체가 안 생겼다"
    assert _p.meta.Find(_stem).Get(_new.pop()).Has("class_id"), "새 객체에 class_id 가 없다"


def test_merge_objects() -> None:
    """객체 병합 = 라벨 재도색(합집합) + bbox 합집합 + 나머지 pop — class 는 **생존자** 것이 이긴다.

    staged 뒤에서 두 번째 stem 을 쓴다(다른 테스트와 안 겹치게).
    """
    _p = _pipe()
    _stem = sorted(_p.meta.Bucket(STAGED))[-2]
    _objs = sorted(_p.meta.Find(_stem).Branches(), key=int)
    if len(_objs) < 2:
        return
    _into, _gone = _objs[0], _objs[1]
    _p.meta.Find(_stem).Get(_into).Set_attr("class_id", "keep")
    _p.meta.Find(_stem).Get(_gone).Set_attr("class_id", "drop")

    _seg = _p.meta.Load(_stem, "segment")
    _px = int((_seg == int(_into) + 1).sum()) + int((_seg == int(_gone) + 1).sum())

    _p.meta.Merge_objects(_stem, _into, [_gone])         # bbox 합집합 + 컨테이너 pop (store)
    Merge_into(_seg, _into, [_gone])                      # 라벨 재도색 (func — 호출 측)

    _item = _p.meta.Find(_stem)
    assert not _item.Has(_gone), "흡수된 객체가 안 지워졌다"
    assert _item.Get(_into).Attr("class_id") == "keep", "생존자의 class 가 안 이겼다"
    assert int((_seg == int(_into) + 1).sum()) == _px, "라벨 합집합이 안 됐다(픽셀 수 불일치)"
    assert int((_seg == int(_gone) + 1).sum()) == 0, "흡수된 라벨이 유령으로 남았다"

    _flush_segment(_p, _stem, _seg)                      # 명시적 저장
    _p.Order(stems=[_stem])                              # 저장 = 구멍 압축 (병합이 남긴 자리)
    assert sorted(_p.meta.Find(_stem).Branches(), key=int) \
        == [str(_i) for _i in range(len(_objs) - 1)], "병합 뒤 obj_id 가 안 압축됐다"


def test_order_drops_unlabeled_object() -> None:
    """라벨맵에 자리가 없는 객체(빈 mask·bbox 없음)는 저장(``Order``)에서 **제거**되고, 그 수를 돌려준다.

    ``+ 객체`` 로 만든 빈 객체가 정확히 이것이다 — 칠하지도 그리지도 않으면 객체로 성립하지 않는다.
    """
    _p = _pipe()
    _stem = sorted(_p.meta.Bucket(MODIFIED))[-1]
    _new = _p.meta.Add_branch(_p.meta.Item_path(_stem))  # 빈 객체 (라벨도 bbox 도 없다)
    _p.meta.Save(_stem)
    assert _p.meta.Find(_stem).Has(_new)

    _dropped = _p.Order(stems=[_stem])                   # 공유 pipeline — 남이 남긴 빈 객체도 같이 진다

    assert _dropped >= 1, "빈 객체가 안 떨어졌다"
    assert not _p.meta.Find(_stem).Has(_new), "라벨 없는 객체가 저장 후에도 남았다"
    for _oid in _p.meta.Find(_stem).Branches():          # 남은 것은 전부 라벨이 있어야 한다
        _seg = _p.meta.Load(_stem, "segment")
        assert int((_seg == int(_oid) + 1).sum()) > 0, f"라벨 없는 객체가 남았다: {_oid}"


def test_order_compacts_holes() -> None:
    """``Pipeline.Order`` 가 삭제로 생긴 obj_id 구멍을 0부터 연속 재부여하고 segment 라벨을 맞춘다.

    staged[0] 을 쓴다(이 stem 을 뒤에 읽는 테스트 없음). Remove_object 로 구멍을 낸 뒤 Order 로 압축.
    """
    _p = _pipe()
    _stem = sorted(_p.meta.Bucket(STAGED))[0]
    _n0 = len(_p.meta.Find(_stem).Branches())
    if _n0 < 2:
        return
    _seg = _p.meta.Load(_stem, "segment")
    _oid = sorted(_p.meta.Find(_stem).Branches(), key=int)[0]
    Erase(_seg, _oid)                                    # 라벨맵 구멍 (func)
    _p.meta.Remove_object(_stem, _oid)                   # 컨테이너 pop (store)
    _flush_segment(_p, _stem, _seg)                      # 저장해야 Order 가 그 라벨맵을 본다
    _p.Order(stems=[_stem])

    _objs = sorted(_p.meta.Find(_stem).Branches(), key=int)
    assert _objs == [str(_i) for _i in range(_n0 - 1)], f"obj_id 가 0부터 연속이 아니다: {_objs}"
    _seg = _p.meta.Load(_stem, "segment")
    _labels = sorted({int(_l) for _l in _seg.flatten().tolist()} - {0})
    assert _labels == list(range(1, _n0)), f"segment 라벨이 obj_id 와 안 맞다: {_labels}"


if __name__ == "__main__":
    _tests = [_v for _k, _v in sorted(globals().items()) if _k.startswith("test_")]
    _fail = 0
    for _t in _tests:
        try:
            _t()
            print(f"[ ok ] {_t.__name__}")
        except Exception:
            _fail += 1
            print(f"[FAIL] {_t.__name__}")
            print("       " + traceback.format_exc().strip().splitlines()[-1])
    shutil.rmtree(_STATE.get("tmp", ""), ignore_errors=True)
    print(f"\n{len(_tests) - _fail}/{len(_tests)} surfaces OK")
    sys.exit(1 if _fail else 0)
