"""메시 지오메트리 간 유사도 계측 독립 함수 모듈."""
from __future__ import annotations

import numpy as np
import trimesh
from scipy.spatial import KDTree


# ==========================================
# 정확 일치 비교
# ==========================================


def Is_exact_match(
    geo_a: trimesh.Trimesh, geo_b: trimesh.Trimesh, tol: float = 1e-5
) -> bool:
    """두 trimesh 지오메트리의 정점/면 배열이 허용 오차 내에서 완벽히 일치하는지 검사함.

    Args:
        geo_a: 비교 기준 지오메트리.
        geo_b: 비교 대상 지오메트리.
        tol: 부동소수점 비교 허용 오차.

    Returns:
        bool: 완전 일치 여부.
    """
    # 빠른 기각: 정점/면 개수
    if len(geo_a.vertices) != len(geo_b.vertices):
        return False

    if len(geo_a.faces) != len(geo_b.faces):
        return False

    # 빠른 기각: 바운딩 박스
    if not np.allclose(geo_a.extents, geo_b.extents, atol=tol):
        return False

    # 전수 비교

    _vertices = np.allclose(geo_a.vertices, geo_b.vertices, atol=tol)
    _face = np.array_equal(geo_a.faces, geo_b.faces)

    return _vertices and _face


# ==========================================
# 표면 샘플링 기반 유사도 (원본 좌표계)
# ==========================================


def Calculate_match_rate(
    geo_a: trimesh.Trimesh, geo_b: trimesh.Trimesh,
    num_samples: int = 5000, threshold: float = 0.01
) -> float:
    """표면 샘플링을 통한 두 지오메트리의 기하학적 형상 일치율을 계산함.

    동일 좌표계/스케일을 전제하는 기본 비교 함수.
    토폴로지가 다르거나 정점 순서가 뒤섞여 있어도
    3D 공간상의 외형 유사도를 평가할 수 있음.

    Args:
        geo_a: 비교 기준 지오메트리.
        geo_b: 비교 대상 지오메트리.
        num_samples: 표면에서 추출할 무작위 점의 개수.
        threshold: 동일 표면 판정 최대 거리 오차(미터 단위).

    Returns:
        float: 0.0(완전 다름) ~ 1.0(완벽 일치).
    """
    _pts_a = trimesh.sample.sample_surface(geo_a, num_samples)[0]
    _pts_b = trimesh.sample.sample_surface(geo_b, num_samples)[0]

    _dist_a_to_b = geo_b.nearest.on_surface(_pts_a)[1]
    _dist_b_to_a = geo_a.nearest.on_surface(_pts_b)[1]

    _match_a = np.sum(_dist_a_to_b < threshold) / num_samples
    _match_b = np.sum(_dist_b_to_a < threshold) / num_samples

    return float((_match_a + _match_b) / 2.0)


# ==========================================
# 비정형 스캔 대응 유사도
# ==========================================


def Calculate_scan_match_rate(
    geo_a: trimesh.Trimesh, geo_b: trimesh.Trimesh,
    num_samples: int = 5000, threshold: float = 0.02,
    icp_iterations: int = 30, icp_tol: float = 1e-6
) -> float:
    """비정형 스캔 데이터 간 유사도를 계산함.

    스케일 정규화 → ICP 정합 → 표면 샘플링 비교 파이프라인을 수행하며,
    부분 스캔에 대응하여 양방향 일치율 중 최대값을 반환함.

    Args:
        geo_a: 비교 기준 지오메트리.
        geo_b: 비교 대상 지오메트리.
        num_samples: 표면에서 추출할 무작위 점의 개수.
        threshold: 정규화 공간에서의 동일 표면 판정 최대 거리.
        icp_iterations: ICP 최대 반복 횟수.
        icp_tol: ICP 수렴 판정 오차 (평균 거리 변화량).

    Returns:
        float: 0.0(완전 다름) ~ 1.0(완벽 일치).
    """
    # 1. 스케일 정규화
    _pts_a = _Normalize_to_unit(
        trimesh.sample.sample_surface(geo_a, num_samples)[0]
    )
    _pts_b = _Normalize_to_unit(
        trimesh.sample.sample_surface(geo_b, num_samples)[0]
    )

    # 2. ICP 정합 (B를 A 좌표계로 정렬)
    _pts_b_aligned = _ICP(
        _pts_b, _pts_a,
        max_iterations=icp_iterations, tol=icp_tol
    )

    # 3. 양방향 표면 거리 측정
    _tree_a = KDTree(_pts_a)
    _tree_b = KDTree(_pts_b_aligned)

    _dist_a_to_b, _ = _tree_b.query(_pts_a)
    _dist_b_to_a, _ = _tree_a.query(_pts_b_aligned)

    _match_a = np.sum(_dist_a_to_b < threshold) / num_samples
    _match_b = np.sum(_dist_b_to_a < threshold) / num_samples

    # 4. 부분 스캔 대응: max 집계
    return float(max(_match_a, _match_b))


# ==========================================
# 내부 헬퍼
# ==========================================


def _Normalize_to_unit(points: np.ndarray) -> np.ndarray:
    """점군을 중심 원점 + 바운딩 박스 대각선 = 1.0 으로 정규화함.

    Args:
        points: (N, 3) 점 좌표 배열.

    Returns:
        np.ndarray: 정규화된 (N, 3) 배열.
    """
    _center = (points.max(axis=0) + points.min(axis=0)) * 0.5
    _centered = points - _center

    _diag = np.linalg.norm(points.max(axis=0) - points.min(axis=0))
    if _diag < 1e-12:
        return _centered

    return _centered / _diag


def _ICP(
    source: np.ndarray, target: np.ndarray,
    max_iterations: int = 30, tol: float = 1e-6
) -> np.ndarray:
    """SVD + KDTree 기반 ICP(Iterative Closest Point) 정합.

    source를 target 좌표계에 맞추는 강체 변환(회전 + 이동)을 반복 추정함.

    Args:
        source: (N, 3) 정렬할 점군.
        target: (M, 3) 기준 점군.
        max_iterations: 최대 반복 횟수.
        tol: 수렴 판정 평균 거리 변화량.

    Returns:
        np.ndarray: 정렬된 (N, 3) source 점군.
    """
    _src = source.copy()
    _tree = KDTree(target)
    _prev_error = float("inf")

    for _ in range(max_iterations):
        # 최근접 점 탐색
        _dists, _indices = _tree.query(_src)
        _matched = target[_indices]

        # 현재 평균 오차
        _mean_error = float(np.mean(_dists))
        if abs(_prev_error - _mean_error) < tol:
            break
        _prev_error = _mean_error

        # 중심점 계산
        _centroid_src = _src.mean(axis=0)
        _centroid_tgt = _matched.mean(axis=0)

        # 중심 이동 후 SVD로 최적 회전 추정
        _H = (_src - _centroid_src).T @ (_matched - _centroid_tgt)
        _U, _, _Vt = np.linalg.svd(_H)
        _R = _Vt.T @ _U.T

        # 반사(reflection) 보정
        if np.linalg.det(_R) < 0:
            _Vt[-1, :] *= -1
            _R = _Vt.T @ _U.T

        # 이동 벡터
        _t = _centroid_tgt - _R @ _centroid_src

        # 변환 적용
        _src = (_R @ _src.T).T + _t

    return _src
