"""dataset 구조·핸들러·직렬화 검증 (flat ``Data_Ref`` 모델).

프로젝트 루트(LENS)에서 실행::

    python core/data/meta/test_dataset.py

검증 대상:
  1. ``Data_Ref`` leaf/stem 재귀 변환 (``type=="stem"`` → ``info`` 자식 재구성)
  2. ``Serialize`` → ``__init__`` 라운드트립 (중첩 stem)
  3. ``Dataset_Meta`` (flat ``Bucket_Store``) — 범주 조회·순회·영속·전이·병합
  4. 핸들러 레지스트리 (Types/Get/미등록 에러) + classmethod
  5. 핸들러별 Save/Load (image·array·attr·rle) + File_Handler 경로 파생/이동/복사

NOTE(WIP): ``core/__init__`` 이 아직 미마이그레이션 sample 을 eager import 해 깨져 있어, 이 파일은 그
cascade 를 피하려 ``core``/``core.data`` 를 namespace stub 으로 잡는다 — ``core/`` 단계 마이그레이션 후 제거.
"""

from __future__ import annotations

import inspect
import os
import sys
import tempfile
import types
from pathlib import Path

import numpy as np

_ROOT = str(Path(__file__).resolve().parents[3])
sys.path.insert(0, _ROOT)
for _n, _p in (("core", "core"), ("core.data", "core/data")):   # core/__init__ cascade 회피 (WIP)
    if _n not in sys.modules:
        _m = types.ModuleType(_n)
        _m.__path__ = [os.path.join(_ROOT, _p)]
        sys.modules[_n] = _m

from core.data import handler
from core.data.handler import Data_Ref
from core.data.meta import Dataset_Meta


def _stem(**info: Data_Ref) -> Data_Ref:
    """테스트용 컨테이너(``type="stem"``) 생성 헬퍼."""
    return Data_Ref(type="stem", info=dict(info))


def _attr(value) -> Data_Ref:
    return Data_Ref(type="attr", info={"value": value})


# ── 1. 변환 ──────────────────────────────────────────────────────────────────

def test_data_ref_defaults() -> None:
    r = Data_Ref(type="attr")
    assert r.format == "" and r.info == {}


def test_leaf_info_untouched() -> None:
    r = Data_Ref(type="attr", info={"value": [1, 2]})   # leaf 는 info 를 Data_Ref 로 안 바꿈
    assert r.info == {"value": [1, 2]} and not r.Is_stem()


def test_stem_converts_nested() -> None:
    s = Data_Ref(type="stem", info={
        "img": {"type": "image", "format": "png", "info": {"dir": ""}},
        "0":   {"type": "stem", "info": {"bbox": {"type": "attr", "info": {"value": [1, 2, 3, 4]}}}},
    })
    assert s.Is_stem()
    assert isinstance(s.info["img"], Data_Ref) and s.info["img"].type == "image"
    assert s.info["0"].Is_stem()
    assert isinstance(s.info["0"].info["bbox"], Data_Ref)
    assert s.info["0"].info["bbox"].info["value"] == [1, 2, 3, 4]


def test_stem_keeps_instances() -> None:
    r = Data_Ref(type="attr")
    s = _stem(x=r, sub=_stem(y=_attr(1)))
    assert s.info["x"] is r and isinstance(s.info["sub"].info["y"], Data_Ref)


# ── 2. 직렬화 ────────────────────────────────────────────────────────────────

def test_serialize_roundtrip() -> None:
    s = _stem(cid=_attr("A"), **{"0": _stem(bbox=_attr([1, 2]))})
    ser = s.Serialize()
    assert Data_Ref(**ser).Serialize() == ser                  # round-trip
    assert ser["type"] == "stem" and ser["info"]["0"]["type"] == "stem"


# ── 3. Dataset_Meta (flat Bucket_Store) ──────────────────────────────────────

def test_meta_buckets() -> None:
    m = Dataset_Meta(root="/r")
    assert m.Find("x") is None and m.Category_of("x") is None
    f = _stem(class_id=_attr("A"))
    m.Bucket("modified")["s0"] = f
    assert m.Find("s0") is f and m.Category_of("s0") == "modified"
    assert list(m.Iter_category("modified")) == [("s0", f)]
    assert list(m.Iter_all()) == [("modified", "s0", f)]       # (category, key, item)
    assert m.Category_root("modified") == str(Path("/r") / "modified")
    assert m.CATEGORIES == ("modified", "staged")


