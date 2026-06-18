"""폴더 단위 일괄 처리 + 캐시.

폴더 구조 가정:
    <root>/<class_name>/<image>.png
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .feature_extract import FeatureOpts, PCA_RELIABLE_RATIO, extract_features


_IMG_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')

# {class_name: (X, feat_names, stems, ratios)}
ClassData = dict[str, tuple[np.ndarray, list[str], list[str], np.ndarray]]


# ── Mask loading ──────────────────────────────────────────────────────────────────

def load_mask(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise OSError(f"Cannot read image: {path}")
    return img > 0


# ── Per-class extraction ──────────────────────────────────────────────────────────

def process_class_folder(
    class_dir: Path,
    opts: FeatureOpts,
) -> tuple[np.ndarray, list[str], list[str], np.ndarray]:
    """단일 class 폴더 내 모든 mask → feature matrix."""
    paths = sorted(p for p in class_dir.iterdir() if p.suffix.lower() in _IMG_EXTS)
    if not paths:
        return np.empty((0, 0)), [], [], np.empty(0)

    vecs:   list[np.ndarray] = []
    stems:  list[str]        = []
    ratios: list[float]      = []
    feat_names: list[str]    = []

    for path in paths:
        try:
            result = extract_features(load_mask(path), opts)
            vecs.append(result.vector)
            stems.append(path.stem)
            ratios.append(result.debug['eigenvalue_ratio'])
            if not feat_names:
                feat_names = result.names
        except Exception as e:
            print(f"  [WARN] {path.name}: {e}")

    if not vecs:
        return np.empty((0, 0)), [], [], np.empty(0)

    return np.stack(vecs), feat_names, stems, np.array(ratios)


def scan_class_dirs(root: Path) -> list[Path]:
    dirs = sorted(d for d in root.iterdir() if d.is_dir())
    if not dirs:
        raise ValueError(f"No class subdirectories found in {root}")
    return dirs


def collect_class_data(class_dirs: list[Path], opts: FeatureOpts) -> ClassData:
    class_data: ClassData = {}
    for class_dir in class_dirs:
        class_name = class_dir.name
        X_cls, names, stems, ratios = process_class_folder(class_dir, opts)
        if X_cls.shape[0] == 0:
            print(f"[SKIP] {class_name}: no valid masks")
            continue
        class_data[class_name] = (X_cls, names, stems, ratios)
        n_bad = int((ratios < PCA_RELIABLE_RATIO).sum())
        print(
            f"[OK]   {class_name:30s}  {X_cls.shape[0]:4d} samples"
            f"  PCA unreliable: {n_bad:3d} ({n_bad / len(ratios) * 100:.1f}%)"
        )
    return class_data


def merge_class_data(
    class_data: ClassData,
) -> tuple[np.ndarray, np.ndarray, list[str], list[str], np.ndarray]:
    if not class_data:
        raise ValueError("class_data is empty — nothing to merge.")

    all_X:      list[np.ndarray] = []
    all_y:      list[str]        = []
    all_stems:  list[str]        = []
    all_ratios: list[np.ndarray] = []
    feat_names: list[str]        = []

    for class_name, (X_cls, names, stems, ratios) in class_data.items():
        all_X.append(X_cls)
        all_y.extend([class_name] * X_cls.shape[0])
        all_stems.extend(stems)
        all_ratios.append(ratios)
        if not feat_names:
            feat_names = names

    return (
        np.vstack(all_X),
        np.array(all_y),
        feat_names,
        all_stems,
        np.concatenate(all_ratios),
    )


# ── Cache helpers ─────────────────────────────────────────────────────────────────

def _opts_hash(opts: FeatureOpts) -> str:
    import dataclasses, hashlib, json
    return hashlib.md5(
        json.dumps(dataclasses.asdict(opts), sort_keys=True).encode()
    ).hexdigest()[:8]


def _pca_cache_folder(cache_dir: Path, root_name: str) -> Path:
    return cache_dir / f".{root_name}__pca_cache"


# 하위 호환 alias
def _cache_folder(cache_dir: Path, root_name: str) -> Path:
    return _pca_cache_folder(cache_dir, root_name)


def _class_cache_path(cache_folder: Path, class_name: str, h: str) -> Path:
    return cache_folder / f"{class_name}__{h}.npz"


# ── Clustering cache ──────────────────────────────────────────────────────────────

def _clustering_cache_folder(cache_dir: Path, root_name: str) -> Path:
    return cache_dir / f".{root_name}__clustering_cache"


def _cluster_opts_hash(opts) -> str:
    """ClusterOpts → 8자리 해시."""
    import dataclasses, hashlib, json
    return hashlib.md5(
        json.dumps(dataclasses.asdict(opts), sort_keys=True, default=str).encode()
    ).hexdigest()[:8]


def _cluster_cache_path(clust_folder: Path, feat_hash: str, cluster_hash: str) -> Path:
    return clust_folder / f"{feat_hash}__{cluster_hash}.npz"


def save_clustering_cache(
    path: Path,
    emb: np.ndarray | None,
    cluster_labels: np.ndarray,
    stems: list[str],
    y: np.ndarray,
) -> None:
    kwargs: dict = dict(
        cluster_labels = cluster_labels,
        stems          = np.array(stems, dtype=object),
        y              = np.array(y,     dtype=object),
    )
    if emb is not None:
        kwargs['emb'] = emb
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **kwargs)


def load_clustering_cache(
    path: Path,
    stems: list[str],
    y: np.ndarray,
) -> tuple[np.ndarray | None, np.ndarray] | None:
    """(emb | None, cluster_labels) 반환. stems/y 불일치 시 None."""
    d = np.load(path, allow_pickle=True)
    if d['stems'].tolist() != stems or d['y'].tolist() != y.tolist():
        print("[CLUSTER CACHE] 데이터 불일치 — 캐시 무시")
        return None
    emb = d['emb'] if 'emb' in d.files else None
    return emb, d['cluster_labels']


def _save_class_cache(
    path: Path,
    X: np.ndarray,
    names: list[str],
    stems: list[str],
    ratios: np.ndarray,
) -> None:
    np.savez_compressed(
        path,
        X=X,
        names=np.array(names, dtype=object),
        stems=np.array(stems, dtype=object),
        ratios=ratios,
    )


def _load_class_cache(path: Path) -> tuple[np.ndarray, list[str], list[str], np.ndarray]:
    d = np.load(path, allow_pickle=True)
    return d["X"], d["names"].tolist(), d["stems"].tolist(), d["ratios"]


def _feature_names_path(cache_folder: Path, h: str) -> Path:
    return cache_folder / f"feature_names__{h}.json"


def save_feature_names(cache_folder: Path, h: str, names: list[str]) -> None:
    import json
    path = _feature_names_path(cache_folder, h)
    path.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")


def load_feature_names(cache_folder: Path, h: str) -> list[str] | None:
    import json
    path = _feature_names_path(cache_folder, h)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── CSV export ────────────────────────────────────────────────────────────────────

def export_to_csv(
    X: np.ndarray,
    y: np.ndarray,
    names: list[str],
    stems: list[str],
    ratios: np.ndarray,
    path: Path,
) -> None:
    import pandas as pd
    df = pd.DataFrame(X, columns=names)
    df.insert(0, "eigenvalue_ratio", ratios)
    df.insert(0, "stem", stems)
    df.insert(0, "class", y)
    df.to_csv(path, index=False, float_format="%.17g")
    print(f"[CSV] {len(df)} rows → {path}")


# ── process_folder ────────────────────────────────────────────────────────────────

def process_folder(
    root: Path,
    opts: FeatureOpts | None = None,
    cache_dir: Path | None = None,
    export_csv: bool = False,
) -> tuple[np.ndarray, np.ndarray, list[str], list[str], np.ndarray]:
    """root/<class_name>/*.png 구조에서 feature matrix 일괄 추출.

    캐시: class별 <cache_dir>/<root.name>__cache/<class>__<opts_hash>.npz
    """
    from .report import report_pca_reliability

    if opts is None:
        opts = FeatureOpts()

    resolved_cache = root.parent if cache_dir is None else cache_dir
    cache_folder   = _pca_cache_folder(resolved_cache, root.name)
    h = _opts_hash(opts)

    class_dirs = scan_class_dirs(root)
    class_data: ClassData = {}

    for class_dir in class_dirs:
        class_name = class_dir.name
        cp = _class_cache_path(cache_folder, class_name, h)

        if cp.exists():
            X_cls, names, stems, ratios = _load_class_cache(cp)
            n_bad = int((ratios < PCA_RELIABLE_RATIO).sum())
            print(
                f"[CACHE] {class_name:30s}  {X_cls.shape[0]:4d} samples"
                f"  PCA unreliable: {n_bad:3d} ({n_bad / len(ratios) * 100:.1f}%)"
            )
        else:
            X_cls, names, stems, ratios = process_class_folder(class_dir, opts)
            if X_cls.shape[0] == 0:
                print(f"[SKIP]  {class_name}: no valid masks")
                continue
            cache_folder.mkdir(parents=True, exist_ok=True)
            _save_class_cache(cp, X_cls, names, stems, ratios)
            if not _feature_names_path(cache_folder, h).exists():
                save_feature_names(cache_folder, h, names)
            n_bad = int((ratios < PCA_RELIABLE_RATIO).sum())
            print(
                f"[OK]    {class_name:30s}  {X_cls.shape[0]:4d} samples"
                f"  PCA unreliable: {n_bad:3d} ({n_bad / len(ratios) * 100:.1f}%)"
            )

        class_data[class_name] = (X_cls, names, stems, ratios)

    if not class_data:
        raise ValueError("No samples successfully extracted.")

    X, y, feat_names, all_stems, all_ratios = merge_class_data(class_data)
    print(f"\nTotal: {X.shape[0]} samples  D={X.shape[1]}  classes={len(class_data)}")
    report_pca_reliability(y, all_ratios)

    if export_csv:
        csv_path = resolved_cache / f"{root.name}__{h}.csv"
        export_to_csv(X, y, feat_names, all_stems, all_ratios, csv_path)

    return X, y, feat_names, all_stems, all_ratios
