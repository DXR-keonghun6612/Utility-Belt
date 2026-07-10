"""ChromaDiag — 공간 의존성 진단 결과 (CLI/GUI 공용 산출물)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.process.func.chroma._space import ChromaSpace


@dataclass
class ChromaDiag:
    """픽셀별 맵 + 전역 통계 + 분산 분해. 채널 0/1 은 ``space.labels`` 에 대응.

    표현(report/figure)과 분리된 순수 데이터 컨테이너 — 어떤 표현 stage 든 이 객체만 소비한다.
    """

    space:     ChromaSpace
    window:    int
    min_count: int
    mean:      tuple[np.ndarray, np.ndarray]   # 픽셀별 평균 맵 (H,W) × 2채널
    std:       tuple[np.ndarray, np.ndarray]   # 픽셀별 표준편차 맵 (H,W) × 2채널
    n:         np.ndarray                       # coverage — 픽셀별 누산 표본 수 (H,W)
    g_mean:    tuple[float, float]              # 전역 평균 (공간합산, sample-weighted)
    g_std:     tuple[float, float]              # 전역 표준편차
    g_robust:  tuple[float, float]              # 2중 robust 전역 대표색 (픽셀당 1표 → robust)
    part:      tuple[dict, dict]                # 채널별 분산 분해

    def chan_delta(self) -> tuple[float, float]:
        """채널별 |g_mean − g_robust| (순환 채널은 wrap 최단거리). 오염 의심 지표."""
        _out = []
        for _i, (_gm, _gr, _cir, _b) in enumerate(zip(
                self.g_mean, self.g_robust, self.space.circular, self.space.bins)):
            _d = abs(_gm - _gr)
            if _cir:
                _d = min(_d, _b - _d)
            _out.append(float(_d))
        return _out[0], _out[1]

    @property
    def contaminated(self) -> bool:
        """sample-weighted 전역색이 vote-robust 대표색과 한 채널이라도 5%bin 넘게 벌어지면 True."""
        _d0, _d1 = self.chan_delta()
        _b0, _b1 = self.space.bins
        return _d0 > 0.05 * _b0 or _d1 > 0.05 * _b1

    @property
    def valid_mask(self) -> np.ndarray:
        """신뢰 픽셀(n ≥ min_count) bool 마스크."""
        return self.n >= max(self.min_count, 1)

    @property
    def spatial_fraction(self) -> float:
        """두 채널 중 큰 공간분산 비율 — 모델 결정의 단일 지표."""
        return max(self.part[0].get("spatial_fraction", 0.0),
                   self.part[1].get("spatial_fraction", 0.0))