def test_meta_post_init_converts() -> None:
    m = Dataset_Meta(root="/r", categories={"modified": {
        "s0": {"type": "stem", "info": {"class_id": {"type": "attr", "info": {"value": "A"}}}}}})
    f = m.Bucket("modified")["s0"]
    assert isinstance(f, Data_Ref) and f.Is_stem()
    assert f.info["class_id"].info["value"] == "A"


def test_meta_iter_refs() -> None:
    m = Dataset_Meta(root="/r")
    m.params["p"] = _attr(1)
    m.Bucket("modified")["s0"] = _stem(cid=_attr("A"), **{"0": _stem(bbox=_attr([1]))})
    got = sorted((p, n) for p, n, _ in m.Iter_refs())
    assert ((), "p") in got
    assert (("modified", "s0"), "cid") in got
    assert (("modified", "s0", "0"), "bbox") in got


def test_meta_scatter_load() -> None:
    d = tempfile.mkdtemp()
    m = Dataset_Meta(root=d)
    m.params["cls"] = _attr(["a"])
    m.Bucket("modified")["s0"] = _stem(**{"0": _stem(bbox=_attr([1, 2, 3, 4]))})
    m.Scatter()
    m2 = Dataset_Meta.Load(d)
    assert m2.params["cls"].info["value"] == ["a"]
    assert m2.Find("s0").info["0"].info["bbox"].info["value"] == [1, 2, 3, 4]


def test_meta_move_delete() -> None:
    d = tempfile.mkdtemp()
    m = Dataset_Meta(root=d)
    m.Bucket("modified")["s0"] = _stem(class_id=_attr("A"))
    m.Scatter()
    m.Move("s0", "staged")
    assert m.Category_of("s0") == "staged"
    assert not (Path(d) / "modified" / ".meta" / "s0.json").exists()
    assert (Path(d) / "staged" / ".meta" / "s0.json").exists()
    m.Delete("s0")
    assert m.Find("s0") is None and not (Path(d) / "staged" / ".meta" / "s0.json").exists()


def test_meta_merge_conflicts() -> None:
    host = Dataset_Meta(root="/h", modified={"s0": _stem()}, staged={"s1": _stem()})
    other = Dataset_Meta(root="/o", modified={"s1": _stem(), "s2": _stem()})
    assert host.Merge_conflicts(other) == ["s1"]               # 범주 무관 key 중복 (flat: list[str])


def test_meta_merge_skip() -> None:
    d = tempfile.mkdtemp()
    host = Dataset_Meta(root=d, modified={"s1": _stem(keep=_attr(1))})
    other = Dataset_Meta(root=tempfile.mkdtemp(), modified={"s1": _stem(), "s2": _stem()})
    host.Merge(other, override=False)
    assert "keep" in host.Find("s1").info                       # 충돌 → 기존 유지(내부 병합)
    assert host.Find("s2") is not None                          # 비충돌 신규 추가
    assert (Path(d) / "modified" / ".meta" / "s2.json").exists()


def test_meta_merge_cross_category_override() -> None:
    d = tempfile.mkdtemp()
    host = Dataset_Meta(root=d, staged={"s1": _stem(x=_attr(1))})
    other = Dataset_Meta(root=tempfile.mkdtemp(), modified={"s1": _stem(y=_attr(2))})
    host.Merge(other, override=True)                            # staged→modified 회수
    assert host.Category_of("s1") == "modified" and "s1" not in host.Bucket("staged")
    assert "y" in host.Find("s1").info


# ── 4. 레지스트리 ────────────────────────────────────────────────────────────

def test_registry_types_and_get() -> None:
    assert set(handler.Types()) == {"image", "array", "attr", "rle", "segmap"}
    _cls = handler.HANDLER_REGISTRY.Get("image", handler.Handler)
    assert issubclass(_cls, handler.Handler)


def test_handler_methods_are_classmethods() -> None:
    _cls = handler.HANDLER_REGISTRY.Get("image", handler.Handler)
    assert isinstance(inspect.getattr_static(_cls, "Load"), classmethod)
    assert isinstance(inspect.getattr_static(_cls, "Save"), classmethod)


def test_unknown_type_raises() -> None:
    try:
        handler.HANDLER_REGISTRY.Get("nope", handler.Handler)
    except KeyError:
        return
    raise AssertionError("미등록 type 인데 KeyError 가 안 났다")


# ── 5. File_Handler 경로 파생 + Save/Load/Move/Copy/Delete ────────────────────

