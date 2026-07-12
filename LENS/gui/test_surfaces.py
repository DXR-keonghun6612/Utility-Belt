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
    _seg = _data._segment_node()
    assert _seg is not None, "segment 가 체크돼 있어야 조준한다"

    # 첫 객체를 조준 → 그 라벨로만 칠한다.
    _item0, _node0 = _objs[0]
    _v._obj_tree.setCurrentItem(_item0)
    _t = _data._editor.target()
    assert _t is not None and _t.paint == int(_node0.name) + 1, "조준 라벨 = obj_id+1"

    _label = _t.paint
    _other = _label + 1 if _label == 1 else _label - 1
    _before_other = int((_seg.value == _other).sum())
    _data._editor._set_mode("paint")
    _canvas.mouse_pressed.emit(20, 20)
    _canvas.mouse_moved.emit(60, 60)
    _canvas.mouse_released.emit(60, 60)
    assert int((_seg.value == _label).sum()) > 0, "조준한 라벨로 칠해지지 않았다"
    assert int((_seg.value == _other).sum()) == _before_other, "다른 객체의 라벨을 건드렸다"

    # undo 로 되돌아온다.
    _painted = int((_seg.value == _label).sum())
    _data._editor.undo()
    assert int((_seg.value == _label).sum()) < _painted, "undo 가 안 먹었다"

    # bbox 드래그 → 그 객체의 attr 이 된다.
    _data._editor._set_mode("bbox")
    _canvas.mouse_pressed.emit(10, 10)
    _canvas.mouse_moved.emit(70, 60)
    _canvas.mouse_released.emit(70, 60)
    assert _node0.ref.Get("bbox") is not None, "bbox 드래그가 attr 을 안 만들었다"

    # stem 을 넘어가면 조준이 풀린다.
    _stem2 = sorted(_p.meta.Bucket(STAGED))[1]
    _v._on_stem(_stem2)
    assert _data._editor.target() is None, "stem 이 바뀌었는데 옛 라스터를 계속 겨눈다"


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

    _p.meta.Remove_object(_stem, _oid)

    assert not _p.meta.Find(_stem).Has(_oid), "객체 컨테이너가 안 지워졌다"
    _seg2 = _p.meta.Load(_stem, "segment")
    assert int((_seg2 == _label).sum()) == 0, "지운 객체의 라벨이 segment 에 유령으로 남았다"
    assert int((_seg2 == _other).sum()) > 0, "남의 라벨(구멍 아님)을 건드렸다"


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
    _d._editor._set_mode("bbox")
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
    _v._obj_panel._add_branch()
    _new = set(_p.meta.Find(_stem).Branches()) - _before
    assert len(_new) == 1, "객체가 안 생겼다"
    assert _p.meta.Find(_stem).Get(_new.pop()).Has("class_id"), "새 객체에 class_id 가 없다"


def test_order_compacts_holes() -> None:
    """``Pipeline.Order`` 가 삭제로 생긴 obj_id 구멍을 0부터 연속 재부여하고 segment 라벨을 맞춘다.

    staged[0] 을 쓴다(이 stem 을 뒤에 읽는 테스트 없음). Remove_object 로 구멍을 낸 뒤 Order 로 압축.
    """
    _p = _pipe()
    _stem = sorted(_p.meta.Bucket(STAGED))[0]
    _n0 = len(_p.meta.Find(_stem).Branches())
    if _n0 < 2:
        return
    _p.meta.Remove_object(_stem, sorted(_p.meta.Find(_stem).Branches(), key=int)[0])  # 구멍
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
