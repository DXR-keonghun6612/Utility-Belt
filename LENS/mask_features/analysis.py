"""클러스터 기반 레이블 일치 분석.

파이프라인:
  1. feature 준비 (UMAP 3D 또는 named feature 선택)
  2. HDBSCAN 전역 클러스터링 (레이블 무관)
  3. 클러스터별 dominant tag + purity 계산
  4. 샘플별 match 분류: O / X / ~ / ?
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

UNCLASSIFIED = "__unclassified__"

_MATCH_ORDER = {'X': 0, '~': 1, '?': 2, 'O': 3}


# ── ClusterOpts ───────────────────────────────────────────────────────────────────

@dataclass
class ClusterOpts:
    """클러스터링 옵션.

    mode:
      'umap'     (기본): 전체 feature → UMAP 3D 임베딩 → HDBSCAN
      'features' : --cluster-features 로 지정한 named feature → HDBSCAN

    cluster_selection_epsilon:
      HDBSCAN 계층 트리에서 이 거리보다 가까운 클러스터는 강제 병합.
      대형 클러스터가 내부 밀도 차이로 과잉 분할되는 것을 방지.

    global_epsilon_ratio:
      전체 공간 거리 분포(p50)의 몇 배를 epsilon으로 쓸지 지정 (0.0~1.0).
      cluster_selection_epsilon 이 직접 지정된 경우 무시됨.
      불균형 클래스(수천 개 vs 수십 개) 환경에서 유용.
    """
    mode: str = "umap"
    feature_cols: list[int] | None = None
    # UMAP
    umap_n_components: int = 3
    umap_n_neighbors: int = 15
    umap_min_dist: float = 0.1
    # HDBSCAN
    min_cluster_size: int = 5
    min_samples: int | None = None
    cluster_selection_epsilon: float | None = None
    global_epsilon_ratio: float | None = None
    # 분류 임계값
    purity_threshold: float = 0.8


# ── Feature helpers ───────────────────────────────────────────────────────────────

def _build_class_id_map(class_names: list[str]) -> dict[str, int]:
    """class 이름 → 순차 정수 ID. 알파벳 오름차순으로 0, 1, 2, ...

    UNCLASSIFIED(noise) 는 실제 class 가 아니므로 ID 부여 대상에서 제외한다.
    """
    return {
        cls: i
        for i, cls in enumerate(
            sorted(c for c in set(class_names) if c != UNCLASSIFIED)
        )
    }


def resolve_feature_cols(names: list[str], feature_names: list[str]) -> list[int]:
    """feature 이름 목록 → 열 인덱스 목록 변환."""
    name_to_idx = {n: i for i, n in enumerate(feature_names)}
    missing = [n for n in names if n not in name_to_idx]
    if missing:
        raise ValueError(f"Unknown feature name(s): {missing}")
    return [name_to_idx[n] for n in names]


def _prepare_features(
    X: np.ndarray,
    opts: ClusterOpts,
) -> tuple[np.ndarray, np.ndarray | None]:
    """feature 준비 → (X_fit, emb | None).

    Returns:
        X_fit : HDBSCAN에 입력할 배열
        emb   : UMAP 임베딩 (mode='umap' 일 때만, 아니면 None)
    """
    from sklearn.preprocessing import StandardScaler, normalize as sk_normalize

    if opts.mode == 'features':
        if not opts.feature_cols:
            raise ValueError("mode='features' requires feature_cols.")
        X_fit = StandardScaler().fit_transform(X[:, opts.feature_cols])
        print(f"  mode=features  dims={len(opts.feature_cols)}  N={len(X)}")
        return X_fit, None

    # mode == 'umap'
    try:
        import umap as umap_lib
    except ImportError:
        raise ImportError("pip install umap-learn") from None

    X_scaled = StandardScaler().fit_transform(X)
    print(f"  mode=umap  n_components={opts.umap_n_components}"
          f"  n_neighbors={opts.umap_n_neighbors}  N={len(X)}")
    print("  computing UMAP embedding ... ", end="", flush=True)
    reducer = umap_lib.UMAP(
        n_components=opts.umap_n_components,
        n_neighbors=opts.umap_n_neighbors,
        min_dist=opts.umap_min_dist,
        random_state=42,
    )
    emb = np.asarray(reducer.fit_transform(X_scaled), dtype=np.float64)
    print("done")
    return emb, emb


# ── Epsilon helpers ───────────────────────────────────────────────────────────────

def _global_distance_scale(X_fit: np.ndarray, n_sample: int = 2000) -> float:
    """X_fit 에서 랜덤 서브샘플로 전체 공간 거리 중앙값을 추정한다.

    N^2 pairwise를 피하기 위해 최대 n_sample 개로 제한.
    """
    from scipy.spatial.distance import pdist
    rng = np.random.default_rng(42)
    n   = len(X_fit)
    if n > n_sample:
        idx    = rng.choice(n, size=n_sample, replace=False)
        X_sub  = X_fit[idx]
    else:
        X_sub  = X_fit
    dists = pdist(X_sub, metric="euclidean")
    return float(np.median(dists))


def _resolve_epsilon(X_fit: np.ndarray, opts: ClusterOpts) -> float | None:
    """ClusterOpts 에서 cluster_selection_epsilon 최종값 결정.

    우선순위:
      1. opts.cluster_selection_epsilon (직접 지정)
      2. opts.global_epsilon_ratio × 전체 거리 중앙값 (자동 계산)
      3. None (비활성)
    """
    if opts.cluster_selection_epsilon is not None:
        return opts.cluster_selection_epsilon

    if opts.global_epsilon_ratio is not None:
        print("  estimating global distance scale ... ", end="", flush=True)
        scale   = _global_distance_scale(X_fit)
        epsilon = opts.global_epsilon_ratio * scale
        print(f"done  (median_dist={scale:.4f}  ratio={opts.global_epsilon_ratio}"
              f"  → epsilon={epsilon:.4f})")
        return epsilon

    return None


# ── Per-class / confusion helpers ────────────────────────────────────────────────

def _build_class_summary(
    records: list[dict],
    cluster_info: dict[int, dict],
    opts: ClusterOpts,
) -> dict[str, dict]:
    """class별 O 비율, noise 비율, 순수 클러스터 수를 집계한다."""
    from collections import defaultdict
    by_cls: dict[str, list] = defaultdict(list)
    for r in records:
        by_cls[r['cls']].append(r)

    summary: dict[str, dict] = {}
    for cls, recs in by_cls.items():
        n = len(recs)
        n_o = sum(1 for r in recs if r['match'] == 'O')
        n_q = sum(1 for r in recs if r['match'] == '?')
        pure_cids = [
            cid for cid, info in cluster_info.items()
            if info['dominant_tag'] == cls
            and not np.isnan(info['purity'])
            and info['purity'] >= opts.purity_threshold
        ]
        summary[cls] = dict(
            n_total          = n,
            n_o              = n_o,
            n_noise          = n_q,
            o_ratio          = n_o / n if n else 0.0,
            noise_ratio      = n_q / n if n else 0.0,
            n_pure_clusters  = len(pure_cids),
            pure_cluster_ids = pure_cids,
        )
    return summary


def _build_confusion_pairs(
    records: list[dict],
    cluster_info: dict[int, dict],
    opts: ClusterOpts,
) -> list[dict]:
    """X 샘플과 ~ 클러스터에서 혼동 쌍(cls_a ↔ cls_b)을 추출한다.

    X 레코드  : cls != group 인 샘플 1개당 1 카운트.
    ~ 클러스터: tag_breakdown의 실제 class 쌍마다 해당 샘플 수 합산.
    """
    from collections import defaultdict
    pair_n:    dict[tuple, int] = defaultdict(int)
    pair_cids: dict[tuple, set] = defaultdict(set)

    for r in records:
        if r['match'] == 'X':
            a, b = r['cls'], r['group']
            if UNCLASSIFIED in (a, b):
                continue
            key = (min(a, b), max(a, b))
            pair_n[key]    += 1
            pair_cids[key].add(r['cluster_id'])

    for cid, info in cluster_info.items():
        if np.isnan(info['purity']) or info['purity'] >= opts.purity_threshold:
            continue
        real = {k: v for k, v in info['tag_breakdown'].items() if k != UNCLASSIFIED}
        cls_list = sorted(real)
        for i, a in enumerate(cls_list):
            for b in cls_list[i + 1:]:
                key = (min(a, b), max(a, b))
                pair_n[key]    += real[a] + real[b]
                pair_cids[key].add(cid)

    return sorted(
        [
            dict(cls_a=a, cls_b=b,
                 n_samples=n,
                 cluster_ids=sorted(pair_cids[(a, b)]))
            for (a, b), n in pair_n.items()
        ],
        key=lambda x: -x['n_samples'],
    )


# ── Main: detect_clusters ─────────────────────────────────────────────────────────

def detect_clusters(
    X: np.ndarray,
    y: np.ndarray,
    stems: list[str],
    opts: ClusterOpts | None = None,
    *,
    precomputed_emb: np.ndarray | None = None,
    precomputed_labels: np.ndarray | None = None,
) -> dict:
    """전역 HDBSCAN 클러스터링 후 레이블 일치 분석.

    Returns::

        {
          'records'            : [{ cls, group, purity, match, stem, cluster_id, idx }],
          'cluster_info'       : { cid: { dominant_tag, purity, size, tag_breakdown } },
          'confusion_clusters' : { cid: info },   # purity < purity_threshold
          'cluster_labels'     : np.ndarray (N,),
          'emb'                : np.ndarray (N, k) | None,
          'opts'               : ClusterOpts,
        }

    match 값:
      'O' : own_tag == dominant_tag  AND  purity ≥ threshold
      'X' : own_tag != dominant_tag  AND  purity ≥ threshold  → 오분류 후보
      '~' : purity < threshold                                 → 혼동 클러스터
      '?' : noise (cluster_id == -1)                           → 미분류
    """
    if opts is None:
        opts = ClusterOpts()

    if precomputed_emb is not None and precomputed_labels is not None:
        emb            = precomputed_emb
        cluster_labels = precomputed_labels
        n_clusters = len(set(cluster_labels.tolist())) - (1 if -1 in cluster_labels else 0)
        n_noise    = int((cluster_labels == -1).sum())
        print(f"  [CLUSTER CACHE] 재사용  clusters={n_clusters}  noise={n_noise}")
    else:
        try:
            import hdbscan as hdbscan_lib
        except ImportError:
            raise ImportError("pip install hdbscan") from None

        X_fit, emb = _prepare_features(X, opts)

        epsilon = _resolve_epsilon(X_fit, opts)

        min_s = opts.min_samples if opts.min_samples is not None else opts.min_cluster_size
        eps_str = f"{epsilon:.4f}" if epsilon is not None else "None"
        print(f"  HDBSCAN: min_cluster_size={opts.min_cluster_size}  min_samples={min_s}"
              f"  epsilon={eps_str}  purity_thr={opts.purity_threshold:.0%}")
        print("  clustering ... ", end="", flush=True)
        hdbscan_kwargs: dict = dict(
            min_cluster_size=opts.min_cluster_size,
            min_samples=min_s,
        )
        if epsilon is not None:
            hdbscan_kwargs["cluster_selection_epsilon"] = epsilon
        clusterer = hdbscan_lib.HDBSCAN(**hdbscan_kwargs)
        cluster_labels = clusterer.fit_predict(X_fit)
        n_clusters = len(set(cluster_labels.tolist())) - (1 if -1 in cluster_labels else 0)
        n_noise    = int((cluster_labels == -1).sum())
        print(f"done  (clusters={n_clusters}  noise={n_noise})")

    if n_clusters == 0:
        print("  [WARN] 클러스터가 하나도 없습니다. min_cluster_size를 줄여보세요.")

    # 클러스터별 dominant tag + purity
    # __unclassified__ 는 실제 class 가 아니므로 purity 계산에서 제외한다.
    cluster_info: dict[int, dict] = {}
    for cid in sorted(set(cluster_labels.tolist())):
        if cid == -1:
            continue
        mask       = cluster_labels == cid
        tags       = y[mask]
        real_tags  = tags[tags != UNCLASSIFIED]

        if len(real_tags) == 0:
            dominant = UNCLASSIFIED
            purity   = float('nan')
        else:
            uniq, cnts = np.unique(real_tags, return_counts=True)
            best_i     = int(np.argmax(cnts))
            dominant   = str(uniq[best_i])
            purity     = float(cnts[best_i]) / float(len(real_tags))

        uniq_all, cnts_all = np.unique(tags, return_counts=True)
        cluster_info[cid] = dict(
            dominant_tag  = dominant,
            purity        = purity,
            size          = int(mask.sum()),
            tag_breakdown = {str(t): int(c) for t, c in zip(uniq_all, cnts_all)},
        )

    # 샘플별 record
    stems_arr = np.array(stems)
    records: list[dict] = []
    for i in range(len(X)):
        cid     = int(cluster_labels[i])
        own_tag = str(y[i])
        stem    = str(stems_arr[i])

        if cid == -1:
            group  = UNCLASSIFIED
            purity = float('nan')
            match  = '?'
        else:
            info   = cluster_info[cid]
            group  = info['dominant_tag']
            purity = info['purity']
            if np.isnan(purity) or purity < opts.purity_threshold:
                match = '~'
            elif own_tag == group:
                match = 'O'
            else:
                match = 'X'

        records.append(dict(
            cls        = own_tag,
            group      = group,
            purity     = purity,
            match      = match,
            stem       = stem,
            cluster_id = cid,
            idx        = i,
        ))

    confusion_clusters = {
        cid: info for cid, info in cluster_info.items()
        if np.isnan(info['purity']) or info['purity'] < opts.purity_threshold
    }

    n_o = sum(1 for r in records if r['match'] == 'O')
    n_x = sum(1 for r in records if r['match'] == 'X')
    n_t = sum(1 for r in records if r['match'] == '~')
    n_q = sum(1 for r in records if r['match'] == '?')
    print(f"  O={n_o}  X={n_x}  ~={n_t}  ?={n_q}"
          f"  confusion_clusters={len(confusion_clusters)}")

    if n_clusters > 0 and len(set(y.tolist())) > 0:
        ratio = n_clusters / len(set(y.tolist()))
        if ratio > 3:
            print(f"  [WARN] clusters/classes={ratio:.1f} > 3 → min_cluster_size 값을 키워보세요.")

    class_summary   = _build_class_summary(records, cluster_info, opts)
    confusion_pairs = _build_confusion_pairs(records, cluster_info, opts)

    return dict(
        records            = records,
        cluster_info       = cluster_info,
        confusion_clusters = confusion_clusters,
        cluster_labels     = cluster_labels,
        emb                = emb,
        opts               = opts,
        class_summary      = class_summary,
        confusion_pairs    = confusion_pairs,
    )
