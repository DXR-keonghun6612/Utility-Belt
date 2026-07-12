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


def test_stem_editor_load_and_save() -> None:
    """base 이미지 로드 · 객체/데이터 트리 · segment 저장(store 에 write 요청)."""
    from gui.meta_page.edit._editor import Stem_editor
    _p = _pipe()
    _stem = sorted(_p.meta.Bucket(STAGED))[0]
    _ed = Stem_editor(_p.meta, _stem)
    assert _ed._state == STAGED                      # 범주는 store 가 답한다(Category_of)
    _ed.save()
    assert _p.meta.Find(_stem).Get("segment") is not None


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
