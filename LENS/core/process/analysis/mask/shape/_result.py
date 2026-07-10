"""ShapeAnalysis — 데이터셋 단계 형상 분석 결과 (CLI/GUI 공용 산출물)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ShapeAnalysis:
    """형상 feature 행렬 + 임베딩 + 클러스터. 표현(report/figure)과 분리된 순수 데이터.

    채널: ``X`` 는 ``extract_shape_features`` 벡터를 행으로 쌓은 ``(N, D)``. ``labels`` 는 폴더에서
    온 class(없으면 UNLABELED), ``clusters`` 는 HDBSCAN 결과(-1=noise).
    """

    X:         np.ndarray   # (N, D) feature 행렬
    names:     list[str]    # 길이 D feature 이름
    labels:    np.ndarray   # (N,) class label
    stems:     list[str]    # (N,) 원본 stem
    embedding: np.ndarray   # (N, n_components)
    clusters:  np.ndarray   # (N,) 클러스터 label
