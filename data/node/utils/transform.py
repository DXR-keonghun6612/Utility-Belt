"""노드 변환 행렬 구성 및 분해 유틸리티."""
from __future__ import annotations

import numpy as np


def Build_transform(
    tx: float = 0.0, ty: float = 0.0, tz: float = 0.0,
    rx: float = 0.0, ry: float = 0.0, rz: float = 0.0
) -> np.ndarray:
    """Euler 회전(XYZ, degrees) + 이동으로 4x4 변환 행렬을 구성함.

    Args:
        tx, ty, tz: 이동량 (씬 좌표계).
        rx, ry, rz: 회전량 (degrees, XYZ Euler).

    Returns:
        np.ndarray: 4x4 변환 행렬 (float32).
    """
    _rx, _ry, _rz = np.radians(rx), np.radians(ry), np.radians(rz)

    _cx, _sx = np.cos(_rx), np.sin(_rx)
    _cy, _sy = np.cos(_ry), np.sin(_ry)
    _cz, _sz = np.cos(_rz), np.sin(_rz)

    # Rz @ Ry @ Rx (extrinsic XYZ 순서)
    _m = np.eye(4, dtype=np.float32)
    _m[0, 0] = _cy * _cz
    _m[0, 1] = _sx * _sy * _cz - _cx * _sz
    _m[0, 2] = _cx * _sy * _cz + _sx * _sz
    _m[1, 0] = _cy * _sz
    _m[1, 1] = _sx * _sy * _sz + _cx * _cz
    _m[1, 2] = _cx * _sy * _sz - _sx * _cz
    _m[2, 0] = -_sy
    _m[2, 1] = _sx * _cy
    _m[2, 2] = _cx * _cy

    _m[0, 3] = tx
    _m[1, 3] = ty
    _m[2, 3] = tz

    return _m


def Decompose_transform(matrix: np.ndarray) -> tuple[float, ...]:
    """4x4 변환 행렬에서 이동 + Euler 회전(XYZ, degrees)을 역분해함.

    Args:
        matrix: 4x4 변환 행렬.

    Returns:
        tuple: (tx, ty, tz, rx, ry, rz).
    """
    _tx, _ty, _tz = float(matrix[0, 3]), float(matrix[1, 3]), float(matrix[2, 3])

    _sy = -float(matrix[2, 0])
    _cy = np.sqrt(float(matrix[0, 0])**2 + float(matrix[1, 0])**2)

    if _cy > 1e-6:
        _rx = np.degrees(np.arctan2(float(matrix[2, 1]), float(matrix[2, 2])))
        _ry = np.degrees(np.arctan2(_sy, _cy))
        _rz = np.degrees(np.arctan2(float(matrix[1, 0]), float(matrix[0, 0])))
    else:
        # 짐벌 락 근사
        _rx = np.degrees(np.arctan2(-float(matrix[1, 2]), float(matrix[1, 1])))
        _ry = np.degrees(np.arctan2(_sy, _cy))
        _rz = 0.0

    return (_tx, _ty, _tz, _rx, _ry, _rz)
