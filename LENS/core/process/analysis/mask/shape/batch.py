"""mask shape 데이터셋 배치 — 폴더의 mask 들을 정렬·특징화해 feature 행렬로.

``root/<class>/*.png`` (클래스 하위폴더) 또는 flat ``root/*.png`` 둘 다 지원. 각 mask 는
``align_mask`` 로 정준 자세 → ``extract_shape_features`` 로 벡터화한다. 정렬(PCA 회전, 반사
없음)과 phase 정규화 Fourier descriptor 가 회전을 흡수하므로 배치 단계는 그대로 쌓기만 한다.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..align import align_mask
from .features import extract_shape_features

UNLABELED = "__unlabeled__"


def load_mask(path: Path) -> np.ndarray:
    """grayscale png → bool mask."""
    _img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if _img is None:
        raise FileNotFoundError(f"mask 로드 실패: {path}")
    return _img > 0


def iter_masks(root: Path, pattern: str = "*.png"):
    """``root`` 아래 mask 경로를 ``(stem, class, path)`` 로 내준다.

    하위 디렉토리가 있으면 디렉토리명을 class 로, 없으면 flat 으로 보고 class=UNLABELED.
    """
    root = Path(root)
    _subdirs = [_d for _d in sorted(root.iterdir()) if _d.is_dir()]
    if _subdirs:
        for _d in _subdirs:
            for _p in sorted(_d.glob(pattern)):
                yield _p.stem, _d.name, _p
    else:
        for _p in sorted(root.glob(pattern)):
            yield _p.stem, UNLABELED, _p


def process_masks(
    root: Path, *,
    pattern: str = "*.png",
    resolution: int = 256,
    n_harmonics: int = 20,
    normalize: bool = False,
) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """폴더의 mask 들을 특징화한다.

    Returns:
        ``(X, labels, stems, names)`` — ``X (N, D) float32``, ``labels (N,)``, ``stems`` 리스트,
        ``names`` feature 이름(길이 D).
    """
    _X, _labels, _stems, _names = [], [], [], None
    for _stem, _cls, _p in iter_masks(root, pattern):
        _m = load_mask(_p)
        if not _m.any():
            continue
        try:
            _aligned = align_mask(_m)
            _res = extract_shape_features(
                _aligned.mask, resolution=resolution,
                n_harmonics=n_harmonics, normalize=normalize)
        except ValueError:
            continue                                   # 빈/퇴화 mask 스킵
        _X.append(_res.vector)
        _labels.append(_cls)
        _stems.append(_stem)
        _names = _res.names

    if not _X:
        raise ValueError(f"특징화된 mask 가 없음: {root} (pattern={pattern})")
    return np.asarray(_X, np.float32), np.asarray(_labels), _stems, _names
