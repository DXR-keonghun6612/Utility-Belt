"""기존 정본 데이터 검사 — segmap 접기·bbox 축 정리 이후의 정합을 훑는다 (기본 리포트).

객체별 mask(정본) 모델로 옮긴 뒤 **옛 모델 잔재·정합 위반**을 stem/객체 단위로 찾아 리포트한다.
``--fix`` 는 그중 **``mask_outside_bbox`` 하나만** 고친다(bbox 밖 전경 제거 — 그리기의 clip 규칙과 같은
연산). 나머지는 판단이 필요하거나(어느 쪽이 진실인가) 데이터 부재라 리포트만 한다. 무엇을 보나:

- **segment leaf 잔존**   — item 에 저장된 ``segmap`` 도메인 leaf (이제 라벨맵은 저장 안 한다).
- **옛 bbox 포맷**        — ``("bbox", …)`` (새 정본은 ``("region","bbox","xyxy")``).
- **mask ⊄ bbox**        — mask 가 그 객체 bbox 밖으로 삐져나옴 (그리기 clip 규칙 위반 데이터).
- **mask 없음/빈 것**     — bbox 는 있는데 mask leaf 가 없거나 전경이 0 (유령 후보).
- **bbox 없음**           — mask 는 있는데 bbox 가 없음.
- **bbox↔mask 어긋남**    — 저장 bbox 가 mask 의 tight 외접박스와 크게 다름 (IoU 낮음).

실행 (source 루트에서, sl 환경)::

    PYTHONPATH="$PWD" python check_data.py <root> [--category staged] [--limit 20] [--verbose]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from core.store import Dataset_Meta
from core.func.cv.geom import Clip_to_box, Mask_to_box


#: bbox↔mask tight 어긋남 판정 — IoU 가 이보다 낮으면 리포트.
_MISMATCH_IOU = 0.5


def _box_iou(a: list[float], b: list[float]) -> float:
    """두 XYXY 박스의 IoU (겹침/합집합). 둘 중 하나라도 면적 0 이면 0."""
    _ix0, _iy0 = max(a[0], b[0]), max(a[1], b[1])
    _ix1, _iy1 = min(a[2], b[2]), min(a[3], b[3])
    _iw, _ih = max(_ix1 - _ix0, 0.0), max(_iy1 - _iy0, 0.0)
    _inter = _iw * _ih
    _aa = max(a[2] - a[0], 0.0) * max(a[3] - a[1], 0.0)
    _ab = max(b[2] - b[0], 0.0) * max(b[3] - b[1], 0.0)
    _union = _aa + _ab - _inter
    return _inter / _union if _union > 0 else 0.0


def _bbox_of(obj) -> tuple[list[float] | None, tuple | None]:
    """객체 bbox 의 (인라인 값, format) — 없으면 (None, None)."""
    _ref = obj.Get("bbox")
    if _ref is None:
        return None, None
    _v = _ref.info.get("value")
    _v = [float(_x) for _x in _v] if isinstance(_v, (list, tuple)) and len(_v) == 4 else None
    return _v, _ref.format


def _check_object(meta: Dataset_Meta, path: tuple[str, ...], obj) -> list[tuple[str, str]]:
    """한 객체 → (검사코드, 상세) 리스트. path = (범주, stem, obj_id)."""
    _out: list[tuple[str, str]] = []
    _box, _box_fmt = _bbox_of(obj)
    _mask_ref = obj.Get("mask")
    _mask = meta.Decode(path, "mask", _mask_ref) if _mask_ref is not None else None
    _has_fg = _mask is not None and bool(np.any(_mask))

    if _box_fmt is not None and _box_fmt[:1] != ("region",):
        _out.append(("old_bbox_format", f"format={tuple(_box_fmt)}"))
    if not _has_fg:
        _out.append(("no_mask", "mask leaf 없음" if _mask_ref is None else "전경 0 (빈 mask)"))
    if _box is None:
        _out.append(("no_bbox", "bbox 없음"))

    if _has_fg and _box is not None:
        _clipped = Clip_to_box(_mask, _box)
        _spill = int(_mask.sum()) - int(_clipped.sum())
        if _spill > 0:
            _out.append(("mask_outside_bbox",
                         f"{_spill}px ({_spill / int(_mask.sum()):.1%}) bbox 밖"))
        _tight = Mask_to_box(_mask)
        if _tight is not None:
            _iou = _box_iou(_box, [float(_v) for _v in _tight])
            if _iou < _MISMATCH_IOU:
                _out.append(("bbox_mask_mismatch",
                             f"IoU={_iou:.2f} (bbox={[round(v) for v in _box]} "
                             f"tight={[round(float(v)) for v in _tight]})"))
    return _out


def _check_item(item) -> list[tuple[str, str]]:
    """item(프레임) 레벨 검사 — 저장된 segmap leaf 잔재."""
    _out: list[tuple[str, str]] = []
    for _name, _leaf in item.Leaves().items():
        if _leaf.format[:1] == ("segmap",):
            _out.append(("segment_leaf", f"leaf '{_name}' format={tuple(_leaf.format)}"))
    return _out


def _clip_object(meta: Dataset_Meta, path: tuple[str, ...], obj) -> int:
    """bbox 밖 mask 전경을 지운다 — **제거한 픽셀 수** (교정 못 하면 0).

    지우는 것은 bbox 밖 전경뿐이다(그리기의 clip 규칙과 같은 연산 ``Clip_to_box``). bbox·format 은
    안 건드린다 — 이 도구가 고치는 건 ``mask_outside_bbox`` 하나다.

    **인라인 mask 만 고친다** — 파일 payload(png/npy)면 경로·write 가 얽혀 여기서 손대지 않는다(0 반환).
    포맷은 그 leaf 가 쓰던 것을 그대로 유지한다(``store.Encode`` 경유 — rle 를 손으로 짓지 않는다).
    """
    _box, _ = _bbox_of(obj)
    _leaf = obj.Get("mask")
    if _box is None or _leaf is None or _leaf.info.get("value") is None:
        return 0                                        # 판정 근거 없음 / 파일 payload → 건너뜀
    _mask = meta.Decode(path, "mask", _leaf)
    if _mask is None:
        return 0
    _clipped = Clip_to_box(_mask, _box)
    _removed = int(_mask.sum()) - int(_clipped.sum())
    if _removed <= 0:
        return 0
    _fmt = _leaf.format[1] if len(_leaf.format) > 1 and _leaf.format[1] else "rle"
    _leaf.info["value"] = meta.Encode({"type": "mask", "format": _fmt}, _clipped).info["value"]
    return _removed


def _tighten_object(meta: Dataset_Meta, path: tuple[str, ...], obj) -> tuple | None:
    """bbox 를 mask 의 **tight 외접박스**로 맞춘다 — 바뀌었으면 ``(옛 box, 새 box)``, 아니면 None.

    mask 가 정본이므로 bbox 는 그 외곽을 따른다 — 헐거운 bbox 는 조인다. ``--fix`` 와 함께 쓰면 clip 이
    **먼저** 돌아, 잘려나간 뒤의 mask 기준으로 조여진다(그래서 삐친 조각이 bbox 를 늘리지 않는다).

    **의도적으로 키운 bbox 도 조여진다** — flow 의 ``bbox_gap`` 으로 여유를 준 데이터면 그 여유가 사라진다.
    mask 없거나 전경이 없으면 근거가 없어 건드리지 않는다.
    """
    _leaf, _box_ref = obj.Get("mask"), obj.Get("bbox")
    if _leaf is None or _box_ref is None:
        return None
    _mask = meta.Decode(path, "mask", _leaf)
    if _mask is None or not np.any(_mask):
        return None
    _tight = Mask_to_box(_mask)
    if _tight is None:
        return None
    _new = [float(_v) for _v in _tight]
    _old = _box_ref.info.get("value")
    if _old and [round(float(_v), 2) for _v in _old] == [round(_v, 2) for _v in _new]:
        return None                                     # 이미 딱 맞음
    _box_ref.info["value"] = _new
    return (_old, _new)


#: 진행 표시는 **터미널일 때만** — 파이프·리다이렉트면 ``\\r`` 이 파일에 그대로 남아 리포트가 지저분해진다.
_TTY = sys.stdout.isatty()


def _progress(done: int, total: int) -> None:
    """같은 줄을 갱신하는 진행 표시 — 상세 출력과 안 섞이게 ``\\r`` 로만 쓴다."""
    if _TTY and total:
        print(f"\r  검사 중 {done:,}/{total:,} ({done / total:.0%}) …", end="", flush=True)


def _clear_line() -> None:
    """진행 표시 줄을 지운다 — 상세 리포트를 찍기 직전에."""
    if _TTY:
        print("\r" + " " * 40 + "\r", end="", flush=True)


def check(root: str, *, category: str | None, limit: int | None, verbose: bool,
          fix: bool = False, tight: bool = False) -> Counter:
    _meta = Dataset_Meta.Restore(root)
    _stats: Counter = Counter()
    _cats = [category] if category else list(_meta.CATEGORIES)
    _total = sum(len(_meta.Bucket(_c)) for _c in _cats)

    for _cat in _cats:
        for _stem, _item in _meta.Bucket(_cat).items():
            _stats["items"] += 1
            _findings: list[str] = []
            for _code, _detail in _check_item(_item):
                _stats[_code] += 1
                _findings.append(f"    [{_code}] {_detail}")

            _dirty = False
            for _oid, _obj in _item.Branches().items():
                _stats["objects"] += 1
                _path, _codes = (_cat, _stem, _oid), set()
                for _code, _detail in _check_object(_meta, _path, _obj):
                    _stats[_code] += 1
                    _codes.add(_code)
                    _findings.append(f"    obj {_oid}: [{_code}] {_detail}")

                if fix and "mask_outside_bbox" in _codes:      # ① bbox 밖 전경 제거
                    _px = _clip_object(_meta, _path, _obj)
                    if _px:
                        _dirty = True
                        _stats["fixed_objects"] += 1
                        _stats["fixed_px"] += _px
                        _findings.append(f"    obj {_oid}: → clip 적용 ({_px}px 제거)")
                    else:
                        _stats["fix_skipped"] += 1
                        _findings.append(f"    obj {_oid}: → clip 못 함 (인라인 mask 아님)")

                if tight:                                      # ② bbox 를 mask tight 로 (clip 뒤 기준)
                    _moved = _tighten_object(_meta, _path, _obj)
                    if _moved is not None:
                        _dirty = True
                        _stats["tightened"] += 1
                        _o, _n = _moved
                        _findings.append(
                            f"    obj {_oid}: → bbox tight "
                            f"({[round(float(_v)) for _v in (_o or [])]} → {[round(_v) for _v in _n]})")
            if _dirty:
                _meta.Save(_stem)                              # 이 stem 사이드카만 다시 쓴다
                _stats["fixed_stems"] += 1

            if _findings:
                _stats["problem_stems"] += 1                   # 전수 집계 (출력 여부와 무관)
                if verbose or _stats["printed"] < (limit or 10**9):
                    _stats["printed"] += 1
                    _clear_line()
                    print(f"[{_cat}] {_stem}")
                    for _f in _findings:
                        print(_f)
            if _stats["items"] % 25 == 0 or _stats["items"] == _total:
                _progress(_stats["items"], _total)
    _clear_line()
    return _stats


def main() -> None:
    _ap = argparse.ArgumentParser(
        description="기존 정본 데이터 정합 검사 (기본 리포트 전용; --fix 로 bbox 밖 mask 만 교정)")
    _ap.add_argument("root", help="dataset root (Dataset_Meta.Restore 대상)")
    _ap.add_argument("--category", default=None, help="한 범주만 (modified/staged/skipped)")
    _ap.add_argument("--limit", type=int, default=30, help="문제 stem 출력 상한 (verbose 면 무시)")
    _ap.add_argument("--verbose", action="store_true", help="문제 stem 전부 출력")
    _ap.add_argument("--fix", action="store_true",
                    help="bbox 밖 mask 전경을 지우고 **제자리 저장**한다 (그 stem 사이드카만 다시 씀).")
    _ap.add_argument("--tight", action="store_true",
                    help="bbox 를 mask 의 tight 외접박스로 조인다 (--fix 와 같이 쓰면 clip 뒤 기준). "
                         "**bbox_gap 으로 준 여유도 사라진다.**")
    _args = _ap.parse_args()

    if not Path(_args.root).exists():
        raise SystemExit(f"root 가 없습니다: {_args.root}")
    if _args.fix or _args.tight:
        _what = " + ".join(_w for _w, _on in
                           (("bbox 밖 mask 제거", _args.fix), ("bbox tight 조이기", _args.tight)) if _on)
        print(f"※ 제자리 수정합니다 ({_what}) — 원본 백업 권장.\n")

    _stats = check(_args.root, category=_args.category, limit=_args.limit,
                   verbose=_args.verbose, fix=_args.fix, tight=_args.tight)

    print("\n── 요약 ──")
    _issue_keys = ["segment_leaf", "old_bbox_format", "mask_outside_bbox",
                   "no_mask", "no_bbox", "bbox_mask_mismatch"]
    _hidden = _stats["problem_stems"] - _stats["printed"]
    print(f"  items={_stats['items']:,}  objects={_stats['objects']:,}  "
          f"문제 stem={_stats['problem_stems']:,}"
          + (f" (위에 {_stats['printed']:,}개만 출력 — 전부 보려면 --verbose)"
             if _hidden > 0 else ""))
    _total = sum(_stats[_k] for _k in _issue_keys)
    for _k in _issue_keys:
        print(f"  {_k:20s} {_stats[_k]:,}")
    print(f"  {'합계':20s} {_total:,}")
    if _total == 0:
        print("  ✓ 문제 없음")

    if _args.fix or _args.tight:
        print("\n── 교정 ──")
        if _args.fix:
            print(f"  clip   — 객체 {_stats['fixed_objects']:,}개 · {_stats['fixed_px']:,}px 제거")
            if _stats["fix_skipped"]:
                print(f"           건너뜀 {_stats['fix_skipped']:,} (인라인 mask 가 아님 — 파일 payload)")
        if _args.tight:
            print(f"  tight  — bbox {_stats['tightened']:,}개 조임")
        print(f"  저장   — stem {_stats['fixed_stems']:,}개 사이드카")
    else:
        if _stats["mask_outside_bbox"]:
            print(f"\n  → bbox 밖 mask {_stats['mask_outside_bbox']:,}건은 --fix 로 지울 수 있습니다.")
        if _stats["bbox_mask_mismatch"]:
            print(f"  → bbox 어긋남 {_stats['bbox_mask_mismatch']:,}건은 --tight 로 조일 수 있습니다.")


if __name__ == "__main__":
    main()
