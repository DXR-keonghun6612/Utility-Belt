"""형상 feature 행렬 → 임베딩·클러스터링 (UMAP + HDBSCAN 직접 사용).

의존성(미설치 시 ``pip install -r requirements.txt`` 의 분석 섹션): scikit-learn·umap-learn·hdbscan.
"""

from __future__ import annotations

import numpy as np

# 무거운 의존성(scikit-learn·umap-learn·hdbscan)은 함수 내부에서 import 한다 — SAM3·matplotlib 과
# 같은 repo 관례. 미설치 시 다른 import 경로(per-mask primitive 등)엔 영향 없고, 실제 실행할 때만
# 필요하다 (없으면 requirements 의 분석 섹션 설치).


def standardize(X: np.ndarray) -> np.ndarray:
    """열별 z-score 표준화 (스케일 다른 특징을 임베딩 전에 정규화)."""
    from sklearn.preprocessing import StandardScaler
    return StandardScaler().fit_transform(X)


def embed(
    X: np.ndarray, *,
    n_components: int = 2,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    random_state: int = 42,
) -> np.ndarray:
    """표준화 → UMAP 임베딩 ``(N, n_components)``."""
    import umap
    _reducer = umap.UMAP(
        n_components=n_components, n_neighbors=n_neighbors,
        min_dist=min_dist, random_state=random_state)
    return _reducer.fit_transform(standardize(X))


def cluster(
    emb: np.ndarray, *,
    min_cluster_size: int = 5,
    min_samples: int | None = None,
) -> np.ndarray:
    """임베딩 → HDBSCAN 클러스터 레이블 ``(N,)`` (-1 = noise)."""
    import hdbscan
    _h = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples)
    return _h.fit_predict(emb)
