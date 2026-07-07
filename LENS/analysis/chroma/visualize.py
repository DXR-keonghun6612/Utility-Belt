"""visualize — ChromaDiag → matplotlib Figure (저장·표시는 호출자)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ._result import ChromaDiag

if TYPE_CHECKING:
    from matplotlib.figure import Figure


def _reference_color_map(diag: ChromaDiag) -> np.ndarray:
    """픽셀별 기준색 — 크로마 평균(2채널)을 실제 RGB 로 역변환. 저신뢰 픽셀은 회색."""
    (m0, m1) = diag.mean
    _rgb = diag.space.chroma_to_rgb(m0, m1).astype(np.float32) / 255.0
    _rgb[~diag.valid_mask] = 0.85
    return _rgb


def build_figure(diag: ChromaDiag) -> "Figure":
    """6개 패널(mean0/std0/mean1/std1/coverage/기준색) Figure 를 만든다.

    마지막 패널은 크로마 평균을 실제 색으로 되돌린 **픽셀별 기준색**(저신뢰=회색)이며, 우하단
    inset 에 **전역 기준색** swatch 를 함께 띄운다. 나머지 맵의 저신뢰 픽셀(n < min_count)은
    NaN 처리해 회색으로 뺀다. 저장/표시는 호출자가 결정한다 (CLI: savefig/show, GUI: canvas).
    """
    import matplotlib.pyplot as plt

    _sp = diag.space
    _l0, _l1 = _sp.labels
    _b0, _b1 = _sp.bins
    _cmap0 = "hsv" if _sp.circular[0] else "viridis"
    _cmap1 = "hsv" if _sp.circular[1] else "viridis"

    _bg = ~diag.valid_mask
    def _m(arr):
        _a = arr.astype(np.float32).copy()
        _a[_bg] = np.nan
        return _a

    (m0, m1), (s0, s1) = diag.mean, diag.std
    _panels = [
        (f"mean {_l0}", _m(m0), _cmap0,    0, _b0),
        (f"std {_l0}",  _m(s0), "magma",   0, None),
        (f"mean {_l1}", _m(m1), _cmap1,    0, _b1),
        (f"std {_l1}",  _m(s1), "magma",   0, None),
        ("coverage n",  np.where(diag.n > 0, diag.n, np.nan), "cividis", 0, None),
    ]
    _fig, _axs = plt.subplots(2, 3, figsize=(16, 9))
    _axs = _axs.ravel()
    for _ax, (_title, _data, _cmap, _vmin, _vmax) in zip(_axs, _panels):
        _cm = plt.get_cmap(_cmap).copy()
        _cm.set_bad(color="0.85")
        _im = _ax.imshow(_data, cmap=_cm, vmin=_vmin, vmax=_vmax)
        _ax.set_title(_title)
        _ax.axis("off")
        _fig.colorbar(_im, ax=_ax, fraction=0.046, pad=0.04)

    # 기준색 패널 — 픽셀별 RGB + 전역 기준색 두 swatch (sample-weighted vs 2중 robust vote)
    _ref_ax = _axs[5]
    _ref_ax.imshow(_reference_color_map(diag))
    _ref_ax.set_title("reference color (per-pixel / global · robust)")
    _ref_ax.axis("off")
    _g_w = diag.space.chroma_to_rgb(diag.g_mean[0], diag.g_mean[1]).astype(np.float32) / 255.0
    _g_r = diag.space.chroma_to_rgb(diag.g_robust[0], diag.g_robust[1]).astype(np.float32) / 255.0
    for _x, _rgb, _lab in ((0.52, _g_w, "global"), (0.76, _g_r, "robust")):
        _ins = _ref_ax.inset_axes((_x, 0.04, 0.20, 0.18))
        _ins.imshow(np.broadcast_to(_rgb, (1, 1, 3)))
        _ins.set_title(_lab, fontsize=8, pad=2)
        _ins.set_xticks([]); _ins.set_yticks([])
        for _s in _ins.spines.values():
            _s.set_edgecolor("white"); _s.set_linewidth(1.0)

    _fig.suptitle(f"background chroma per-pixel stats (space={_sp.name}, gray=low-confidence px)",
                  fontsize=14)
    _fig.tight_layout()
    return _fig
