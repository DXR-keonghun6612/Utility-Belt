"""임시 스크립트 2 — crop_out mask 들의 형상 임베딩 + 유사 객체 시각 군집화.

``analysis.mask.shape`` 파이프라인을 그대로 쓴다 (네 설계 그대로):
  1. ``align_mask`` — centroid 원점 → **PCA 주축 수평** 회전 → centroid 기준 **좌우·상하 픽셀
     비율**로 flip 방향 확정 (정준 자세).
  2. ``polar`` — centroid 원점 (r, θ) radial profile.
  3. ``features`` — 프로파일 통계 + thickness + Fourier descriptor → 특징 벡터.
  4. ``embed`` — 표준화 → UMAP 2D 임베딩 → HDBSCAN 클러스터.

산출물(모두 ``crop_out_debug/`` 아래):
  - ``shape_embedding_report.txt`` — 클래스·클러스터 요약.
  - ``embedding_scatter.png``      — (좌)class·(우)cluster 점 산점도.
  - ``embedding_thumbnails.png``   — 임베딩 좌표에 **정렬된 mask 썸네일**을 배치(클러스터 색 tint)
                                     → 공간에서 유사 형상이 뭉치는 걸 눈으로 확인.
  - ``clusters/cluster_XX.png``    — 클러스터별 mask 몽타주(유사 객체끼리 모아 보기).
  - ``mislabeled_report.txt``      — **섞인(오분류) 탐지**: 클러스터 다수 클래스와 폴더가 어긋난
                                     mask 를 "원본클래스 → 대상클래스" 로, noise·혼합은 '유사 없음'
                                     으로 따로 정리.

실행: ``python temp_shape_embed.py [crop_out] [--out crop_out_debug] [--min-cluster-size 15] ...``
(LENS 루트에서 실행 — ``analysis`` 패키지 import 가능해야 함. deps: umap-learn·hdbscan·sklearn·matplotlib)
"""

from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from analysis.mask.align import align_mask
from analysis.mask.shape import analyze, format_report, build_figure, iter_masks, load_mask


