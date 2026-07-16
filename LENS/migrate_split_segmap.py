"""마이그레이션 — 병합 segmap 라벨맵을 **객체별 rle mask 로 분산** + bbox format + image h/w.

## 무엇을 바꾸나

옛 정본은 프레임마다 라벨맵 한 장(``segment`` png, 픽셀 = obj_id+1)에 객체 mask 를 **겹쳐 담았다**.
이 병합 저장은 겹침(픽셀당 라벨 하나)과 uint8 255개 한계를 안고 있었다. 이제 각 객체가 자기 mask 를
**rle 인라인**으로 든다 — 라벨맵은 process 내부 계산 표현으로만 살고, 저장·조준·편집의 단위는 객체다.

stem 사이드카마다:

- **객체 ``mask`` 추가** — ``segment`` 를 읽어 ``Mask_of(seg, id)`` 로 분리, ``rle`` 로 인라인
  (``("mask", "rle")``). 겹침·255 한계가 사라진다.
- **bbox format** — ``("bbox", "list")`` → ``("region", "bbox", "xyxy")`` (region 도메인 + style).
- **image h/w** — coco ``image`` 엔트리용. ``frame.info`` 에 height·width (파일 안 열고 얻게).
- **``segment`` 노드·png 제거** — 객체별 mask 가 truth 다. export 가 필요할 때 재구성한다.

## 원본을 안 건드린다

``src`` 는 읽기만 하고 ``dst`` 에 새로 쓴다 — 사이드카(변형본)와 **frame png 만** 옮긴다. segment png 는
객체 mask 로 분산돼 사라지므로 안 옮긴다(그게 이 마이그레이션이다). 원본은 롤백 안전장치로 그대로 남는다.
``--apply`` 없이는 통계만 낸다(dry-run). ``--category`` 로 한 범주만(검증용).

실행 (source 루트에서)::

    PYTHONPATH="$PWD" python migrate_split_segmap.py <src> <dst> --apply
"""
from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from core.func.mask.instance import Obj_label
from core.format.rle import From_mask
from core.port._structure import Structure


def _migrate_node(node: dict, seg: np.ndarray | None, hw: tuple[int, int] | None,
                  stats: Counter) -> None:
    """한 stem 사이드카(dict)를 제자리 변형한다."""
    _info = node.get("info", {})
    for _key, _obj in _info.items():
        if not _key.isdigit():                       # 객체(숫자 key)만
            continue
        _oinfo = _obj.setdefault("info", {})
        _box = _oinfo.get("bbox")
        if _box is not None and tuple(_box.get("format", ())[:1]) == ("bbox",):
            _box["format"] = ["region", "bbox", "xyxy"]
            stats["bbox"] += 1
        if seg is not None:
            _mask = (seg == Obj_label(_key)).astype(np.uint8)
            _oinfo["mask"] = {"format": ["mask", "rle"], "info": {"value": From_mask(_mask)}}
            stats["mask"] += 1

    if "frame" in _info and hw is not None:
        _frame_info = _info["frame"].setdefault("info", {})
        _frame_info["height"], _frame_info["width"] = int(hw[0]), int(hw[1])
        stats["hw"] += 1

    if _info.pop("segment", None) is not None:
        stats["segment_removed"] += 1


def _size_of(src: Path, cat: str, stem: str, seg: np.ndarray | None) -> tuple[int, int] | None:
    """이미지 크기 (H, W) — segment 가 있으면 그 shape, 없으면 frame png 헤더."""
    if seg is not None:
        return seg.shape[:2]
    _frame = src / cat / "frame" / f"{stem}.png"
    if _frame.exists():
        _img = cv2.imread(str(_frame), cv2.IMREAD_UNCHANGED)
        if _img is not None:
            return _img.shape[:2]
    return None


def migrate(src: str, dst: str, *, limit: int | None, apply: bool,
            category: str | None) -> Counter:
    _src, _dst = Path(src), Path(dst)
    _stats: Counter = Counter()

    if apply and _dst.exists():
        raise SystemExit(f"dst 가 이미 있습니다: {_dst} (덮어쓰지 않습니다 — 지우고 다시 실행)")

    for _keys, _node in Structure.Walk(str(_src)):
        _cat, _stem = _keys[0], _keys[-1]
        if category and _cat != category:
            continue
        _stats["sidecars"] += 1
        _seg_path = _src / _cat / "segment" / f"{_stem}.png"
        _seg = (cv2.imread(str(_seg_path), cv2.IMREAD_UNCHANGED)
                if _seg_path.exists() else None)
        if _seg is not None and _seg.ndim == 3:
            _seg = _seg[..., 0]                       # 다채널 저장본 → 첫 채널 (segmap 규약)

        _migrate_node(_node, _seg, _size_of(_src, _cat, _stem, _seg), _stats)

        if apply:
            Structure.Write(str(_dst), _keys, _node)  # 변형 사이드카
            _frame = _src / _cat / "frame" / f"{_stem}.png"
            if _frame.exists():                       # frame png 만 옮긴다 (segment 는 분산돼 사라진다)
                _dst_frame = _dst / _cat / "frame" / f"{_stem}.png"
                _dst_frame.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_frame, _dst_frame)
                _stats["frames_copied"] += 1

        if limit and _stats["sidecars"] >= limit:
            break

    return _stats


def main() -> None:
    _ap = argparse.ArgumentParser(description="병합 segmap → 객체별 rle mask 마이그레이션")
    _ap.add_argument("src", help="원본 dataset root (안 건드린다)")
    _ap.add_argument("dst", help="새 dataset root (사이드카 변형 + frame png)")
    _ap.add_argument("--apply", action="store_true", help="실제로 dst 를 만든다 (없으면 dry-run)")
    _ap.add_argument("--limit", type=int, default=None, help="처음 N 사이드카만 (dry-run 확인용)")
    _ap.add_argument("--category", default=None, help="한 범주만 (modified/staged/skipped — 검증용)")
    _args = _ap.parse_args()

    _stats = migrate(_args.src, _args.dst, limit=_args.limit, apply=_args.apply,
                     category=_args.category)
    print(f"\n{'적용' if _args.apply else 'dry-run'} 완료:")
    for _k, _v in sorted(_stats.items()):
        print(f"  {_k:18s} {_v:,}")


if __name__ == "__main__":
    main()
