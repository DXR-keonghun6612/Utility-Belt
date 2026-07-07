"""analyze — mask 폴더 → ShapeAnalysis (batch 추출 → 임베딩 → 클러스터, CLI/GUI 공용 진입점)."""

from __future__ import annotations

from pathlib import Path

from ._result import ShapeAnalysis
from .batch import process_masks
from .embed import embed, cluster


def analyze(
    root: Path, *,
    pattern: str = "*.png",
    resolution: int = 256,
    n_harmonics: int = 20,
    normalize: bool = False,
    n_components: int = 2,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    min_cluster_size: int = 5,
    min_samples: int | None = None,
    random_state: int = 42,
) -> ShapeAnalysis:
    """mask 폴더를 형상 특징화 → UMAP 임베딩 → HDBSCAN 클러스터까지 한 번에."""
    _X, _labels, _stems, _names = process_masks(
        root, pattern=pattern, resolution=resolution,
        n_harmonics=n_harmonics, normalize=normalize)

    _emb = embed(_X, n_components=n_components, n_neighbors=n_neighbors,
                 min_dist=min_dist, random_state=random_state)
    _clu = cluster(_emb, min_cluster_size=min_cluster_size, min_samples=min_samples)

    return ShapeAnalysis(
        X=_X, names=_names, labels=_labels, stems=_stems,
        embedding=_emb, clusters=_clu)
