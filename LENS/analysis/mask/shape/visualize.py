"""visualize — ShapeAnalysis → matplotlib Figure (class·cluster 산점도). 저장·표시는 호출자."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ._result import ShapeAnalysis

if TYPE_CHECKING:
    from matplotlib.figure import Figure


def _scatter(ax, emb: np.ndarray, key: np.ndarray, title: str) -> None:
    """임베딩(2D)을 ``key`` 별 색으로 산점. 3D 이상이면 앞 2축만."""
    import matplotlib.pyplot as plt

    _xy = emb[:, :2]
    for _k in sorted(set(key.tolist())):
        _sel = key == _k
        _lab = ("noise" if _k == -1 else str(_k))
        _col = "0.7" if _k == -1 else None
        ax.scatter(_xy[_sel, 0], _xy[_sel, 1], s=18, label=_lab, color=_col, alpha=0.85)
    ax.set_title(title)
    ax.legend(fontsize=7, markerscale=1.2, loc="best")
    ax.set_xticks([]); ax.set_yticks([])


def build_figure(res: ShapeAnalysis) -> "Figure":
    """임베딩을 (좌)class · (우)cluster 두 산점도로 그린 Figure 를 만든다."""
    import matplotlib.pyplot as plt

    _fig, _axs = plt.subplots(1, 2, figsize=(14, 6))
    _scatter(_axs[0], res.embedding, res.labels,   "by class")
    _scatter(_axs[1], res.embedding, res.clusters, "by HDBSCAN cluster")
    _fig.suptitle(f"mask shape embedding (N={len(res.stems)}, D={res.X.shape[1]})", fontsize=13)
    _fig.tight_layout()
    return _fig
