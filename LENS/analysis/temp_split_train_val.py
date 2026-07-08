"""임시 스크립트 — crop_out 의 클래스별 mask 를 train/val 8:2 로 나눈다.

``crop_out/<class>/*.png`` 를 **클래스별 층화**(각 클래스 내부에서 8:2)로 섞어 나눠,
``{out}/train/<class>/*.png`` · ``{out}/val/<class>/*.png`` 로 **복사**한다(원본 보존).
클래스마다 따로 나누므로 클래스 비율이 train/val 에 그대로 유지된다.

실행: ``python temp_split_train_val.py [crop_out] [--out crop_out_split] [--val-frac 0.2]
        [--seed 42] [--move]``
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


def main() -> None:
    _ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    _ap.add_argument("root", nargs="?", type=Path, default=Path("crop_out"),
                     help="입력 폴더 (root/<class>/*.png)")
    _ap.add_argument("--out", type=Path, default=Path("crop_out_split"),
                     help="출력 루트 (train/·val/ 하위에 class 폴더)")
    _ap.add_argument("--pattern", default="*.png", help="mask glob")
    _ap.add_argument("--val-frac", type=float, default=0.2, help="val 비율 (기본 0.2 = 8:2)")
    _ap.add_argument("--seed", type=int, default=42, help="셔플 시드")
    _ap.add_argument("--move", action="store_true", help="복사 대신 이동 (원본 제거)")
    _args = _ap.parse_args()

    _out = _args.out
    if _out.exists():
        shutil.rmtree(_out)
    _rng = random.Random(_args.seed)
    _xfer = shutil.move if _args.move else shutil.copy2

    _classes = sorted(_d for _d in _args.root.iterdir() if _d.is_dir())
    _tot_tr = _tot_va = 0
    _lines = [f"{'class':<16} {'total':>6} {'train':>6} {'val':>6}",
              "-" * 38]
    for _cdir in _classes:
        _files = sorted(_cdir.glob(_args.pattern))
        if not _files:
            continue
        _rng.shuffle(_files)
        _n_val = int(round(len(_files) * _args.val_frac))
        _n_val = min(_n_val, len(_files))                 # 전부 val 방지용 상한
        _val, _train = _files[:_n_val], _files[_n_val:]

        for _split, _items in (("train", _train), ("val", _val)):
            _dst_dir = _out / _split / _cdir.name
            _dst_dir.mkdir(parents=True, exist_ok=True)
            for _f in _items:
                _xfer(str(_f), str(_dst_dir / _f.name))

        _tot_tr += len(_train); _tot_va += len(_val)
        _lines.append(f"{_cdir.name:<16} {len(_files):>6} {len(_train):>6} {len(_val):>6}")

    _lines.append("-" * 38)
    _lines.append(f"{'TOTAL':<16} {_tot_tr + _tot_va:>6} {_tot_tr:>6} {_tot_va:>6}")
    _summary = "\n".join(_lines) + "\n"
    _out.mkdir(parents=True, exist_ok=True)
    (_out / "split_summary.txt").write_text(_summary, encoding="utf-8")
    print(_summary)
    print(f"완료 — {_out}/train, {_out}/val  ({'이동' if _args.move else '복사'})")


if __name__ == "__main__":
    main()
