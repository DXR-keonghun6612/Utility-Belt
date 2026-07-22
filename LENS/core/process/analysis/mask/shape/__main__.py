"""CLI — mask 폴더 형상 임베딩 분석. ``python -m LENS.analysis.mask.shape --root ...``"""

from __future__ import annotations

import argparse
from pathlib import Path

from .analyze import analyze
from .report import format_report
from .visualize import build_figure


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="mask 형상 임베딩 분석 (정렬→(r,θ)특징→UMAP→HDBSCAN)")
    p.add_argument("--root", type=Path, required=True,
                   help="mask 폴더 (root/<class>/*.png 또는 flat root/*.png)")
    p.add_argument("--pattern", default="*.png", help="mask 파일 glob (예: *_mask.png)")
    p.add_argument("--resolution", type=int, default=512, help="θ bin 수(각도 해상도)")
    p.add_argument("--n-harmonics", type=int, default=20, help="Fourier harmonic 수")
    p.add_argument("--batch-size", type=int, default=64, help="한 번에 태울 mask 수")
    p.add_argument("--n-components", type=int, default=2, help="UMAP 임베딩 차원")
    p.add_argument("--n-neighbors", type=int, default=15, help="UMAP n_neighbors")
    p.add_argument("--min-dist", type=float, default=0.1, help="UMAP min_dist")
    p.add_argument("--min-cluster-size", type=int, default=5, help="HDBSCAN min_cluster_size")
    p.add_argument("--out-dir", type=Path, default=None, help="리포트/figure 저장 (기본: root)")
    p.add_argument("--no-show", action="store_true", help="figure 창 안 띄움 (저장만)")
    p.add_argument("--no-plot", action="store_true", help="시각화 생략(리포트만)")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    print(f"[analyze] root={args.root}  pattern={args.pattern}")
    res = analyze(
        args.root, pattern=args.pattern, resolution=args.resolution,
        n_harmonics=args.n_harmonics, batch_size=args.batch_size,
        n_components=args.n_components, n_neighbors=args.n_neighbors,
        min_dist=args.min_dist, min_cluster_size=args.min_cluster_size)

    _txt = format_report(res)
    print("\n" + _txt + "\n")

    _out = args.out_dir or args.root
    _out.mkdir(parents=True, exist_ok=True)
    (_out / "shape_embedding_report.txt").write_text(_txt, encoding="utf-8")
    print(f"[save] report → {_out / 'shape_embedding_report.txt'}")

    if not args.no_plot:
        import matplotlib.pyplot as plt
        _fig = build_figure(res)
        _png = _out / "shape_embedding.png"
        _fig.savefig(_png, dpi=120)
        print(f"[save] figure → {_png}")
        if args.no_show:
            plt.close(_fig)
        else:
            plt.show()


if __name__ == "__main__":
    main()