def _aligned_thumb(path: Path, size: int) -> np.ndarray | None:
    """mask → 정준 자세 정렬 → bbox crop → 정사각 pad → ``size`` 리샘플 (0/255). 빈 것은 None."""
    _m = load_mask(path)
    try:
        _a = align_mask(_m).mask
    except ValueError:
        return None
    _ys, _xs = np.nonzero(_a)
    if _xs.size == 0:
        return None
    _crop = (_a[_ys.min():_ys.max() + 1, _xs.min():_xs.max() + 1]).astype(np.uint8) * np.uint8(255)
    _h, _w = _crop.shape
    _s  = max(_h, _w)
    _sq = np.zeros((_s, _s), np.uint8)
    _sq[(_s - _h) // 2:(_s - _h) // 2 + _h, (_s - _w) // 2:(_s - _w) // 2 + _w] = _crop
    return cv2.resize(_sq, (size, size), interpolation=cv2.INTER_AREA)


def _cluster_colors(clusters: np.ndarray) -> dict[int, tuple]:
    """클러스터 label → RGB(0~1). noise(-1)=회색."""
    import matplotlib.cm as cm
    _uni = sorted(_k for _k in set(clusters.tolist()) if _k != -1)
    _cmap = cm.get_cmap("tab20", max(len(_uni), 1))
    _col = {_k: _cmap(_i)[:3] for _i, _k in enumerate(_uni)}
    _col[-1] = (0.7, 0.7, 0.7)
    return _col


def _thumbnail_scatter(res, path_by_stem: dict, out: Path, *,
                       thumb: int, zoom: float, max_thumbs: int) -> None:
    """임베딩 좌표에 정렬 mask 썸네일을 배치한 그림 (클러스터 색 tint)."""
    import matplotlib.pyplot as plt
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox

    _emb = res.embedding[:, :2]
    _idx = list(range(len(res.stems)))
    if max_thumbs and len(_idx) > max_thumbs:                    # 너무 많으면 가독성 위해 표본
        _idx = sorted(np.random.default_rng(0).choice(len(_idx), max_thumbs, replace=False))
    _col = _cluster_colors(res.clusters)

    _fig, _ax = plt.subplots(figsize=(26, 26))
    _ax.scatter(_emb[:, 0], _emb[:, 1], s=5, c="0.9", zorder=1)  # 전체 점(맥락)
    for _i in _idx:
        _t = _aligned_thumb(path_by_stem[res.stems[_i]], thumb)
        if _t is None:
            continue
        _rgba = np.zeros((thumb, thumb, 4), np.float32)
        _rgba[..., :3] = _col[int(res.clusters[_i])]             # 전경을 클러스터 색으로
        _rgba[..., 3]  = (_t > 0).astype(np.float32)            # 배경 투명
        _ab = AnnotationBbox(OffsetImage(_rgba, zoom=zoom),
                             (_emb[_i, 0], _emb[_i, 1]), frameon=False, pad=0, zorder=2)
        _ax.add_artist(_ab)
    _ax.set_title(f"aligned mask thumbnails on UMAP embedding "
                  f"(N={len(res.stems)}, shown={len(_idx)})", fontsize=15)
    _ax.set_xticks([]); _ax.set_yticks([])
    _fig.tight_layout()
    _fig.savefig(out / "embedding_thumbnails.png", dpi=110)
    plt.close(_fig)


def _montage(masks: list[np.ndarray], cols: int, cell: int, pad: int = 2) -> np.ndarray:
    """썸네일 리스트 → 그리드 몽타주 (흰 형상 / 검은 배경)."""
    _rows = (len(masks) + cols - 1) // cols
    _canvas = np.zeros((_rows * (cell + pad) + pad, cols * (cell + pad) + pad), np.uint8)
    for _i, _m in enumerate(masks):
        _r, _c = divmod(_i, cols)
        _y = pad + _r * (cell + pad)
        _x = pad + _c * (cell + pad)
        _canvas[_y:_y + cell, _x:_x + cell] = _m
    return _canvas


def _cluster_montages(res, path_by_stem: dict, out: Path, *,
                      cell: int, cols: int, max_per: int) -> None:
    """클러스터별 정렬 mask 몽타주를 ``clusters/cluster_XX.png`` 로 저장."""
    _dir = out / "clusters"
    _dir.mkdir(parents=True, exist_ok=True)
    _clu = res.clusters
    for _k in sorted(set(_clu.tolist())):
        _stems = [res.stems[_i] for _i in range(len(res.stems)) if _clu[_i] == _k]
        _thumbs = []
        for _st in _stems[:max_per]:
            _t = _aligned_thumb(path_by_stem[_st], cell)
            if _t is not None:
                _thumbs.append(_t)
        if not _thumbs:
            continue
        _name = "noise" if _k == -1 else f"{_k:02d}"
        _path = _dir / f"cluster_{_name}_n{len(_stems)}.png"
        cv2.imwrite(str(_path), _montage(_thumbs, cols, cell))
        print(f"[save] {_path}  ({len(_thumbs)}/{len(_stems)} shown)")


def _bidirectional_section(pair: Counter) -> str:
    """이동 제안 쌍 Counter → **쌍방 오류**(A→B 와 B→A 둘 다 존재) 요약 텍스트.

    두 클래스가 서로 오분류를 주고받으면(형상이 사실상 구분 안 됨) 한 줄로 묶어 적는다.
    """
    _seen: set[frozenset] = set()
    _rows: list[tuple[str, str, int, int]] = []   # (A, B, A→B, B→A)
    for (_a, _b), _ab in pair.items():
        _ba = pair.get((_b, _a), 0)
        if _ba > 0 and frozenset((_a, _b)) not in _seen:
            _seen.add(frozenset((_a, _b)))
            _rows.append((_a, _b, _ab, _ba))
    _rows.sort(key=lambda _r: -(_r[2] + _r[3]))

    _lines = ["", "=" * 70,
              f"쌍방 오류 (상호 혼동 — 형상 구분 어려움): {len(_rows)} 쌍",
              "=" * 70]
    if _rows:
        for _a, _b, _ab, _ba in _rows:
            _lines.append(f"  {_a} <-> {_b}   ({_a}->{_b}: {_ab}건 / {_b}->{_a}: {_ba}건)")
    else:
        _lines.append("  (없음)")
    return "\n".join(_lines) + "\n"


def _mislabel_report(res, out: Path, *, purity: float, pattern_ext: str) -> tuple[int, int, Counter]:
    """클러스터 다수 클래스와 폴더 클래스가 어긋난 mask 를 찾아 txt 로 정리한다.

    각 HDBSCAN 클러스터의 **다수 클래스**(mode)를 그 클러스터의 정답으로 본다. 다수 비율이
    ``purity`` 이상인 클러스터에서 다른 클래스인 mask 는 **오분류 후보**로 보고 "원본 → 대상"
    으로 적는다. noise(클러스터 없음)·혼합(다수 비율 < purity) mask 는 '유사 없음'으로 따로 뺀다.

    Returns:
        ``(이동 제안 수, 유사 없음 수)``.
    """
    _labels, _clusters, _stems = res.labels, res.clusters, res.stems
    _ext = pattern_ext

    # 클러스터 → (다수 클래스, 다수 비율, 크기)
    _major: dict[int, tuple[str, float, int]] = {}
    for _k in set(_clusters.tolist()):
        if _k == -1:
            continue
        _idx = [_i for _i in range(len(_stems)) if _clusters[_i] == _k]
        _cnt = Counter(str(_labels[_i]) for _i in _idx)
        _cls, _c = _cnt.most_common(1)[0]
        _major[_k] = (_cls, _c / len(_idx), len(_idx))

    _moves: list[tuple[str, str, str, int, float, int]] = []   # (원본cls, stem, 대상cls, k, 비율, n)
    _orphans: list[tuple[str, str, str]] = []                  # (원본cls, stem, 사유)
    for _i in range(len(_stems)):
        _k, _cls, _st = int(_clusters[_i]), str(_labels[_i]), _stems[_i]
        if _k == -1:
            _orphans.append((_cls, _st, "noise (유사 클러스터 없음)"))
            continue
        _maj, _frac, _n = _major[_k]
        if _cls == _maj:
            continue                                           # 다수와 같음 = 제자리
        if _frac >= purity:
            _moves.append((_cls, _st, _maj, _k, _frac, _n))    # 오분류 후보
        else:
            _orphans.append((_cls, _st, f"혼합 cluster {_k:02d}: 최다 {_maj} {_frac:.0%}"))

    _moves.sort(key=lambda _m: (_m[0], _m[2], _m[1]))
    _orphans.sort(key=lambda _o: (_o[0], _o[1]))

    _lines: list[str] = []
    _lines.append("=" * 70)
    _lines.append(f"오분류 후보 리포트 (purity>={purity:.0%})  "
                  f"이동제안 {len(_moves)} / 유사없음 {len(_orphans)} / 전체 {len(_stems)}")
    _lines.append("=" * 70)

    _pair: Counter = Counter((_m[0], _m[2]) for _m in _moves)   # (원본→대상) 쌍별 건수
    _lines.append("\n[이동 제안]  원본클래스/stem  ->  대상클래스   (근거: cluster·다수비율·크기)")
    if _moves:
        _lines.append("  · 쌍별 소계:")
        for (_src, _dst), _c in sorted(_pair.items(), key=lambda _x: -_x[1]):
            _lines.append(f"      {_src} -> {_dst}: {_c}건")
        _lines.append("  · 상세:")
        for _src, _st, _dst, _k, _frac, _n in _moves:
            _lines.append(f"      {_src}/{_st}{_ext}  ->  {_dst}"
                          f"   (cluster {_k:02d}, 다수 {_frac:.0%}, n={_n})")
    else:
        _lines.append("      (없음)")

    _lines.append("\n[유사 없음]  클래스/stem   (사유)")
    if _orphans:
        for _cls, _st, _why in _orphans:
            _lines.append(f"      {_cls}/{_st}{_ext}   ({_why})")
    else:
        _lines.append("      (없음)")

    _txt = "\n".join(_lines) + "\n"
    (out / "mislabeled_report.txt").write_text(_txt, encoding="utf-8")
    print(f"[save] {out / 'mislabeled_report.txt'}  "
          f"(이동제안 {len(_moves)}, 유사없음 {len(_orphans)})")
    return len(_moves), len(_orphans), _pair


def main() -> None:
    _ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    _ap.add_argument("root", nargs="?", type=Path, default=Path("crop_out"),
                     help="mask 폴더 (root/<class>/*.png)")
    _ap.add_argument("--out", type=Path, default=Path("crop_out_debug"), help="출력 루트")
    _ap.add_argument("--pattern", default="*.png", help="mask glob")
    _ap.add_argument("--resolution", type=int, default=256, help="θ bin 수(각도 해상도)")
    _ap.add_argument("--n-harmonics", type=int, default=20, help="Fourier harmonic 수")
    _ap.add_argument("--normalize", action="store_true", help="형상 프로파일 scale-free 정규화")
    _ap.add_argument("--n-neighbors", type=int, default=15, help="UMAP n_neighbors")
    _ap.add_argument("--min-dist", type=float, default=0.1, help="UMAP min_dist")
    _ap.add_argument("--min-cluster-size", type=int, default=15, help="HDBSCAN min_cluster_size")
    _ap.add_argument("--thumb", type=int, default=44, help="썸네일 픽셀 크기")
    _ap.add_argument("--zoom", type=float, default=0.4, help="임베딩 썸네일 확대율")
    _ap.add_argument("--max-thumbs", type=int, default=1500,
                     help="썸네일 산점도에 그릴 최대 개수(0=전부)")
    _ap.add_argument("--montage-cols", type=int, default=12, help="클러스터 몽타주 열 수")
    _ap.add_argument("--montage-max", type=int, default=144, help="클러스터당 몽타주 최대 개수")
    _ap.add_argument("--purity", type=float, default=0.6,
                     help="클러스터 다수 비율이 이 값 이상일 때만 오분류 후보로 이동 제안 (기본 0.6)")
    _args = _ap.parse_args()

    _out = _args.out
    if _out.exists():
        shutil.rmtree(_out)
    _out.mkdir(parents=True)

    print(f"[analyze] root={_args.root}  (align→(r,θ)→UMAP→HDBSCAN)")
    _res = analyze(
        _args.root, pattern=_args.pattern, resolution=_args.resolution,
        n_harmonics=_args.n_harmonics, normalize=_args.normalize,
        n_neighbors=_args.n_neighbors, min_dist=_args.min_dist,
        min_cluster_size=_args.min_cluster_size)

    # stem → 원본 경로 (썸네일 로드용; stem 은 프레임 타임스탬프라 유일)
    _path_by_stem = {_st: _p for _st, _cls, _p in iter_masks(_args.root, _args.pattern)}

    # 1) 텍스트 리포트 (쌍방 오류는 mislabel 분석 뒤 아래에서 함께 기록)
    _txt = format_report(_res)
    print("\n" + _txt + "\n")

    # 2) 점 산점도 (class / cluster)
    import matplotlib.pyplot as plt
    _fig = build_figure(_res)
    _fig.savefig(_out / "embedding_scatter.png", dpi=120)
    plt.close(_fig)
    print(f"[save] {_out / 'embedding_scatter.png'}")

    # 3) 썸네일 산점도 (유사 형상이 공간에서 뭉치는 걸 시각화)
    _thumbnail_scatter(_res, _path_by_stem, _out,
                       thumb=_args.thumb, zoom=_args.zoom, max_thumbs=_args.max_thumbs)
    print(f"[save] {_out / 'embedding_thumbnails.png'}")

    # 4) 클러스터별 몽타주 (유사 객체끼리 모아 보기)
    _cluster_montages(_res, _path_by_stem, _out,
                      cell=_args.thumb, cols=_args.montage_cols, max_per=_args.montage_max)

    # 5) 오분류 후보 리포트 (섞인 것 탐지 — 원본→대상 / 유사없음)
    _pattern_ext = Path(_args.pattern).suffix or ".png"
    _n_move, _n_orphan, _pair = _mislabel_report(
        _res, _out, purity=_args.purity, pattern_ext=_pattern_ext)

    # 형상 리포트 + 쌍방 오류(상호 혼동 쌍)를 shape_embedding_report.txt 에 함께 기록
    (_out / "shape_embedding_report.txt").write_text(
        _txt + _bidirectional_section(_pair), encoding="utf-8")
    print(f"[save] {_out / 'shape_embedding_report.txt'}  (+ 쌍방 오류)")

    _n_clu = len({_k for _k in _res.clusters.tolist() if _k != -1})
    _n_noise = int((_res.clusters == -1).sum())
    print(f"\n완료 — N={len(_res.stems)}, 클러스터 {_n_clu}개, noise {_n_noise}, "
          f"이동제안 {_n_move}, 유사없음 {_n_orphan} → {_out}")


if __name__ == "__main__":
    main()
