"""mask_features — mask geometry feature 추출 및 클러스터 분석 패키지.

사용 예::

    from mask_features import (
        extract_features, process_folder, FeatureOpts,
        detect_clusters, report_clusters,
        ClusterOpts, plot_umap_3d,
    )
"""

from .feature_extract import (
    FeatureOpts,
    FeatureResult,
    PCA_RELIABLE_RATIO,
    extract_features,
    preprocess_mask,
    compute_region_props,
    compute_pca_frame,
    compute_radial_profile,
    compute_fourier_features,
    assemble_feature_vector,
    _FEATURE_GROUPS,
    _ROTATION_INVARIANT_COLS,
    _ROTATION_STABLE_COLS,
)

from .batch import (
    load_mask,
    process_folder,
    process_class_folder,
    scan_class_dirs,
    merge_class_data,
    export_to_csv,
    save_feature_names,
    load_feature_names,
    _opts_hash,
    _cache_folder,
    _pca_cache_folder,
    _clustering_cache_folder,
    _cluster_opts_hash,
    _cluster_cache_path,
    save_clustering_cache,
    load_clustering_cache,
)

from .analysis import (
    ClusterOpts,
    UNCLASSIFIED,
    resolve_feature_cols,
    detect_clusters,
)

from .report import (
    report_pca_reliability,
    report_clusters,
    report_stems,
    report_class_summary,
)

from .visualize import plot_umap, plot_umap_3d

__all__ = [
    # feature extraction
    "FeatureOpts", "FeatureResult", "PCA_RELIABLE_RATIO",
    "extract_features",
    "preprocess_mask", "compute_region_props", "compute_pca_frame",
    "compute_radial_profile", "compute_fourier_features", "assemble_feature_vector",
    "_FEATURE_GROUPS", "_ROTATION_INVARIANT_COLS", "_ROTATION_STABLE_COLS",
    # batch
    "load_mask", "process_folder", "process_class_folder",
    "scan_class_dirs", "merge_class_data",
    "export_to_csv", "save_feature_names", "load_feature_names",
    "_opts_hash", "_cache_folder",
    # analysis
    "ClusterOpts", "UNCLASSIFIED", "resolve_feature_cols", "detect_clusters",
    # report
    "report_pca_reliability", "report_clusters", "report_stems", "report_class_summary",
    # visualize
    "plot_umap", "plot_umap_3d",
]
