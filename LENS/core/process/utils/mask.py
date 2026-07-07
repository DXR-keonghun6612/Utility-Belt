"""단일 이미지 mask 변환 유틸리티."""

from __future__ import annotations

import cv2
import numpy as np

from .._base import GRAY_IMAGE, BBOX


def Mask_to_box(mask: GRAY_IMAGE) -> np.ndarray | None:
    """이진 mask의 외접 박스를 ``[x0, y0, x1, y1]`` (XYXY, float32)로 만든다.

    Args:
        mask: 0/255 또는 bool 이진 mask ``(H, W)``.

    Returns:
        ``[x0, y0, x1, y1]`` float32 배열. 전경이 없으면 None.
    """
    _ys, _xs = np.where(mask > 0)
    if _xs.size == 0:
        return None
    return np.array([_xs.min(), _ys.min(), _xs.max() + 1, _ys.max() + 1], dtype=np.float32)


def Roi_to_box(roi: BBOX | GRAY_IMAGE) -> tuple[int, int, int, int] | None:
    """roi(마스크 또는 BBOX)를 ``(y0, y1, x0, x1)`` 슬라이스 범위로 변환한다.

    빈 마스크면 ``None``. BBOX는 ``(y, x, h, w)`` 형식으로 받는다.
    """
    if isinstance(roi, np.ndarray):
        _ys, _xs = np.where(roi > 0)
        if _xs.size == 0:
            return None
        return int(_ys.min()), int(_ys.max()) + 1, int(_xs.min()), int(_xs.max()) + 1
    _y0, _x0, _dh, _dw = roi
    return _y0, _y0 + _dh, _x0, _x0 + _dw


def Roi_to_mask(roi: BBOX | GRAY_IMAGE | None, shape: tuple[int, int]) -> np.ndarray | None:
    """roi를 ``(H, W)`` bool 선택 마스크로 변환한다. ``None`` 이면 전체(=None 반환).

    마스크(ndarray)는 ``>0`` 영역, BBOX는 ``(y, x, h, w)`` 사각 영역.
    """
    if roi is None:
        return None
    if isinstance(roi, np.ndarray):
        return roi > 0
    _y, _x, _h, _w = roi
    _sel = np.zeros(shape, dtype=bool)
    _sel[_y:_y + _h, _x:_x + _w] = True
    return _sel


def Vec_slices(start: np.ndarray, end: np.ndarray) -> tuple[slice, ...]:
    return tuple(map(slice, start, end))


def Crop_square(mask: GRAY_IMAGE, ratio: float = 1.0) -> np.ndarray:
    """bounding box 기준 정사각형 crop."""
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
    """mask가 target보다 작으면 target 크기 캔버스 중앙에 배치한다."""
    _hw = np.array(mask.shape)
    if np.all(_hw >= target):
        return mask
    _offset = (target - _hw) // 2
    _canvas = np.zeros((target, target), dtype=mask.dtype)
    _canvas[Vec_slices(_offset, _offset + _hw)] = mask
    return _canvas


def Make_morph_kernel(size: int = 3) -> np.ndarray:
    """사각형 morphology 커널을 생성한다."""
    return cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))


def Filter_by_area(mask: GRAY_IMAGE, min_area: int = 0, max_area: int | None = None) -> GRAY_IMAGE:
    """연결 성분(8-이웃) 중 면적이 ``[min_area, max_area]`` 밖인 것을 제거한다.

    Args:
        mask: 0/255 또는 bool 이진 mask ``(H, W)``.
        min_area: 이 값 미만 면적의 성분 제거 (``<=0`` 이면 하한 없음).
        max_area: 이 값 초과 면적의 성분 제거 (``None`` 이면 상한 없음).

    Returns:
        남은 성분만 255인 같은 shape의 uint8 mask. 하한·상한 둘 다 없으면 입력 그대로.
    """
    if min_area <= 0 and max_area is None:
        return mask
    _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(
        (mask > 0).astype(np.uint8), connectivity=8)
    _areas = _stats[:, cv2.CC_STAT_AREA]
    _ok = _areas >= max(min_area, 1)
    if max_area is not None:
        _ok &= _areas <= max_area
    _ok[0] = False                                   # 0번 = 배경
    return np.where(_ok[_lbl], np.uint8(255), np.uint8(0))


