"""임시 스크립트 — staged 0번 obj mask 를 stem segmap 에서 뽑아 중심 윈도우로 crop 해 저장.

특정 데이터셋 경로의 **staged** 프레임마다 프레임 레벨 **segmap**(라벨맵, 픽셀=obj_id+1)에서
0번 객체(``frame.object[0]``) mask 를 뽑아:
  1. mask 중심(픽셀 무게중심)이 이미지 중심에서 **대각선 길이의 10% 미만** 떨어진 프레임만 통과.
  2. ``Normalize_mask`` (norm_mask — 정사각 crop + target 크기 pad) 적용.
  3. 결과를 ``{out}/{class_id}/{stem}.png`` 로 저장 (파일명 = stem, 폴더 = obj 의 class_id).

실행: ``python temp_crop_mask.py [<루트>] [--seg-key KEY] [--out crop_out] [--size 256] [--dist-frac 0.10]``
segmap 키를 모르면 생략 — ``frame.data`` 에서 type=segmap 인 첫 항목을 자동으로 찾는다.
(LENS 루트에서 실행 — ``core`` 패키지 import 가능해야 함.)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from core.data import handler
from core.data.meta.schema import Frame
from core.data.meta import store
from core.process.mask import Normalize_mask


def _load_segmap(root: str, stem: str, frame: Frame, seg_key: str | None) -> np.ndarray | None:
    """프레임 segmap(라벨맵)을 (H,W) uint8 로 읽는다. seg_key 없으면 type=segmap 자동 탐색. 없으면 None."""
    if seg_key:
        _ref = frame.data.get(seg_key)
        _items = [(seg_key, _ref)] if _ref is not None else []
    else:
        _items = [(_n, _r) for _n, _r in frame.data.items() if _r.type == "segmap"]
    for _name, _ref in _items:
        _v = handler.Load(root, stem, _name, _ref)
        if isinstance(_v, np.ndarray) and _v.ndim >= 2:
            return _v[..., 0] if _v.ndim == 3 else _v
    return None


def main() -> None:
    _ap = argparse.ArgumentParser(description=__doc__)
    _ap.add_argument("root", nargs="?", default="result/sl_mirrortech/",
                     help="데이터셋 폴더 (staged 사이드카 포함)")
    _ap.add_argument("--seg-key", default="segment",
                     help="frame.data 의 라벨맵 키 (기본 segment; 빈 값이면 type=segmap 자동 탐색)")
    _ap.add_argument("--out", default="crop_out", help="출력 루트 (기본 crop_out)")
    _ap.add_argument("--size", type=int, default=256, help="crop 윈도우 크기 px (norm target)")
    _ap.add_argument("--dist-frac", type=float, default=0.10,
                     help="이미지 대각선 대비 중심 거리 임계 (기본 0.15)")
    _args = _ap.parse_args()

    _meta  = store.Load(_args.root)
    _root  = _meta.State_root("staged")                  # {root}/staged — 파일 루트
    _norm  = Normalize_mask(target_shape=_args.size)
    _out   = Path(_args.out)

    _n_save = _n_far = _n_skip = 0
    for _stem, _frame in _meta.staged.items():
        if not _frame.object:
            print(f"[skip] {_stem}: 객체 없음")
            _n_skip += 1
            continue
        _obj    = _frame.object[0]
        _segmap = _load_segmap(_root, _stem, _frame, _args.seg_key)
        if _segmap is None:
            print(f"[skip] {_stem}: segmap 없음")
            _n_skip += 1
            continue

        _label = int(_obj.obj_id) + 1                     # segmap 픽셀값 = obj_id+1
        _mask  = (_segmap == _label).astype(np.uint8) * np.uint8(255)
        _ys, _xs = np.where(_mask > 0)
        if _xs.size == 0:
            print(f"[skip] {_stem}: 0번 obj(label {_label}) 픽셀 없음")
            _n_skip += 1
            continue

        _h, _w = _mask.shape[:2]
        _cy, _cx = float(_ys.mean()), float(_xs.mean())   # mask 무게중심
        _dist = ((_cx - _w / 2.0) ** 2 + (_cy - _h / 2.0) ** 2) ** 0.5
        _diag = (_h ** 2 + _w ** 2) ** 0.5
        if _dist >= _args.dist_frac * _diag:              # 중심에서 너무 먼 mask 는 버림
            print(f"[far ] {_stem}: 중심거리 {_dist:.1f} >= {_args.dist_frac * _diag:.1f}")
            _n_far += 1
            continue

        _res = _norm.Run(mask=_mask)                       # norm_mask (정사각 crop + pad)
        if not _res:
            print(f"[skip] {_stem}: norm 결과 없음")
            _n_skip += 1
            continue

        _cls = _obj.class_id or "__unclassified__"
        _dir = _out / _cls
        _dir.mkdir(parents=True, exist_ok=True)
        _path = _dir / f"{_stem}.png"
        if not cv2.imwrite(str(_path), _res["mask"]):
            raise OSError(f"저장 실패: {_path}")
        print(f"[save] {_path}")
        _n_save += 1

    print(f"\n완료 — 저장 {_n_save} / 거리초과 {_n_far} / 스킵 {_n_skip}")


if __name__ == "__main__":
    main()
