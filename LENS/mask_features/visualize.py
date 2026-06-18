"""UMAP 2D / 3D 시각화."""

from __future__ import annotations

import numpy as np

from .feature_extract import _FEATURE_GROUPS
from .analysis import UNCLASSIFIED, _build_class_id_map


def plot_umap(
    X: np.ndarray,
    y: np.ndarray,
    classes: list[str] | None = None,
    *,
    stems: list[str] | None = None,
    cluster_result: dict | None = None,
    emb: np.ndarray | None = None,
    n_components: int = 3,
    feature_group: str | None = None,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    normalize: bool = True,
    max_pts_per_class: int = 200,
    title: str | None = None,
    show: bool = True,
    show_match: bool = False,
    color_by: str = 'class',
) -> tuple:
    """feature matrix를 UMAP으로 2D 또는 3D 투영 후 클래스별 scatter 시각화.

    emb 파라미터:
      detect_clusters 가 반환한 임베딩을 그대로 받으면 UMAP 재계산을 생략한다.
      emb.shape[1] 로 2D / 3D 를 자동 판별한다.
      emb 가 None 이면 n_components (2 또는 3) 로 내부 UMAP 계산 후 투영한다.

    show_match=True 이면 cluster_result 의 match 정보로 마커를 구분한다:
      O (일치)   : ● 기본 (서브샘플)
      X (오분류) : ★ 붉은 테두리 (전부)
      ~ (혼동)   : △ 주황 테두리 (전부)
      ? (미분류) : × 회색 테두리 (전부)
    show_match=False (기본) 이면 모든 점을 단일 마커로 표시한다.

    color_by:
      'class'   (기본): 클래스(사물 ID)별 색상.
      'cluster': 클러스터 ID별 색상. noise(-1) 는 회색 ×.

    Returns:
        (fig, ax, emb)
    """
    import matplotlib.pyplot as plt
    from sklearn.preprocessing import StandardScaler

    stems_arr = np.array(stems) if stems is not None else None

    # 클래스 필터링 (X, y, stems, emb 동시에)
    if classes is not None:
        mask      = np.isin(y, classes)
        n_selected = int(mask.sum())
        X    = X[mask]
        y    = y[mask]
        if stems_arr is not None:
            stems_arr = stems_arr[mask]
        if emb is not None:
            # emb가 이미 class-filtered 상태(len==n_selected)면 재필터 불필요
            if len(emb) != n_selected:
                emb = emb[mask]

    if len(X) == 0:
        raise ValueError("No samples after class filtering.")

    # emb 없으면 자체 계산
    if emb is None:
        try:
            import umap as _umap
        except ImportError:
            raise ImportError("pip install umap-learn") from None

        # UMAP 입력 feature 결정
        # 우선순위: feature_group > cluster_result의 feature_cols(mode='features') > 전체
        if feature_group is not None:
            if feature_group not in _FEATURE_GROUPS:
                raise ValueError(f"feature_group must be one of {list(_FEATURE_GROUPS)}")
            sel = _FEATURE_GROUPS[feature_group]
            X_for_umap = X[:, sel] if isinstance(sel, list) else X[:, sel[0]:sel[1]]
        elif (
            cluster_result is not None
            and cluster_result.get('opts') is not None
            and getattr(cluster_result['opts'], 'mode', None) == 'features'
            and cluster_result['opts'].feature_cols
        ):
            X_for_umap = X[:, cluster_result['opts'].feature_cols]
        else:
            X_for_umap = X

        valid = np.isfinite(X_for_umap).all(axis=1)
        if not valid.all():
            print(f"[WARN] {(~valid).sum()} samples with NaN/Inf removed before UMAP.")
            X_for_umap = X_for_umap[valid]
            y = y[valid]
            if stems_arr is not None:
                stems_arr = stems_arr[valid]

        X_input = StandardScaler().fit_transform(X_for_umap) if normalize else X_for_umap.astype(np.float64)
        reducer = _umap.UMAP(
            n_components=n_components, n_neighbors=n_neighbors,
            min_dist=min_dist, random_state=42,
        )
        emb = np.asarray(reducer.fit_transform(X_input), dtype=np.float64)

    dims = emb.shape[1]
    if dims not in (2, 3):
        raise ValueError(f"emb must be 2D or 3D, got {dims}D")

    # match 정보 준비
    stem_to_match: dict[str, str] = {}
    if cluster_result is not None and stems_arr is not None:
        for r in cluster_result['records']:
            stem_to_match[r['stem']] = r['match']

    unique_classes = sorted(set(y.tolist()))
    cmap      = plt.cm.get_cmap("tab20", len(unique_classes))
    color_map = {cls: cmap(i) for i, cls in enumerate(unique_classes)}

    fig = plt.figure(figsize=(12, 8))
    if dims == 3:
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
        ax = fig.add_subplot(111, projection="3d")
    else:
        ax = fig.add_subplot(111)

    rng = np.random.default_rng(42)

    def _subsample(idx: np.ndarray, n: int) -> np.ndarray:
        if len(idx) <= n:
            return idx
        return idx[np.sort(rng.choice(len(idx), size=n, replace=False))]

    def _sc(ax, idx: np.ndarray, **kwargs) -> None:
        """2D / 3D 통합 scatter 호출."""
        if dims == 3:
            ax.scatter(emb[idx, 0], emb[idx, 1], emb[idx, 2], **kwargs)
        else:
            ax.scatter(emb[idx, 0], emb[idx, 1], **kwargs)

    if color_by == 'cluster' and cluster_result is not None and stems_arr is not None:
        # ── cluster ID 기준 색상 ──────────────────────────────────────────
        stem_to_cid_sc = {r['stem']: r['cluster_id'] for r in cluster_result['records']}
        cids_arr  = np.array([stem_to_cid_sc.get(str(s), -1) for s in stems_arr])
        real_cids = sorted(c for c in set(cids_arr.tolist()) if c != -1)
        n_real    = max(len(real_cids), 1)
        cmap_c    = plt.cm.get_cmap('tab20' if n_real <= 20 else 'hsv', n_real)
        cmap_c_map = {cid: cmap_c(i) for i, cid in enumerate(real_cids)}

        if dims == 2:
            _draw_regions(ax, emb, cids_arr, cmap_c_map)

        noise_idx = np.where(cids_arr == -1)[0]
        if len(noise_idx):
            _sc(ax, noise_idx, c=['#999999'], marker='x', s=20, alpha=0.4)

        for cid in real_cids:
            idx = _subsample(np.where(cids_arr == cid)[0], max_pts_per_class)
            if len(idx):
                _sc(ax, idx, c=[cmap_c_map[cid]], marker='o', s=18, alpha=0.65)

    else:
        # ── class(사물 ID) 기준 색상 ─────────────────────────────────────
        if dims == 2 and cluster_result is not None and stems_arr is not None:
            # 영역은 클러스터 단위로 그리고, 색만 dominant class 색으로 표시
            # impure(혼동) 클러스터는 제외 — 여러 class 색 hull이 겹쳐 난잡해지는 것을 방지
            _stem_to_cid = {r['stem']: r['cluster_id'] for r in cluster_result['records']}
            _cids_arr    = np.array([_stem_to_cid.get(str(s), -1) for s in stems_arr])
            _c_info      = cluster_result['cluster_info']
            _purity_thr  = getattr(cluster_result.get('opts'), 'purity_threshold', 0.8)
            _cluster_colors = {
                cid: color_map[info['dominant_tag']]
                for cid, info in _c_info.items()
                if info['dominant_tag'] in color_map
                and not np.isnan(info['purity'])
                and info['purity'] >= _purity_thr
            }
            _draw_regions(ax, emb, _cids_arr, _cluster_colors)

        for cls in unique_classes:
            cls_idx = np.where(y == cls)[0]
            color   = [color_map[cls]]
            n_total = len(cls_idx)

            if show_match and stems_arr is not None and stem_to_match:
                def _by_match(idx_arr: np.ndarray, m: str) -> np.ndarray:
                    return idx_arr[np.array([stem_to_match.get(stems_arr[i], 'O') == m
                                             for i in idx_arr])]

                o_idx    = _subsample(_by_match(cls_idx, 'O'), max_pts_per_class)
                x_idx    = _by_match(cls_idx, 'X')
                t_idx    = _by_match(cls_idx, '~')
                q_idx    = _by_match(cls_idx, '?')
                n_o_full = len(_by_match(cls_idx, 'O'))
                o_label  = (f"{cls} (n={n_total}"
                            + (f", show {len(o_idx)}/{n_o_full}" if len(o_idx) < n_o_full else "")
                            + ")")

                if len(o_idx):
                    _sc(ax, o_idx, c=color, marker="o", s=18, alpha=0.6, label=o_label)
                if len(x_idx):
                    _sc(ax, x_idx, c=color, marker="*", s=120, alpha=1.0,
                        edgecolors="red", linewidths=1.0,
                        label=f"{cls} ★X ({len(x_idx)})")
                if len(t_idx):
                    _sc(ax, t_idx, c=color, marker="^", s=60, alpha=0.9,
                        edgecolors="orange", linewidths=0.8,
                        label=f"{cls} △~ ({len(t_idx)})")
                if len(q_idx):
                    _sc(ax, q_idx, c=color, marker="x", s=40, alpha=0.7,
                        label=f"{cls} ×? ({len(q_idx)})")
            else:
                show_idx = _subsample(cls_idx, max_pts_per_class)
                label    = (f"{cls} (n={n_total}"
                            + (f", show {len(show_idx)}" if len(show_idx) < n_total else "")
                            + ")")
                _sc(ax, show_idx, c=color, label=label, s=18, alpha=0.75)

    _bbox = dict(boxstyle='round,pad=0.25', fc='white', alpha=0.70, ec='none')
    cls_id_map = _build_class_id_map(y.tolist())

    def _text(cx: float, cy: float, label: str, cz: float | None = None) -> None:
        if dims == 3 and cz is not None:
            ax.text(cx, cy, cz, label, fontsize=6,
                    ha='center', va='center', bbox=_bbox, zorder=5)
        else:
            ax.text(cx, cy, label, fontsize=6,
                    ha='center', va='center', bbox=_bbox, zorder=5)

    if color_by == 'cluster' and cluster_result is not None and stems_arr is not None:
        # cluster 뷰: C{id} + #{dominant_class_id} + purity
        from collections import defaultdict
        stem_to_cid: dict[str, int] = {
            r['stem']: r['cluster_id'] for r in cluster_result['records']
        }
        c_info: dict = cluster_result['cluster_info']
        cid_indices: dict[int, list[int]] = defaultdict(list)
        for i, stem in enumerate(stems_arr):
            cid = stem_to_cid.get(str(stem), -1)
            if cid != -1:
                cid_indices[cid].append(i)

        for cid, idx_list in sorted(cid_indices.items()):
            if cid not in c_info:
                continue
            pts   = emb[idx_list]
            cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
            cz    = float(pts[:, 2].mean()) if dims == 3 else None
            info  = c_info[cid]
            total = info['size']
            breakdown_lines = []
            for tag, cnt in sorted(info['tag_breakdown'].items(), key=lambda x: -x[1]):
                pct = cnt / total
                if tag == UNCLASSIFIED:
                    breakdown_lines.append(f"?:{pct:.0%}")
                else:
                    breakdown_lines.append(f"#{cls_id_map.get(tag, '?')}:{pct:.0%}")
            label = f"C{cid}\n" + "\n".join(breakdown_lines)
            _text(cx, cy, label, cz)

    elif color_by == 'class':
        # class 뷰: 각 class 중심에 #class_id 만 표시
        for cls in unique_classes:
            idx = np.where(y == cls)[0]
            if len(idx) == 0:
                continue
            pts    = emb[idx]
            cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
            cz     = float(pts[:, 2].mean()) if dims == 3 else None
            _text(cx, cy, f"#{cls_id_map.get(cls, '?')}", cz)

    dim_str = f"{dims}D"
    _feat_desc = feature_group or (
        f"feature_cols({len(cluster_result['opts'].feature_cols)})"
        if (cluster_result is not None
            and getattr(cluster_result.get('opts'), 'mode', None) == 'features'
            and cluster_result['opts'].feature_cols)
        else 'all features'
    )
    auto_title = f"UMAP {dim_str} — {_feat_desc}"
    ax.set_title(title or auto_title, pad=12)
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    if dims == 3:
        ax.set_zlabel("UMAP-3")
    plt.tight_layout()

    if show:
        plt.show()

    return fig, ax, emb


