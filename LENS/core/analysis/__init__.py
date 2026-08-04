"""core.analysis — 학습 전 데이터 적합성 검증."""

from .cluster import (
    POOL, Cluster_Params, Stats, centers, components, equalize, fit, join, knn,
    merge_totals, mutual_edges, neighbors_of, norm_from_totals, radii, stats_of,
    threshold_of, totals_of)
from .extract import Extract_Spec, FEATURE, Fold, Gauge_Spec, Mask_Geometry, TOKEN
from .group import (
    Class_stat, Hint, build, class_coherence, class_usage, cleanup_hints,
    domain_signature, pool_groups, propagate)
from .inject import Source_Spec, inject
from .store import Address, Cluster_Bucket, Type_explosion

__all__ = [
    "Cluster_Bucket", "Address", "Type_explosion",
    "Mask_Geometry", "Extract_Spec", "Gauge_Spec", "Fold", "Source_Spec", "Cluster_Params",
    "FEATURE", "TOKEN",
    "inject", "build", "class_usage", "cleanup_hints", "class_coherence",
    "Hint", "Class_stat",
    "domain_signature", "pool_groups", "propagate",
    "Stats", "POOL", "fit", "join", "knn", "mutual_edges", "components", "stats_of",
    "centers", "radii", "equalize", "threshold_of", "neighbors_of",
    "totals_of", "merge_totals", "norm_from_totals",
]
