"""콘솔 / 파일 출력 함수."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .feature_extract import PCA_RELIABLE_RATIO
from .analysis import _MATCH_ORDER, _build_class_id_map

CW = 50  # class/group 이름 컬럼 너비 (모든 보고서 공통)


# ── PCA reliability ───────────────────────────────────────────────────────────────

def report_pca_reliability(
    y: np.ndarray,
    ratios: np.ndarray,
    threshold: float = PCA_RELIABLE_RATIO,
) -> None:
    """class별 PCA eigenvalue ratio 분포 출력."""
    print(f"\n{'─'*62}")
    print(f"{'CLASS':<30} {'N':>5} {'mean':>7} {'std':>7} {'<thr':>6} {'%':>6}")
    print(f"{'─'*62}")
    for cls in sorted(set(y.tolist())):
        mask  = y == cls
        r     = ratios[mask]
        n_bad = int((r < threshold).sum())
        print(
            f"{cls:<30} {len(r):>5} {r.mean():>7.2f} {r.std():>7.2f}"
            f" {n_bad:>6} {n_bad/len(r)*100:>5.1f}%"
        )
    print(f"{'─'*62}")
    total_bad = int((ratios < threshold).sum())
    print(
        f"{'ALL':<30} {len(ratios):>5} {ratios.mean():>7.2f} {ratios.std():>7.2f}"
        f" {total_bad:>6} {total_bad/len(ratios)*100:>5.1f}%"
    )
    print(f"{'─'*62}\n")


# ── Cluster report ────────────────────────────────────────────────────────────────

def report_clusters(result: dict, save_path: Path | None = None) -> None:
    """클러스터 단위 보고서.

    클러스터별 dominant class / purity / size / tag breakdown.
    사물 ID 는 report_class_summary 에서만 사용한다.
    """
    opts               = result['opts']
    cluster_info       = result['cluster_info']
    confusion_clusters = result['confusion_clusters']

    SEP = "━" * 76

    mode_desc = f"mode={opts.mode}"
    if opts.mode == 'features':
        mode_desc += f"  dims={len(opts.feature_cols or [])}"
    else:
        mode_desc += f"  umap={opts.umap_n_components}d"
    mode_desc += (f"  min_cluster_size={opts.min_cluster_size}"
                  f"  purity_thr={opts.purity_threshold:.0%}")

    lines = [
        SEP,
        f"Cluster Report  [{mode_desc}]",
        f"  clusters={len(cluster_info)}  confusion={len(confusion_clusters)}",
        SEP,
        f"  {'CID':>4}  {'DOMINANT':<{CW}} {'PURITY':>7}  {'SIZE':>5}  TAG BREAKDOWN",
        f"  {'─'*4}  {'─'*CW} {'─'*7}  {'─'*5}  {'─'*30}",
    ]

    for cid, info in sorted(cluster_info.items()):
        dominant = info['dominant_tag']
        pur      = info['purity']
        pur_str  = f"{pur:7.3f}" if not np.isnan(pur) else "    nan"
        flag     = ' ~' if np.isnan(pur) or pur < opts.purity_threshold else '  '
        breakdown = "  ".join(
            f"{t}:{c}"
            for t, c in sorted(info['tag_breakdown'].items(), key=lambda x: -x[1])
        )
        lines.append(
            f"  {cid:>4}  {dominant:<{CW}}{pur_str}{flag}  {info['size']:>5}  {breakdown}"
        )

    lines.append(SEP)
    text = "\n".join(lines)
    print(text)

    if save_path is not None:
        save_path.write_text(text, encoding="utf-8")
        print(f"[REPORT] clusters → {save_path}")


# ── Stem report ───────────────────────────────────────────────────────────────────

def report_stems(result: dict, save_path: Path | None = None) -> None:
    """stem 단위 보고서.

    검토 필요(X/~/?) / 정상(O) 두 섹션, 각 섹션 내 stem 오름차순.
    __excluded__ 항목은 제외한다.
    사물 ID 는 report_class_summary 에서만 사용한다.
    """
    opts    = result['opts']
    records = [r for r in result['records'] if r['cls'] != '__excluded__']

    review = sorted([r for r in records if r['match'] != 'O'], key=lambda r: r['stem'])
    ok     = sorted([r for r in records if r['match'] == 'O'],  key=lambda r: r['stem'])

    n_o = len(ok)
    n_x = sum(1 for r in review if r['match'] == 'X')
    n_t = sum(1 for r in review if r['match'] == '~')
    n_q = sum(1 for r in review if r['match'] == '?')

    SEP  = "━" * 76
    HDR  = f"  {'CLASS':<{CW}} {'GROUP':<{CW}} {'PURITY':>7}  M  {'C':>4}  STEM"
    RULE = f"  {'─'*CW} {'─'*CW} {'─'*7}  ─  {'─'*4}  {'─'*20}"

    def _row(r: dict) -> str:
        pur = f"{r['purity']:7.3f}" if not math.isnan(r['purity']) else "    -  "
        cid = f"c{r['cluster_id']:>4}" if r['cluster_id'] != -1 else "   ?"
        return (f"  {r['cls']:<{CW}} {r['group']:<{CW}}"
                f" {pur}  {r['match']}  {cid}  {r['stem']}")

    lines = [
        SEP,
        f"Stem Report  [mode={opts.mode}  purity_thr={opts.purity_threshold:.0%}]",
        f"  total={len(records)}  O={n_o}  검토필요={len(review)} (X={n_x} ~={n_t} ?={n_q})",
        SEP,
        f"── 검토 필요 ({len(review)}건) ──",
    ]
    if review:
        lines += [HDR, RULE]
        lines += [_row(r) for r in review]
    else:
        lines.append("  (없음)")

    lines += [SEP, f"── 정상 ({n_o}건) ──"]
    if ok:
        lines += [HDR, RULE]
        lines += [_row(r) for r in ok]
    else:
        lines.append("  (없음)")

    lines.append(SEP)
    text = "\n".join(lines)
    print(text)

    if save_path is not None:
        save_path.write_text(text, encoding="utf-8")
        print(f"[REPORT] stems    → {save_path}")


# ── Class summary report ──────────────────────────────────────────────────────────

def report_class_summary(result: dict, save_path: Path | None = None) -> None:
    """클래스 단위 요약 보고서.

    사물 ID 테이블 / 클래스별 O·? 비율·순수클러스터 수 / 혼동 쌍 / 전체 ? 비율.
    사물 ID(#N) 표기는 이 보고서에서만 사용한다.
    """
    opts            = result['opts']
    records         = result['records']
    class_summary   = result.get('class_summary', {})
    confusion_pairs = result.get('confusion_pairs', [])

    n_total = len(records)
    n_q     = sum(1 for r in records if r['match'] == '?')

    SEP  = "━" * 76
    DISP = 3  # 순수클러스터 수 ≥ 이 값이면 분산 경고

    cls_id_map = _build_class_id_map([r['cls'] for r in records])

    # ── 사물 ID 테이블
    lines = [SEP, f"Class Summary  [mode={opts.mode}  purity_thr={opts.purity_threshold:.0%}]", SEP]
    lines += [f"[사물 ID]  n={len(cls_id_map)}",
              f"  {'ID':>4}  CLASS",
              f"  {'─'*4}  {'─'*CW}"]
    for cls, oid in sorted(cls_id_map.items(), key=lambda x: x[1]):
        lines.append(f"  {oid:>4}  {cls:<{CW}}")

    # ── 전체 noise 비율
    lines += [SEP,
              f"[전체 noise(?)]  {n_q}/{n_total}  ({n_q/n_total:.1%})"]

    # ── 클래스별 요약
    lines += [SEP, f"[클래스별 요약]  (⚠ = 순수클러스터 {DISP}개 이상 분산)"]
    lines.append(f"  {'ID':>4}  {'CLASS':<{CW}} {'O%':>6}  {'?%':>5}  순수클러스터")
    lines.append(f"  {'─'*4}  {'─'*CW} {'─'*6}  {'─'*5}  {'─'*10}")
    for cls in sorted(class_summary):
        s    = class_summary[cls]
        oid  = cls_id_map.get(cls, '?')
        warn = '  ⚠' if s['n_pure_clusters'] >= DISP else ''
        lines.append(
            f"  {oid:>4}  {cls:<{CW}}"
            f" {s['o_ratio']:>6.1%}  {s['noise_ratio']:>5.1%}"
            f"  {s['n_pure_clusters']}{warn}"
        )

    # ── 혼동 쌍
    lines += [SEP, f"[혼동 쌍]  n={len(confusion_pairs)}"]
    if confusion_pairs:
        lines.append(f"  {'CLASS_A':<{CW}}  {'CLASS_B':<{CW}}  {'샘플':>6}  클러스터")
        lines.append(f"  {'─'*CW}  {'─'*CW}  {'─'*6}  {'─'*30}")
        for p in confusion_pairs:
            cluster_ids = ' '.join(f"C{c}" for c in p['cluster_ids'])
            lines.append(
                f"  {p['cls_a']:<{CW}}  {p['cls_b']:<{CW}}"
                f"  {p['n_samples']:>6}  [{cluster_ids}]"
            )
    else:
        lines.append("  (없음)")

    lines.append(SEP)
    text = "\n".join(lines)
    print(text)

    if save_path is not None:
        save_path.write_text(text, encoding="utf-8")
        print(f"[REPORT] summary  → {save_path}")
