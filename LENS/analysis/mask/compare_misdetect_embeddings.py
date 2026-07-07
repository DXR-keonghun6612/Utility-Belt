#!/usr/bin/env python3
"""오검출 실루엣의 geometry embedding 을 class 별 평균(prototype)과 비교한다.

입력: test 산출물 ``test_embeds_<iter>.pt`` (embeddings·pred/gt class id·file_paths 번들).

절차:
  1. 각 실루엣을 **학습과 동일하게 정렬**(``dataloader.mask_sdf_edge.prepare_mask``:
     fill_largest + PCA 주축 수평화 + 180° 모호성 정리) 후 426-dim geometry embedding 재추출.
  2. class 별 평균 prototype 을 만들되 **정답(pred==gt) 샘플만** 사용한다 — **오검출은 평균에서 제외**.
  3. 각 오검출 샘플을 그 평균들과 비교: GT/예측 class 평균까지의 거리, GT class 순위,
     가장 가까운 class, 편차가 큰 feature 등.

거리는 (이질적 스케일 보정을 위해) **정답 샘플 통계로 z-score 표준화**한 공간의 유클리드 거리.

출력(--out):
  - ``misdetect_compare.csv`` : 오검출 샘플별 비교표. meta 컬럼 뒤에 **feature 이름을 각 헤더로 둔**
    열이 이어지고, 셀 값은 GT 평균 대비 **z-편차**(양수=평균보다 큼).
  - ``misdetect_compare_grouped.csv`` : 위 편차를 **의미 그룹별 RMS** 로 요약(샘플마다 어느 축이
    벗어났나). geometry 전용.
  - ``class_means.csv``       : class 별 평균 embedding(raw) — **채널(feature) 전부**. 맨 앞 두 행은
    **전체 객체 분포**(``__ALL_MEAN__``/``__ALL_STD__`` = 모든 valid 샘플의 평균/표준편차).
  - ``class_means_grouped.csv``: 위 평균을 **의미 그룹(FEAT_GROUPS)별로 묶은** 요약. 단 이 그룹 구조는
    **geometry embedding 전용** — ``--use-model-embeds`` (output embedding, e0..eN)일 땐 생성하지 않음.
  - ``class_geo_means.npz``   : 위 값들(raw·z 평균·표준화 통계·정답 표본수·feature 이름) 재사용용.

사용 (프로젝트 root 에서 모듈로 실행 — dataloader 등 로컬 모듈 import 위해):
  python -m tools.compare_misdetect_embeddings --embeds <run_dir>/test_embeds_<iter>.pt \
      [--id-map id_map.yaml] [--out <dir>] [--use-model-embeds]
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import torch

from dataloader.mask_sdf_edge import prepare_mask
from dataloader.utils.sample_extractor import (
    extract_sample_features, ExtractOpts, FEAT_GROUPS, FEAT_DIM,
)

_EPS = 1e-8


# ── 로드 ──────────────────────────────────────────────────────────────────────

def _load_embeds(path: Path) -> dict:
    _d = torch.load(path, map_location="cpu", weights_only=False)
    for _k in ("pred_class_ids", "gt_class_ids", "file_paths"):
        if _k not in _d:
            raise KeyError(f"'{_k}' 키가 없음: {path} (test_embeds_*.pt 형식이어야 함)")
    return _d


def _load_id_map(path: Path | None) -> dict[int, str]:
    if path is None or not path.exists():
        return {}
    import yaml
    _raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {int(_e["class_id"]): _name for _name, _e in _raw.items()}


# ── geometry embedding 재추출 (정렬 포함) ─────────────────────────────────────

def _extract_geometry(file_paths: list[str]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """각 mask 경로 → 정렬 후 426-dim geometry embedding. (X, valid_mask, names) 반환."""
    _opts = ExtractOpts()
    _vecs: list[np.ndarray | None] = []
    _names: list[str] = []
    _n = len(file_paths)
    for _i, _p in enumerate(file_paths):
        try:
            _aligned = prepare_mask(_p)                       # ★ 학습과 동일한 정렬 포함
            _res = extract_sample_features(_aligned, _opts, preprocess=False)
            _vecs.append(_res.vector.astype(np.float64))
            if not _names:
                _names = _res.names
        except Exception as _e:                              # 빈/퇴화/경로없음 mask 스킵
            print(f"  [skip] {_p}: {_e}")
            _vecs.append(None)
        if (_i + 1) % 500 == 0:
            print(f"  ...extracted {_i + 1}/{_n}")

    _dim = len(_names) if _names else 0
    _valid = np.array([_v is not None for _v in _vecs])
    _X = np.full((_n, _dim), np.nan, dtype=np.float64)
    for _i, _v in enumerate(_vecs):
        if _v is not None:
            _X[_i] = _v
    return _X, _valid, _names


# ── 분석 ──────────────────────────────────────────────────────────────────────

def _class_means(Z: np.ndarray, gt: np.ndarray, use: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """정답 표본(use=valid&correct)만으로 class 별 평균(z-space). (class_ids, means, counts)."""
    _cids = np.array(sorted(np.unique(gt[use]).tolist()))
    _means = np.stack([Z[use & (gt == _c)].mean(axis=0) for _c in _cids])
    _counts = np.array([int((use & (gt == _c)).sum()) for _c in _cids])
    return _cids, _means, _counts


def main() -> None:
    _p = argparse.ArgumentParser(description="오검출 실루엣 geometry embedding ↔ class 평균 비교")
    _p.add_argument("--embeds", type=Path, required=True, help="test_embeds_<iter>.pt 경로")
    _p.add_argument("--id-map", type=Path, default=None, help="class_id→이름 표기용 id_map.yaml")
    _p.add_argument("--out", type=Path, default=None, help="출력 디렉토리 (기본: --embeds 폴더)")
    _p.add_argument("--use-model-embeds", action="store_true",
                    help="geometry 재추출 대신 .pt 의 model embeddings 사용")
    _a = _p.parse_args()

    _data = _load_embeds(_a.embeds)
    _gt = np.asarray(_data["gt_class_ids"]).astype(int)
    _pred = np.asarray(_data["pred_class_ids"]).astype(int)
    _paths = [str(_fp) for _fp in _data["file_paths"]]
    _names_map = _load_id_map(_a.id_map)

    def _name(_c) -> str:
        return _names_map.get(int(_c), str(int(_c)))

    # 1) embedding 확보
    if _a.use_model_embeds:
        _X = np.asarray(_data["embeddings"]).astype(np.float64)
        _valid = np.ones(len(_paths), dtype=bool)
        _feat_names = [f"e{_i}" for _i in range(_X.shape[1])]
        print(f"[embeds] model embeddings 사용: {_X.shape}")
    else:
        print(f"[extract] geometry 재추출(정렬 포함) — {len(_paths)}개")
        _X, _valid, _feat_names = _extract_geometry(_paths)
        print(f"[extract] 완료: valid {_valid.sum()}/{len(_paths)}, dim {len(_feat_names)}")

    _correct = _gt == _pred
    _use = _valid & _correct                                  # ★ 평균은 정답 샘플만 (오검출 제외)
    if _use.sum() == 0:
        raise SystemExit("정답(valid&correct) 샘플이 없어 평균을 만들 수 없음.")

    # 2) 표준화(정답 표본 통계) → class 평균(z)
    _mu = _X[_use].mean(axis=0)
    _sd = _X[_use].std(axis=0)
    _sd = np.where(_sd < _EPS, 1.0, _sd)
    _Z = (_X - _mu) / _sd

    _cids, _means_z, _counts = _class_means(_Z, _gt, _use)
    _cid_to_row = {int(_c): _r for _r, _c in enumerate(_cids)}
    _means_raw = _means_z * _sd + _mu

    # 3) 오검출 샘플 비교
    _mis = np.where(_valid & ~_correct)[0]
    _meta_cols = ["file_path", "gt_id", "gt_name", "pred_id", "pred_name", "gt_mean_n",
                  "dist_gt", "dist_pred", "closer_to", "gt_rank",
                  "nearest_id", "nearest_name", "nearest_dist"]
    _dim = _means_z.shape[1]
    _is_geo = (not _a.use_model_embeds) and (_X.shape[1] == FEAT_DIM)   # 의미 그룹 유효 여부
    _meta_rows: list[list] = []       # meta 값
    _devs: list[np.ndarray] = []      # 샘플별 feature z-편차 (GT 평균 대비)
    _closer_pred = 0
    _ranks: list[int] = []
    for _i in _mis:
        _zi = _Z[_i]
        _g, _pd = int(_gt[_i]), int(_pred[_i])
        _dists = np.linalg.norm(_means_z - _zi, axis=1)       # 모든 class 평균까지 거리
        _order = np.argsort(_dists)
        _near_row = int(_order[0])

        _gr = _cid_to_row.get(_g)
        _pr = _cid_to_row.get(_pd)
        _dist_gt = float(_dists[_gr]) if _gr is not None else float("nan")
        _dist_pred = float(_dists[_pr]) if _pr is not None else float("nan")
        _gt_rank = int(np.where(_order == _gr)[0][0]) + 1 if _gr is not None else -1
        _gt_n = int(_counts[_gr]) if _gr is not None else 0

        _closer = "gt"
        if _gr is None or (_pr is not None and _dist_pred < _dist_gt):
            _closer = "pred"
        if _closer == "pred":
            _closer_pred += 1
        if _gr is not None:
            _ranks.append(_gt_rank)

        # GT 평균 대비 feature 별 z-편차 (양수=평균보다 큼)
        _dev = (_zi - _means_z[_gr]) if _gr is not None else np.full(_dim, np.nan)

        _meta_rows.append([
            _paths[_i], _g, _name(_g), _pd, _name(_pd), _gt_n,
            round(_dist_gt, 4), round(_dist_pred, 4), _closer, _gt_rank,
            int(_cids[_near_row]), _name(_cids[_near_row]), round(float(_dists[_near_row]), 4),
        ])
        _devs.append(_dev)

    # 4) 저장
    _out = _a.out or _a.embeds.parent
    _out.mkdir(parents=True, exist_ok=True)

    # 4a) 채널 전부 — meta + feature 별 z-편차(각 feature 이름을 헤더로)
    _csv = _out / "misdetect_compare.csv"
    with _csv.open("w", newline="", encoding="utf-8") as _f:
        _w = csv.writer(_f)
        _w.writerow(_meta_cols + _feat_names)
        for _m, _dv in zip(_meta_rows, _devs):
            _w.writerow(_m + [round(float(_v), 4) for _v in _dv])

    # 4b) 의미 그룹별 요약 — 각 그룹 z-편차의 **RMS**(부호 상쇄 방지). geometry 전용.
    _mis_grouped_csv = None
    if _is_geo:
        _gnames = list(FEAT_GROUPS.keys())
        _mis_grouped_csv = _out / "misdetect_compare_grouped.csv"
        with _mis_grouped_csv.open("w", newline="", encoding="utf-8") as _f:
            _w = csv.writer(_f)
            _w.writerow(_meta_cols + _gnames)
            for _m, _dv in zip(_meta_rows, _devs):
                _gvals = [round(float(np.sqrt(np.mean(_dv[_s:_e] ** 2))), 4)
                          for _s, _e in FEAT_GROUPS.values()]
                _w.writerow(_m + _gvals)

    _npz = _out / "class_geo_means.npz"
    np.savez(
        _npz,
        class_ids=_cids, means_z=_means_z, means_raw=_means_raw,
        n_correct=_counts, feature_names=np.array(_feat_names),
        std_mu=_mu, std_sd=_sd,
    )

    # class 별 평균(raw embedding, 정답 표본만)을 사람이 읽는 CSV 로도 저장.
    # 맨 앞 두 행은 참고용 **전체 객체 분포**(모든 valid 샘플의 raw mean/std).
    _means_csv = _out / "class_means.csv"
    _all_mu = _X[_valid].mean(axis=0)
    _all_sd = _X[_valid].std(axis=0)
    _n_all = int(_valid.sum())
    with _means_csv.open("w", newline="", encoding="utf-8") as _f:
        _w = csv.writer(_f)
        _w.writerow(["class_id", "class_name", "n", *_feat_names])
        _w.writerow(["__ALL_MEAN__", "(all objects)", _n_all,
                     *(round(float(_v), 6) for _v in _all_mu)])
        _w.writerow(["__ALL_STD__", "(all objects)", _n_all,
                     *(round(float(_v), 6) for _v in _all_sd)])
        for _r, _c in enumerate(_cids):
            _w.writerow([int(_c), _name(_c), int(_counts[_r]),
                         *(round(float(_v), 6) for _v in _means_raw[_r])])

    # 의미 그룹(FEAT_GROUPS)별로 묶은 평균 — **geometry embedding 에만** 의미 있음.
    # model output embedding(--use-model-embeds, e0..eN)은 의미 그룹이 없어 생략한다.
    _grouped_csv = None
    if _is_geo:
        _gnames = list(FEAT_GROUPS.keys())

        def _grp(_vec):  # 그룹 slice 별 평균 (그룹 내부는 동질 feature 라 raw 평균이 의미 있음)
            return [round(float(_vec[_s:_e].mean()), 6) for _s, _e in FEAT_GROUPS.values()]

        _grouped_csv = _out / "class_means_grouped.csv"
        with _grouped_csv.open("w", newline="", encoding="utf-8") as _f:
            _w = csv.writer(_f)
            _w.writerow(["class_id", "class_name", "n", *_gnames])
            _w.writerow(["__ALL_MEAN__", "(all objects)", _n_all, *_grp(_all_mu)])
            _w.writerow(["__ALL_STD__", "(all objects)", _n_all, *_grp(_all_sd)])
            for _r, _c in enumerate(_cids):
                _w.writerow([int(_c), _name(_c), int(_counts[_r]), *_grp(_means_raw[_r])])

    # 5) 요약
    _all_cls = set(np.unique(_gt).tolist())
    _no_mean = sorted(_all_cls - set(int(_c) for _c in _cids))
    print("\n" + "═" * 60)
    print(" 오검출 geometry 비교")
    print("═" * 60)
    print(f" 샘플 {len(_paths)}개 (valid {int(_valid.sum())}) · 정답 {int(_use.sum())} · 오검출 {len(_mis)}")
    print(f" class 평균 {len(_cids)}개 (정답표본 min/median/max "
          f"{int(_counts.min())}/{int(np.median(_counts))}/{int(_counts.max())})")
    if _no_mean:
        print(f" ⚠ 정답 표본 0 → 평균 없음 class {len(_no_mean)}개: {_no_mean[:15]}"
              + (" ..." if len(_no_mean) > 15 else ""))
    if _mis.size:
        print(f" 오검출 중 예측 class 평균에 더 가까움: {_closer_pred}/{len(_mis)} "
              f"({100 * _closer_pred / len(_mis):.1f}%)")
        if _ranks:
            print(f" GT class 평균 순위(거리 기준) median {int(np.median(_ranks))} · "
                  f"1위 비율 {100 * sum(_r == 1 for _r in _ranks) / len(_ranks):.1f}%")
    print("─" * 60)
    print(f" [save] {_csv}")
    if _mis_grouped_csv is not None:
        print(f" [save] {_mis_grouped_csv}")
    print(f" [save] {_means_csv}")
    if _grouped_csv is not None:
        print(f" [save] {_grouped_csv}")
    else:
        print(" [skip] class_means_grouped.csv (의미 그룹 없음 — model output embedding)")
    print(f" [save] {_npz}")
    print("═" * 60)


if __name__ == "__main__":
    main()