def _close_border(e: GRAY_IMAGE, gap: int, margin: int = 2) -> GRAY_IMAGE:
    """경계 근처 edge 끝점 사이의 작은 틈(<=gap)만 경계 변을 따라 이어 잘린 윤곽을 닫는다.

    각 변의 경계 띠(margin px)에서 edge 존재를 1D 로 투영해, gap 이하 간격만 1D CLOSE 로
    메운다. 큰 배경 간격은 남겨 전체 프레임 채움을 막는다.
    """
    _out = e.copy()
    _h, _w = e.shape[:2]
    _k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(gap, 1), 1))

    def _bridge(_pres: np.ndarray) -> np.ndarray:          # 1D presence → 새로 이어질 위치
        _closed = cv2.morphologyEx(
            _pres.reshape(1, -1).astype(np.uint8), cv2.MORPH_CLOSE, _k).ravel()
        return (_closed > 0) & (~_pres)

    _bt = _bridge((_out[0:margin, :] > 0).any(axis=0));        _out[0:margin, _bt] = 255
    _bb = _bridge((_out[_h - margin:_h, :] > 0).any(axis=0));  _out[_h - margin:_h, _bb] = 255
    _bl = _bridge((_out[:, 0:margin] > 0).any(axis=1));        _out[_bl, 0:margin] = 255
    _br = _bridge((_out[:, _w - margin:_w] > 0).any(axis=1));  _out[_br, _w - margin:_w] = 255
    return _out


def Fill_contours(
    edge: GRAY_IMAGE, min_area: int = 0, max_area: int | None = None,
    border_gap: int = 0,
) -> GRAY_IMAGE:
    """edge 의 외곽 윤곽(``RETR_EXTERNAL``) 내부를 채워 영역 mask 를 만든다.

    각 윤곽의 면적(``cv2.contourArea``)이 ``[min_area, max_area]`` 밖이면 버리고, 통과한
    윤곽만 solid 로 채운다. ``border_gap>0`` 이면 이미지 경계에 잘린 윤곽을 그 폭 이하로 이어
    닫는다(``_close_border``).

    Args:
        edge: 0/255 또는 bool edge ``(H, W)``.
        min_area: 이 값 미만 윤곽 제거 (``0`` 이면 하한 없음).
        max_area: 이 값 초과 윤곽 제거 (``None`` 이면 상한 없음).
        border_gap: 경계 틈 잇기 폭 (px, ``0`` 이면 끄기).

    Returns:
        채워진 영역만 255인 ``(H, W)`` uint8 mask.
    """
    _e = (edge > 0).astype(np.uint8)
    if border_gap > 0:                       # 경계에 잘린 객체 윤곽 닫기
        _e = _close_border(_e, border_gap)
    _cnts = cv2.findContours(_e, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
    _out: GRAY_IMAGE = np.zeros(edge.shape[:2], np.uint8)
    for _c in _cnts:
        _a = cv2.contourArea(_c)
        if min_area and _a < min_area:
            continue
        if max_area is not None and _a > max_area:
            continue
        cv2.drawContours(_out, [_c], -1, 255, thickness=cv2.FILLED)
    return _out


def Threshold_hysteresis(
    d: np.ndarray, k: float, k_weak: float | None,
    min_area: int = 0, max_area: int | None = None,
) -> np.ndarray:
    """스코어 맵 ``d`` 를 임계 ``k`` 로 이진화한다 (옵션: hysteresis + 씨앗 면적 필터).

    strong(``d > k``) 씨앗에서 출발해 weak(``d > k_weak``, ``k_weak < k``) 영역으로 번지되,
    strong 씨앗이 닿지 않는 weak 덩어리(=잡티)는 버린다. ``k_weak`` 가 없거나 strong 보다
    느슨하지 않으면 단순 임계.

    순서는 **큰 역치(strong) → 크기 적용(``Filter_by_area``) → 작은 역치(weak) 확장**이다 —
    strong 씨앗을 면적으로 먼저 거른 뒤 weak로 키우므로, 크기 기준은 확장 전 씨앗에 걸린다.

    색공간과 무관한 일반 연산이라 거리/스코어 맵이면 무엇이든(크로마 정규화 편차 등) 쓴다.
    """
    _strong = Filter_by_area((d > k).astype(np.uint8), min_area, max_area)
    if k_weak is None or k_weak >= k:
        return np.where(_strong > 0, np.uint8(255), np.uint8(0))

    _weak = (d > k_weak).astype(np.uint8)
    _, _lbl = cv2.connectedComponents(_weak, connectivity=8)
    _keep = np.unique(_lbl[_strong > 0])
    _keep = _keep[_keep != 0]
    if _keep.size == 0:
        return np.zeros_like(_strong)
    return np.isin(_lbl, _keep).astype(np.uint8) * np.uint8(255)
