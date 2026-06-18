"""extract_mask_features.py — mask feature 추출 및 클러스터 분석 CLI.

사용법::

    # 기본 (전체 feature → UMAP 3D → HDBSCAN)
    python extract_mask_features.py --root /data/masks

    # named feature 지정 (UMAP 없이 바로 HDBSCAN)
    python extract_mask_features.py --root /data/masks \\
        --cluster-features area perimeter pca_area_rl pca_area_ud \\
                           mu30_pca_log mu03_pca_log mu21_pca_log mu12_pca_log

    # 특정 class만
    python extract_mask_features.py --root /data/masks \\
        --classes sedan suv truck

Python API::

    from mask_features import (
        extract_features, process_folder, FeatureOpts,
        detect_clusters, report_clusters,
        ClusterOpts, plot_umap_3d,
    )
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from mask_features.feature_extract import (
    _FEATURE_GROUPS, _ROTATION_INVARIANT_COLS, _ROTATION_STABLE_COLS, FeatureOpts,
)
from mask_features.batch import (
    _cache_folder, _opts_hash, load_feature_names, process_folder,
    _pca_cache_folder, _clustering_cache_folder,
    _cluster_opts_hash, _cluster_cache_path,
    save_clustering_cache, load_clustering_cache,
)
from mask_features.analysis import (
    ClusterOpts, detect_clusters, resolve_feature_cols,
)
from mask_features.report import report_clusters, report_stems, report_class_summary
from mask_features.visualize import plot_umap


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="mask feature 추출 및 클러스터 분석")
    p.add_argument("--root", type=Path, default=None,
                   help="root/<class>/*.png 구조의 최상위 경로")

    # feature 추출
    p.add_argument("--pixel-size",  type=float, default=1.0)
    p.add_argument("--num-angles",  type=int,   default=256)
    p.add_argument("--num-fourier", type=int,   default=20)

    # 캐시
    p.add_argument("--cache-dir",  type=Path, default=None,
                   help="캐시 저장 경로 (기본: root의 부모 디렉토리)")
    p.add_argument("--export-csv", action="store_true",
                   help="feature matrix를 CSV로도 저장")
    p.add_argument("--no-cache",   action="store_true",
                   help="캐시 무시하고 재처리")

    # 클러스터링
    p.add_argument("--cluster-features", nargs="+", default=None,
                   metavar="FEATURE_NAME",
                   help="named feature 지정 시 UMAP 없이 해당 feature로 HDBSCAN. "
                        "생략 시 전체 feature → UMAP 3D → HDBSCAN.")
    p.add_argument("--cluster-min-cluster-size", type=int, default=5,
                   help="HDBSCAN min_cluster_size (기본: 5)")
    p.add_argument("--cluster-min-samples", type=int, default=None,
                   help="HDBSCAN min_samples (기본: min_cluster_size 와 동일)")
    p.add_argument("--cluster-purity-thr", type=float, default=0.8,
                   help="혼동 클러스터 판정 purity 임계값 (기본: 0.8)")
    p.add_argument("--cluster-global-ratio", type=float, default=None,
                   metavar="RATIO",
                   help="전체 공간 거리 중앙값 × RATIO 로 cluster_selection_epsilon 자동 계산 (예: 0.1). "
                        "생략 시 epsilon 비활성.")
    p.add_argument("--cluster-umap-neighbors", type=int, default=15,
                   help="UMAP n_neighbors (기본: 15)")
    p.add_argument("--cluster-umap-min-dist", type=float, default=0.1,
                   help="UMAP min_dist (기본: 0.1)")
    p.add_argument("--cluster-report", type=Path, default=None,
                   help="클러스터 분석 리포트 저장 경로 (.txt)")
    p.add_argument("--no-cluster", action="store_true",
                   help="클러스터 분석 생략")

    # UMAP 시각화
    p.add_argument("--classes",       nargs="*", default=None,
                   help="UMAP에 표시할 class 이름 (생략 시 전체)")
    p.add_argument("--feature-group", default=None,
                   choices=list(_FEATURE_GROUPS),
                   help="emb 없을 때 UMAP 투영에 사용할 feature 그룹 (생략 시 전체)")
    p.add_argument("--umap-dims",     type=int, default=3, choices=[2, 3],
                   help="UMAP 투영 차원 2D / 3D (기본: 3)")
    p.add_argument("--umap-max-pts",  type=int, default=200,
                   help="클래스(O 샘플)당 최대 표시 점 수 — 초과 시 랜덤 서브샘플 (기본: 200)")
    p.add_argument("--no-umap", action="store_true",
                   help="UMAP 시각화 생략")
    p.add_argument("--show-match", action="store_true",
                   help="O/X/~/? match 결과로 마커 구분 표시 (기본: 단일 마커)")

    p.add_argument("--list-features", action="store_true",
                   help="저장된 feature 이름 목록 출력 후 종료")
    return p


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    if args.root is None:
        parser.error("--root 경로가 필요합니다.")

    opts = FeatureOpts(
        pixel_size  = args.pixel_size,
        num_angles  = args.num_angles,
        num_fourier = args.num_fourier,
    )

    if args.list_features:
        cache_dir = args.root.parent if args.cache_dir is None else args.cache_dir
        cf        = _cache_folder(cache_dir, args.root.name)
        h         = _opts_hash(opts)
        names     = load_feature_names(cf, h)
        if names is None:
            print(f"[INFO] feature_names__{h}.json not found in {cf}")
            print("       Run without --list-features first to build the cache.")
        else:
            print(f"feature_names__{h}.json  ({len(names)} features)\n")
            for i, n in enumerate(names):
                print(f"  {i:4d}  {n}")
        raise SystemExit(0)

    if args.no_cache:
        cache_dir = args.root.parent if args.cache_dir is None else args.cache_dir
        h         = _opts_hash(opts)
        pca_cf    = _pca_cache_folder(cache_dir, args.root.name)
        clust_cf  = _clustering_cache_folder(cache_dir, args.root.name)
        removed   = list(pca_cf.glob(f"*__{h}.npz")) if pca_cf.exists() else []
        removed  += list(clust_cf.glob(f"{h}__*.npz")) if clust_cf.exists() else []
        for f in removed:
            f.unlink()
        if removed:
            print(f"[CACHE] cleared {len(removed)} file(s)")

    # Step 1: feature extraction
    print(f"\n[Step 1] feature extraction: {args.root}")
    X, y, feat_names, stems, ratios = process_folder(
        args.root, opts,
        cache_dir  = args.cache_dir,
        export_csv = args.export_csv,
    )
    print(f"  X={X.shape}  rotation_invariant={len(_ROTATION_INVARIANT_COLS)} cols"
          f"  rotation_stable={len(_ROTATION_STABLE_COLS)} cols")

    resolved_cache = args.root.parent if args.cache_dir is None else args.cache_dir
    h = _opts_hash(opts)

    # Step 2: cluster analysis
    cluster_result: dict | None = None
    if not args.no_cluster:
        # ClusterOpts 구성
        feature_cols = None
        mode = "umap"
        if args.cluster_features:
            feature_cols = resolve_feature_cols(args.cluster_features, feat_names)
            mode = "features"

        c_opts = ClusterOpts(
            mode                 = mode,
            feature_cols         = feature_cols,
            umap_n_components    = args.umap_dims,
            umap_n_neighbors     = args.cluster_umap_neighbors,
            umap_min_dist        = args.cluster_umap_min_dist,
            min_cluster_size     = args.cluster_min_cluster_size,
            min_samples          = args.cluster_min_samples,
            global_epsilon_ratio = args.cluster_global_ratio,
            purity_threshold     = args.cluster_purity_thr,
        )

        # classes 필터 (분석 범위 제한)
        if args.classes:
            mask = np.isin(y, args.classes)
            X_c, y_c, stems_c = X[mask], y[mask], [s for s, m in zip(stems, mask) if m]
        else:
            X_c, y_c, stems_c = X, y, stems

        print(f"\n[Step 2] cluster analysis  (mode={mode})")
        clust_cf  = _clustering_cache_folder(resolved_cache, args.root.name)
        ch        = _cluster_opts_hash(c_opts)
        clust_cp  = _cluster_cache_path(clust_cf, h, ch)

        pre_emb, pre_labels = None, None
        if clust_cp.exists():
            cached = load_clustering_cache(clust_cp, stems_c, y_c)
            if cached is not None:
                pre_emb, pre_labels = cached
                print(f"  [CLUSTER CACHE] {clust_cp.name}")

        cluster_result = detect_clusters(
            X_c, y_c, stems_c, c_opts,
            precomputed_emb    = pre_emb,
            precomputed_labels = pre_labels,
        )

        if pre_labels is None:
            save_clustering_cache(
                clust_cp,
                cluster_result['emb'],
                cluster_result['cluster_labels'],
                stems_c, y_c,
            )
            print(f"  [CLUSTER CACHE] 저장: {clust_cp.name}")

        auto_clusters = resolved_cache / f"{args.root.name}__{h}__clusters.txt"
        auto_stems    = resolved_cache / f"{args.root.name}__{h}__stems.txt"
        auto_summary  = resolved_cache / f"{args.root.name}__{h}__summary.txt"
        report_clusters(cluster_result, save_path=args.cluster_report or auto_clusters)
        report_stems(cluster_result, save_path=auto_stems)
        report_class_summary(cluster_result, save_path=auto_summary)

    # Step 3: UMAP 시각화
    if not args.no_umap:
        import matplotlib.pyplot as _plt
        print("\n[Step 3] UMAP 시각화")
        emb = cluster_result['emb'] if cluster_result is not None else None
        dim_str = f"{args.umap_dims}D"
        common = dict(
            classes           = args.classes,
            stems             = stems,
            cluster_result    = cluster_result,
            emb               = emb,
            n_components      = args.umap_dims,
            feature_group     = args.feature_group if emb is None else None,
            max_pts_per_class = args.umap_max_pts,
            show_match        = args.show_match,
            show              = False,
        )
        plot_umap(X, y,
                  title    = f"UMAP {dim_str} — by Class — {args.root.name}",
                  color_by = 'class',
                  **common)
        plot_umap(X, y,
                  title    = f"UMAP {dim_str} — by Cluster — {args.root.name}",
                  color_by = 'cluster',
                  **common)
        _plt.show()


if __name__ == "__main__":
    main()
