"""core.analysis — 학습 전 데이터 적합성 검증."""

from .cluster import (
    POOL, Cluster_Params, Stats, centers, components, equalize, fit, join, knn,
    merge_totals, mutual_edges, neighbors_of, norm_from_totals, radii, stats_of,
    threshold_of, totals_of, welds_of)
from .extract import Contract, Extract_Spec, FEATURE, Fold, Gauge_Spec, Read_config, TOKEN
from .group import (
    Class_stat, Hint, build, class_trust, class_usage, cleanup_hints,
    domain_signature, pool_groups, propagate)
from .inject import Source_Spec, inject, reclass, regroup
from .store import Address, Cluster_Bucket, Type_explosion

#: ``cache``·``template`` 은 모듈로 쓴다 (``from core.analysis import cache``) — 둘 다 자유함수
#: 묶음이라 심볼을 여기로 끌어올리면 ``Save``·``Load``·``Name`` 이 어느 것의 짝인지 안 보인다.
from . import cache, template  # noqa: F401

__all__ = [
    "Cluster_Bucket", "Address", "Type_explosion",
    "Contract", "Read_config", "Extract_Spec", "Gauge_Spec", "Fold", "Source_Spec",
    "Cluster_Params", "regroup",
    "FEATURE", "TOKEN", "cache", "template",
    "inject", "reclass", "build", "class_usage", "cleanup_hints", "class_trust",
    "Hint", "Class_stat",
    "domain_signature", "pool_groups", "propagate",
    "Stats", "POOL", "fit", "join", "knn", "mutual_edges", "components", "stats_of",
    "centers", "radii", "equalize", "threshold_of", "neighbors_of", "welds_of",
    "totals_of", "merge_totals", "norm_from_totals",
]