def test_path_derivation() -> None:
    _H = handler.HANDLER_REGISTRY.Get("image", handler.Handler)
    _ref = Data_Ref(type="image", format="png", info={"dir": ""})
    assert _H._path("/root", "frame", _ref, "s0", None) == Path("/root/frame/s0.png")
    _refd = Data_Ref(type="image", format="png", info={"dir": "md"})
    assert _H._path("/root", "mask", _refd, "s0", "2") == Path("/root/md/s0_2.png")
    assert _H._path("/root", "roi", _ref, None, None) == Path("/root/roi/roi.png")  # params(stem 없음)


def test_handler_move() -> None:
    root = tempfile.mkdtemp()
    img = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    ref = handler.Save(f"{root}/modified", "s0", "frame",
                       Data_Ref(type="image", format="png", info={"dir": ""}), img)
    assert (Path(root) / "modified" / "frame" / "s0.png").exists()
    handler.Move(f"{root}/modified", f"{root}/staged", "s0", "frame", ref)
    assert not (Path(root) / "modified" / "frame" / "s0.png").exists()
    assert (Path(root) / "staged" / "frame" / "s0.png").exists()
    handler.Move(f"{root}/modified", f"{root}/staged", "s0", "cid", _attr("X"))     # 인라인 no-op
    handler.Move(f"{root}/modified", f"{root}/staged", "ghost", "frame", ref)       # 없는 파일 no-op


def test_handler_copy() -> None:
    root = tempfile.mkdtemp()
    img = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    ref = handler.Save(f"{root}/modified", "s0", "frame",
                       Data_Ref(type="image", format="png", info={"dir": ""}), img)
    handler.Copy(f"{root}/modified", f"{root}/dst", "s0", "frame", ref)
    assert (Path(root) / "modified" / "frame" / "s0.png").exists()   # 원본 그대로
    assert (Path(root) / "dst" / "frame" / "s0.png").exists()        # 사본 생김
    handler.Copy(f"{root}/modified", f"{root}/dst", "s0", "cid", _attr("X"))         # 인라인 no-op


def test_handler_delete() -> None:
    root = tempfile.mkdtemp()
    ref = handler.Save(root, "s0", "frame",
                       Data_Ref(type="image", format="png", info={"dir": ""}),
                       np.zeros((2, 2, 3), np.uint8))
    assert (Path(root) / "frame" / "s0.png").exists()
    handler.Delete(root, "s0", "frame", ref)
    assert not (Path(root) / "frame" / "s0.png").exists()
    handler.Delete(root, "s0", "cid", _attr("X"))                    # 인라인 no-op


# ── 6. 핸들러 Save/Load (root + ref 기반) ────────────────────────────────────

def test_image_save_load_ndarray() -> None:
    root = tempfile.mkdtemp()
    img = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    ref = handler.Save(root, "s0", "frame", Data_Ref(type="image", format="png", info={"dir": ""}), img)
    assert (Path(root) / "frame" / "s0.png").exists()
    assert handler.Load(root, "s0", "frame", ref).shape == (4, 4, 3)


def test_image_missing_returns_none() -> None:
    root = tempfile.mkdtemp()
    ref = Data_Ref(type="image", format="png", info={"dir": ""})
    assert handler.Load(root, "ghost", "frame", ref) is None


def test_array_params_filename_is_name() -> None:
    root = tempfile.mkdtemp()
    arr = np.array([1.0, 2.0, 3.0])
    ref = handler.Save(root, None, "c0", Data_Ref(type="array", format="npy"), arr)
    assert (Path(root) / "c0" / "c0.npy").exists()               # stem 없음 → 파일명 = name
    assert np.allclose(handler.Load(root, None, "c0", ref), arr)


def test_attr_inline_and_text() -> None:
    root = tempfile.mkdtemp()
    ref = handler.Save(root, "s0", "cid", Data_Ref(type="attr"), "X")
    assert ref.info["value"] == "X" and ref.format == "str"
    assert handler.Load(root, "s0", "cid", ref) == "X"
    txt = Path(root) / "l.txt"
    txt.write_text("  Y \n", encoding="utf-8")                    # raw Path → strip 읽기
    ref2 = handler.Save(root, "s0", "cid", Data_Ref(type="attr"), txt)
    assert ref2.info["value"] == "Y"


def test_rle_encode_decode() -> None:
    root = tempfile.mkdtemp()
    mask = np.zeros((6, 6), np.uint8)
    mask[1:4, 2:5] = 1
    ref = handler.Save(root, "s0", "mask", Data_Ref(type="rle", format="rle"), mask, obj_id="0")
    assert "value" in ref.info
    back = handler.Load(root, "s0", "mask", ref, obj_id="0")
    assert bool((back == mask).all())


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
