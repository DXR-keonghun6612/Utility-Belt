"""단일 이미지 mask 변환 유틸리티."""

from __future__ import annotations

import cv2
import numpy as np

from .._base import GRAY_IMAGE


def Vec_slices(start: np.ndarray, end: np.ndarray) -> tuple[slice, ...]:
    """위치 벡터 쌍을 numpy 인덱싱용 slice 튜플로 변환한다.

    Args:
        start: 각 축의 시작 좌표 벡터.
        end: 각 축의 끝 좌표 벡터.

    Returns:
        (slice(start[0], end[0]), slice(start[1], end[1]), ...) 튜플.
    """
    return tuple(map(slice, start, end))


def Crop_square(mask: GRAY_IMAGE, ratio: float = 1.0) -> np.ndarray:
    """bounding box 기준 정사각형 crop.

    Args:
        mask: 이진 마스크 (H, W).
        ratio: 객체 크기 대비 crop 비율.

    Returns:
        정사각형 crop 결과. 유효 픽셀 없으면 빈 배열.
    """
    _coords = np.argwhere(mask > 0)
    if _coords.size == 0:
        return np.array([])

    _max = _coords.max(axis=0)
    _min = _coords.min(axis=0)
    _center = (_max + _min) // 2
    _size = int(max(_max - _min + 1) * ratio)

    _half = _size // 2
    _start = _center - _half

    _hw   = np.array(mask.shape)
    _s    = np.maximum(0, _start)
    _e    = np.minimum(_hw, _start + _size)
    _os   = _s - _start

    _out  = np.zeros((_size, _size), dtype=mask.dtype)
    if np.all(_e > _s):
        _out[Vec_slices(_os, _os + _e - _s)] = mask[Vec_slices(_s, _e)]
    return _out


def Mask_padding(mask: GRAY_IMAGE, target: int) -> GRAY_IMAGE:
    """mask가 target보다 작으면 target 크기 캔버스 중앙에 배치한다.

    Args:
        mask: 이진 마스크 (H, W) 또는 (H, W, C).
        target: 출력 한 변 크기 (px).

    Returns:
        (target, target) 크기 배열. mask가 target 이상이면 그대로 반환.
    """
    _hw = np.array(mask.shape)
    if np.all(_hw >= target):
        return mask
    _offset = (target - _hw) // 2
    _canvas = np.zeros((target, target), dtype=mask.dtype)
    _canvas[Vec_slices(_offset, _offset + _hw)] = mask
    return _canvas


def Make_morph_kernel(size: int = 3) -> np.ndarray:
    """사각형 morphology 커널을 생성한다.

    Args:
        size: 커널 한 변 크기 (px).

    Returns:
        (size, size) uint8 커널.
    """
    return cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))
