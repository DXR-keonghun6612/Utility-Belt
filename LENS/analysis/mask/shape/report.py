"""report — ShapeAnalysis → 텍스트 (클러스터 구성 · 클래스↔클러스터 일치)."""

from __future__ import annotations

from collections import Counter

import numpy as np

from ._result import ShapeAnalysis


def _cluster_purity(labels: np.ndarray, clusters: np.ndarray) -> list[tuple]:
    """클러스터별 (id, 크기, dominant class, purity) — purity = dominant 비율."""
    _rows = []
    for _c in sorted(set(clusters.tolist())):
        _sel = clusters == _c
        _cnt = Counter(labels[_sel].tolist())
        _dom, _n = _cnt.most_common(1)[0]
        _rows.append((_c, int(_sel.sum()), _dom, _n / int(_sel.sum())))
    return _rows


def format_report(res: ShapeAnalysis) -> str:
    """``ShapeAnalysis`` 를 사람이 읽는 리포트 문자열로."""
    _n = len(res.stems)
    _n_clusters = len({_c for _c in res.clusters.tolist() if _c != -1})
    _noise = int((res.clusters == -1).sum())
    _classes = sorted(set(res.labels.tolist()))

    _lines = [
        "═" * 64,
        " mask 형상 임베딩 분석",
        "═" * 64,
        f" mask {_n}개  ·  feature {res.X.shape[1]}차원  ·  class {len(_classes)}종",
        f" 클러스터 {_n_clusters}개  ·  noise {_noise}개  ·  임베딩 {res.embedding.shape[1]}D",
        "",
        "  [클러스터]  크기   dominant class           purity",
        "  " + "-" * 56,
    ]
    for _c, _sz, _dom, _pur in _cluster_purity(res.labels, res.clusters):
        _name = "noise" if _c == -1 else f"#{_c}"
        _lines.append(f"  {_name:<10} {_sz:>4}   {_dom:<24} {_pur:6.2f}")

    if len(_classes) > 1:                          # class 라벨이 있으면 class→cluster 분포도
        _lines += ["", "  [class]  → 클러스터 분포", "  " + "-" * 56]
        for _cls in _classes:
            _sel = res.labels == _cls
            _dist = Counter(res.clusters[_sel].tolist())
            _txt = ", ".join(f"#{_k if _k != -1 else 'noise'}:{_v}"
                             for _k, _v in sorted(_dist.items()))
            _lines.append(f"  {_cls:<22} {_txt}")

    _lines.append("═" * 64)
    return "\n".join(_lines)
