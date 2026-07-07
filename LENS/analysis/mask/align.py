"""mask 정준 자세(canonical pose) 정렬 — shape 분석의 전제 단계.

순서:
  1. centroid 를 원점으로
  2. **PCA** 주축을 수평(x)으로 회전 (방향 정렬)
  3. 남은 180° 방향 모호성은 centroid 기준 **좌우 질량비**로 **180° 회전**해 확정한다 (질량 무거운
     쪽을 오른쪽으로). **반사(flip)가 아니라 회전만** 쓴다 — 반사는 거울상을 같은 자세로 뭉개
     좌우/카이랄 정보를 지우므로 쓰지 않는다.

``mask.shape`` 는 이 결과(정렬된 mask)를 입력으로 받는다는 전제로 구성한다. 회전으로는 안 지워지는
**상하 비대칭**(``ud_imbalance``)이 좌우 구분(카이랄) 신호다 — 같은 부품 인스턴스끼리는 부호가
같아 정렬되고, 거울상은 부호가 반대라 정렬 후에도 다른 프로파일·descriptor 를 가진다.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .area import centroid


def _fill_holes(bw: np.ndarray) -> np.ndarray:
    """내부 구멍을 채운다 (외곽에서 floodfill 한 배경의 여집합 = 구멍). cv2-only."""
    _f = (bw.astype(np.uint8)) * 255
    _h, _w = _f.shape
    _ff = _f.copy()
    _m = np.zeros((_h + 2, _w + 2), np.uint8)
    cv2.floodFill(_ff, _m, (0, 0), 255)          # 코너(배경)에서 외부를 채움
    _holes = cv2.bitwise_not(_ff)                # 외부에 안 닿은 영역 = 내부 구멍
    return (_f | _holes) > 0


@dataclass
class AlignedMask:
    """정렬 결과 — 정준 자세 mask + 적용한 회전·비대칭 정보 (회전만, 반사 없음)."""

    mask:         np.ndarray   # 정렬된 이진 mask (회전만 적용, 같은 캔버스)
    angle:        float        # 주축 수평화에 적용한 총 회전각(deg, 180° 방향보정 포함)
    lr_imbalance: float        # 회전 후 (R-L)/(R+L) — 방향 보정으로 ≥0
    ud_imbalance: float        # 회전 후 (D-U)/(D+U) — 좌우/카이랄 신호 (정렬로 안 지움)


def _largest_component(bw: np.ndarray) -> np.ndarray:
    """8-이웃 최대 연결요소만 남긴다 (없으면 그대로)."""
    _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(bw.astype(np.uint8), 8)
    if _n <= 1:
        return bw
    _idx = 1 + int(np.argmax(_stats[1:, cv2.CC_STAT_AREA]))
    return _lbl == _idx


def _pca_major_angle(xs: np.ndarray, ys: np.ndarray, cx: float, cy: float) -> float:
    """centroid 기준 픽셀 분포의 PCA 주축 각도(deg, image 좌표 atan2(dy,dx))."""
    _dx = xs - cx
    _dy = ys - cy
    _cov = np.cov(np.vstack([_dx, _dy]).astype(np.float64))
    _evals, _evecs = np.linalg.eigh(_cov)          # 오름차순
    _major = _evecs[:, int(np.argmax(_evals))]     # (vx, vy)
    return float(np.degrees(np.arctan2(_major[1], _major[0])))


def align_mask(mask: np.ndarray, fill_holes: bool = True) -> AlignedMask:
    """mask → 정준 자세 ``AlignedMask`` (주축 수평 + 무거운 질량을 오른쪽으로, **회전만**).

    PCA 주축을 수평으로 돌리고 남은 180° 방향 모호성은 좌우 질량으로 180° 회전해 정한다(반사 아님).
    상하 비대칭은 정렬로 지우지 않고 남겨 거울상이 서로 다른 프로파일을 갖게 한다.
    """
    _bw = mask > 0
    if fill_holes:
        _bw = _fill_holes(_bw)
    _bw = _largest_component(_bw)
    if not _bw.any():
        raise ValueError("빈 mask")

    _H, _W = _bw.shape
    _ys, _xs = np.nonzero(_bw)
    _cx, _cy = centroid(_bw)
    _ccx, _ccy = (_W - 1) / 2.0, (_H - 1) / 2.0

    def _rotate(angle: float) -> np.ndarray:
        """centroid 중심으로 ``angle`` 회전 후 centroid 를 캔버스 중심으로 옮긴 이진 mask."""
        _M = cv2.getRotationMatrix2D((_cx, _cy), angle, 1.0)
        _M[0, 2] += _ccx - _cx
        _M[1, 2] += _ccy - _cy
        return cv2.warpAffine(_bw.astype(np.uint8), _M, (_W, _H), flags=cv2.INTER_NEAREST) > 0

    def _imbalance(rot: np.ndarray) -> tuple[float, float]:
        """(R-L)/(R+L), (D-U)/(D+U) — 캔버스 중심 기준 좌우·상하 픽셀 비대칭."""
        _ry, _rx = np.nonzero(rot)
        _right = int((_rx >= _ccx).sum()); _left = int((_rx < _ccx).sum())
        _down  = int((_ry >= _ccy).sum()); _up   = int((_ry < _ccy).sum())
        return ((_right - _left) / max(_right + _left, 1),
                (_down - _up)   / max(_down + _up, 1))

    # 2) PCA 주축 수평화. 3) 좌우 질량이 오른쪽으로 오도록 180° 회전으로 방향 확정 (반사 아님).
    _angle = _pca_major_angle(_xs, _ys, _cx, _cy)
    _rot = _rotate(_angle)
    _lr_imb, _ud_imb = _imbalance(_rot)
    if _lr_imb < 0:                                # 왼쪽이 무거우면 180° 더 회전 (flip 아님)
        _angle = (_angle + 180.0) % 360.0
        _rot = _rotate(_angle)
        _lr_imb, _ud_imb = _imbalance(_rot)

    return AlignedMask(
        mask=np.ascontiguousarray(_rot),
        angle=_angle, lr_imbalance=_lr_imb, ud_imbalance=_ud_imb,
    )