def _draw_regions(
    ax,
    emb: np.ndarray,
    groups_arr: np.ndarray,
    group_colors: dict,
) -> None:
    """2D 전용 — 그룹별 Convex Hull(반투명 채움) + KDE 등고선.

    groups_arr : 각 점의 그룹 레이블 (cluster ID 또는 class 이름).
    group_colors: {레이블 → matplotlib color} 매핑.
    """
    try:
        from scipy.spatial import ConvexHull
        from scipy.stats import gaussian_kde
        from matplotlib.patches import Polygon as MplPolygon
    except ImportError:
        print("[WARN] scipy 미설치 — 영역 표시 생략 (pip install scipy)")
        return

    for label, color in group_colors.items():
        pts   = emb[groups_arr == label, :2]
        rgba3 = color[:3]

        # ── Convex Hull
        if len(pts) >= 3:
            try:
                hull = ConvexHull(pts)
                ax.add_patch(MplPolygon(
                    pts[hull.vertices], closed=True,
                    fc=(*rgba3, 0.08), ec=(*rgba3, 0.35),
                    lw=0.7, zorder=1,
                ))
            except Exception:
                pass

        # ── KDE contour (외곽 밀도선)
        if len(pts) >= 5:
            try:
                kde    = gaussian_kde(pts.T, bw_method='scott')
                spread = (pts.max(axis=0) - pts.min(axis=0)).max()
                margin = max(spread * 0.2, 0.1)
                x0, x1 = pts[:, 0].min() - margin, pts[:, 0].max() + margin
                y0, y1 = pts[:, 1].min() - margin, pts[:, 1].max() + margin
                gx, gy = np.linspace(x0, x1, 40), np.linspace(y0, y1, 40)
                xx, yy = np.meshgrid(gx, gy)
                zz = kde(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
                ax.contour(xx, yy, zz, levels=[zz.max() * 0.2],
                           colors=[color], alpha=0.65, linewidths=0.9, zorder=2)
            except Exception:
                pass


# 하위 호환 alias
plot_umap_3d = plot_umap
