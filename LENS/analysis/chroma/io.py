"""누산 히스토그램 입력 로드 — 배열(GUI: in-memory) 또는 경로(CLI: 저장본) 모두 허용."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def pick_accumulator(path: Path) -> Path:
    """파일이면 그대로, 디렉토리면 가장 많이 누산된(.sum 최대) npy 를 고른다.

    ``level: frame`` 저장은 stem 마다 '그 시점까지의 누산 스냅샷'을 남기므로, 총합이 가장 큰
    파일이 곧 완성된 히스토그램이다 (stem 순서에 의존하지 않음).
    """
    if path.is_file():
        return path
    _cands = sorted(path.glob("*.npy"))
    if not _cands:
        raise FileNotFoundError(f"npy 없음: {path}")
    if len(_cands) == 1:
        return _cands[0]
    _best, _best_sum = _cands[0], -1
    for _c in _cands:                       # 메모리 절약: 합만 비교 (mmap)
        _s = int(np.load(_c, mmap_mode="r").sum())
        if _s > _best_sum:
            _best, _best_sum = _c, _s
    return _best


def as_histogram(src, bins: int, name: str, space_name: str) -> np.ndarray:
    """배열이면 검증만, 경로(str/Path)면 로드 후 검증해 ``(H,W,bins)`` 히스토그램을 돌려준다."""
    if isinstance(src, np.ndarray):
        _h = src
    else:
        _h = np.load(pick_accumulator(Path(src)))
    if _h.ndim != 3 or _h.shape[-1] != bins:
        raise ValueError(f"{name} shape 비정상: {_h.shape} (space={space_name} 기대 (H,W,{bins}))")
    return _h
