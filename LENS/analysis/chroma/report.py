"""report — ChromaDiag → 텍스트 (권고 포함)."""

from __future__ import annotations

from core.pipeline.process.chroma._space import ChromaSpace

from ._result import ChromaDiag


def recommend(diag: ChromaDiag) -> list[str]:
    """공간분산 비율 + 색공간 특이성 기반 모델·색공간 권고 문장들."""
    _sp = diag.space
    _frac = diag.spatial_fraction
    _g_mean1 = diag.g_mean[1]
    _lines = []
    if _frac < 0.15:
        _lines.append(f"· 모델: 공간분산 비율 {_frac:.2f} (<0.15) → 배경 거의 공간 균일. "
                      f"**전역(global_chroma_stats)** 으로 충분, 메모리·정합 이득.")
    elif _frac < 0.50:
        _lines.append(f"· 모델: 공간분산 비율 {_frac:.2f} (0.15~0.5) → 완만한 영역 의존. "
                      f"**coarse-grid 공간가변**(다운샘플 배경맵)이 sweet spot. 전역은 σ팽창으로 손해.")
    else:
        _lines.append(f"· 모델: 공간분산 비율 {_frac:.2f} (>0.5) → 강한 영역 의존. "
                      f"**픽셀별 또는 coarse-grid 필수**. 전역 단일 모델은 분별력 붕괴.")

    if _sp.name == "hsv":
        if _g_mean1 < 40:
            _lines.append(f"· 색공간: 전역 평균 S={_g_mean1:.0f} (저채도) → 배경이 거의 무채색. "
                          f"HSV의 Hue 항이 불안정(노이즈) → **--space lab (a*,b*) 로 교체 테스트 권장**.")
        else:
            _lines.append(f"· 색공간: 전역 평균 S={_g_mean1:.0f} (유채색) → Hue 신뢰 가능, HSV 유지 무방.")
    else:
        _lines.append("· 색공간: lab(a*,b*) — 무채색에서도 안정·비순환. within σ 가 hsv 대비 낮으면 "
                      "Lab 채택 근거.")
    return _lines


def format_report(diag: ChromaDiag) -> str:
    """``ChromaDiag`` 를 사람이 읽는 리포트 문자열로."""
    _sp: ChromaSpace = diag.space
    _l0, _l1 = _sp.labels
    _gm0, _gm1 = diag.g_mean
    _gs0, _gs1 = diag.g_std
    _p0, _p1 = diag.part
    _cover = float(diag.valid_mask.mean()) * 100.0
    _lines = [
        "═" * 64,
        f" 배경 크로마 공간 의존성 진단  (space={_sp.name}: {_l0}·{_l1})",
        "═" * 64,
        f" 신뢰 픽셀(n≥{diag.min_count}): {_p0.get('valid_px', 0):,d}  "
        f"(ROI/유효 영역 {_cover:.1f}%)",
        "",
        "  [채널]   전역평균  전역σ   within(시간)σ  between(공간)σ  공간분산비율",
        "  " + "-" * 60,
        f"  {_l0:<6} {_gm0:7.1f}  {_gs0:6.2f}  {_p0.get('within_std', 0):11.2f}  "
        f"{_p0.get('between_std', 0):12.2f}  {_p0.get('spatial_fraction', 0):11.2f}",
        f"  {_l1:<6} {_gm1:7.1f}  {_gs1:6.2f}  {_p1.get('within_std', 0):11.2f}  "
        f"{_p1.get('between_std', 0):12.2f}  {_p1.get('spatial_fraction', 0):11.2f}",
        "",
        " 해석: 공간분산비율 = between² / (within² + between²)",
        "        within  = 한 픽셀이 시간에 따라 흔들리는 폭 (전역모델이 못 줄이는 잡음 바닥)",
        "        between = 픽셀별 배경평균이 영역에 따라 퍼진 폭 (전역모델이 σ로 떠안는 세금)",
        "─" * 64,
        " 전역 대표색 — sample-weighted vs 2중 robust(픽셀당 1표)",
        "─" * 64,
        *_global_color_block(diag),
        "─" * 64,
        " 권고",
        "─" * 64,
        *recommend(diag),
        "═" * 64,
    ]
    return "\n".join(_lines)


def _global_color_block(diag: ChromaDiag) -> list[str]:
    """전역색 두 추정(가중 합산 vs 픽셀-vote robust) 비교표 + 오염 의심 플래그."""
    _l0, _l1 = diag.space.labels
    (_gm0, _gm1), (_gr0, _gr1) = diag.g_mean, diag.g_robust
    _d0, _d1 = diag.chan_delta()
    _lines = [
        f"  [채널]   global(가중)   robust(vote)     Δ",
        "  " + "-" * 48,
        f"  {_l0:<6} {_gm0:11.1f}  {_gr0:12.1f}  {_d0:8.1f}",
        f"  {_l1:<6} {_gm1:11.1f}  {_gr1:12.1f}  {_d1:8.1f}",
        "",
    ]
    if diag.contaminated:
        _lines.append("  ⚠ 두 전역색이 벌어짐(Δ>5%bin) → 고정 위치 객체가 sample-weighted 전역")
        _lines.append("    통계를 오염시키는 중. **robust(vote) 쪽이 진짜 배경색** — 이걸 채택.")
    else:
        _lines.append("  · 두 전역색 일치 → 고정 객체 오염 징후 없음. 어느 쪽 전역색이든 무방.")
    return _lines
