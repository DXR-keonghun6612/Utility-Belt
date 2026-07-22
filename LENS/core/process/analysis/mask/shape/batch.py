"""mask shape 데이터셋 배치 — 폴더의 mask 들을 특징화해 feature 행렬로.

``root/<class>/*.png`` (클래스 하위폴더) 또는 flat ``root/*.png`` 둘 다 지원한다.

특징 추출은 **학습이 쓰는 것과 같은 모듈**이다 (``torch_toolbox.modules.transform.mask``).
예전에는 이 폴더에 numpy 사본(``align.py`` · ``shape/polar.py`` · ``shape/features.py`` ·
``sample_extractor.py``)이 따로 있었고 학습 쪽과 갈라져 있었다. 그 사본들은 이런 것을
그대로 안고 있었다:

    - ``fill_holes`` 로 관통 구멍을 메웠다. 실측상 표본의 56%에 구멍이 있는데 처리 후 1%만
      남아, inner 계열 70차원이 형상과 무관한 상수가 되고 thickness 는 outer 의 복제였다.
    - 최대 연결성분 유지는 3501장 중 3400장에서 no-op 였다.

같은 모듈을 쓰면 **분석이 학습과 같은 것을 본다** — 그것이 이 파일이 외부 모듈에 기대는
이유다. 정렬도 그 모듈이 좌표계로 처리하므로(raster 회전 없음) 여기서 따로 돌리지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch

from torch_toolbox.modules.transform.mask.geometry import Geometry_Embedding

UNLABELED = "__unlabeled__"

#: 학습과 같은 캔버스. 극좌표 LUT·Fourier 기저가 이 크기에 맞춰 상수로 굳는다.
CANVAS = (224, 224)


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


def to_canvas(mask: np.ndarray, size: tuple[int, int] = CANVAS) -> np.ndarray:
    """임의 크기 bool mask → 캔버스 크기 {0,1} uint8.

    **학습과 같은 경계 규칙**이다: {0,1} 을 0/255 로 올려 LINEAR resize 한 뒤 >127 로
    재이진화한다. 보간이 만드는 경계 중간값이 임계값과 같은 스케일이어야 하기 때문이다.
    """
    _gray = np.where(mask, 255, 0).astype(np.uint8)
    return (cv2.resize(_gray, size, interpolation=cv2.INTER_LINEAR) > 127).astype(np.uint8)


def feature_names(geometry: Geometry_Embedding) -> list[str]:
    """``groups`` 에서 길이 D 의 feature 이름을 만든다 — 하드코딩하지 않는다."""
    return [
        f"{_g}_{_i:03d}"
        for _g, (_s, _e) in geometry.groups.items()
        for _i in range(_e - _s)
    ]


def process_masks(
    root: Path, *,
    pattern: str = "*.png",
    resolution: int = 512,
    n_harmonics: int = 20,
    batch_size: int = 64,
    device: str | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """폴더의 mask 들을 특징화한다.

    Args:
        root: mask 폴더.
        pattern: mask 파일 glob.
        resolution: theta bin 수(``num_angular``). 프로파일 길이이자 Fourier 길이다.
        n_harmonics: Fourier 유지 harmonic 수.
        batch_size: 한 번에 태울 mask 수. 배치가 클수록 샘플당 비용이 급감한다
            (실측 GPU: B=1 349ms/샘플 → B=128 0.32ms/샘플, peak 1.03GB).
        device: ``"cuda"`` / ``"cpu"``. None 이면 가용한 쪽.

    Returns:
        ``(X, labels, stems, names)`` — ``X (N, D) float32``, ``labels (N,)``,
        ``stems`` 리스트, ``names`` feature 이름(길이 D).
    """
    _dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
    _geo = Geometry_Embedding(
        name="geometry", trainable=False, size=CANVAS,
        num_angular=resolution, num_harmonics=n_harmonics,
    ).eval().to(_dev)

    _rows: list[np.ndarray] = []
    _labels: list[str] = []
    _stems: list[str] = []
    _buf: list[np.ndarray] = []

    def _flush() -> None:
        if not _buf:
            return
        _t = torch.from_numpy(np.stack(_buf).astype(np.float32))[:, None].to(_dev)
        with torch.no_grad():
            _rows.append(_geo(_t).cpu().numpy())
        _buf.clear()

    for _stem, _cls, _p in iter_masks(root, pattern):
        _m = load_mask(_p)
        if not _m.any():
            continue                                   # 빈 mask 스킵
        _buf.append(to_canvas(_m))
        _labels.append(_cls)
        _stems.append(_stem)
        if len(_buf) >= batch_size:
            _flush()
    _flush()

    if not _rows:
        raise ValueError(f"특징화된 mask 가 없음: {root} (pattern={pattern})")
    return (
        np.concatenate(_rows, axis=0).astype(np.float32),
        np.asarray(_labels),
        _stems,
        feature_names(_geo),
    )
