"""도메인 무관 geometry primitive — roi/bbox ↔ region 좌표 변환 + 정사각 crop/pad.

``Roi_to_*``·``Mask_to_box`` 는 bbox/mask 를 슬라이스·bool 선택·박스로 바꾸는 순수 좌표 연산,
``Crop_square``/``Mask_padding`` 은 전경 기준 정사각 배치다 — mask 처리 의미가 아니라 배열 좌표
연산이라 여기(generic)에 산다. chroma·model 등이 써도 도메인 누수가 아니다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ...typing import BBOX, IMAGE, GRAY_IMAGE

#: 보간 이름 → cv2 플래그. UI 는 이 키(str)를 고르고 func 층이 여기서 플래그로 정규화한다
#: — 계산 계층이 cv2 상수를 밖으로 흘리지 않기 위한 자리(``func/chroma`` 의 색공간 테이블과 같은 관례).
INTERP_CODES = {
    "nearest": cv2.INTER_NEAREST,   # 라벨맵 값 보존
    "linear":  cv2.INTER_LINEAR,
    "area":    cv2.INTER_AREA,      # 다운샘플에 적합
    "cubic":   cv2.INTER_CUBIC,
    "lanczos": cv2.INTER_LANCZOS4,
}
DEFAULT_DOWN_INTERP  = "area"       # 다운샘플(축소) 기본
DEFAULT_LABEL_INTERP = "nearest"    # 라벨맵 복원 기본 (값 보존)


def Get_interp(interp: str) -> int:
    """보간 이름(str)을 cv2 플래그로 정규화한다 — 미지값은 실패(조용한 기본값 없음)."""
    try:
        return INTERP_CODES[interp]
    except KeyError:
        raise ValueError(
            f"알 수 없는 보간 '{interp}'. 가능: {sorted(INTERP_CODES)}") from None


def Resize_by(image: IMAGE, ratio: float, interp: str = DEFAULT_DOWN_INTERP) -> IMAGE:
    """이미지를 ``ratio`` 배로 리사이즈한다 (``ratio=1.0`` 이면 무변경).

    큰 이미지에서 CV 를 돌리기 전 canonical 해상도로 줄이는 자리 — 비율로 균일 축소해 고정
    커널(canny·clahe·morphology)이 해상도에 덜 휘둘리고, 속도도 는다. 되돌리려면 원본 ``(H, W)`` 를
    따로 들고 :func:`Resize_to` 로 (여긴 비율을 기억하지 않는다).

    Args:
        image: gray ``(H,W)`` 또는 다채널 ``(H,W,C)``.
        ratio: 스케일 배수 ``(0, 1]`` — ``0.5`` 면 반, ``1.0`` 이면 원본 그대로.
        interp: 보간 이름 (:data:`INTERP_CODES` 키). 축소 기본은 ``area``.

    Returns:
        ``ratio`` 배로 리사이즈된 이미지(``ratio=1.0`` 이면 원본 그대로).
    """
    if ratio == 1.0:
        return image
    _h, _w = image.shape[:2]
    return cv2.resize(image, (max(1, int(_w * ratio)), max(1, int(_h * ratio))),
                      interpolation=Get_interp(interp))


def Resize_to(image: IMAGE, size_hw: tuple[int, int], interp: str = DEFAULT_LABEL_INTERP) -> IMAGE:
    """이미지를 정확한 ``(H, W)`` 로 리사이즈한다 — 기본은 라벨 보존 ``nearest``.

    :func:`Resize_by` 의 짝 — 작은 해상도에서 만든 결과를 원본 크기로 되돌린다. mask·라벨맵은
    ``nearest`` 로 되돌려 값(obj_id+1)을 섞지 않는다. 연속값(이미지)이면 ``linear`` 등을 준다.

    Args:
        image: 되돌릴 이미지.
        size_hw: 목표 크기 ``(H, W)``.
        interp: 보간 이름 (:data:`INTERP_CODES` 키). 라벨맵 복원 기본은 ``nearest``.

    Returns:
        ``(H, W)`` 로 리사이즈된 이미지.
    """
    _h, _w = size_hw
    return cv2.resize(image, (int(_w), int(_h)), interpolation=Get_interp(interp))


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


def Box_center(box: list[float] | BBOX) -> tuple[float, float]:
    """bbox(XYXY)의 중심점 ``(cx, cy)``."""
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def Mask_centroid(mask: GRAY_IMAGE) -> tuple[float, float] | None:
    """전경 픽셀의 무게중심 ``(cx, cy)``. 전경이 없으면 None."""
    if not np.any(mask):
        return None
    _ys, _xs = np.nonzero(mask)
    return float(_xs.mean()), float(_ys.mean())


def Center_offset(shape: tuple[int, int], point: tuple[float, float]) -> float:
    """이미지 중심에서 ``point`` 까지의 거리를 **대각선 길이로 정규화**해 ``[0, 1]`` 로 만든다.

    대각선으로 나누므로 이미지 종횡비·해상도가 달라도 비교 가능한 척도가 된다.

    Args:
        shape: 이미지 ``(H, W)``.
        point: ``(cx, cy)`` 픽셀 좌표.

    Returns:
        정규화 거리. 중심이면 ``0``, 모서리면 ``0.5`` 근처.
    """
    _h, _w = shape[:2]
    _cx, _cy = point
    return float(np.hypot(_cx - _w / 2.0, _cy - _h / 2.0) / np.hypot(_w, _h))


def Mask_within_roi(mask: GRAY_IMAGE, roi: BBOX | GRAY_IMAGE) -> GRAY_IMAGE | None:
    """``roi`` 의 **외접 박스** 밖 전경을 지운다. roi 가 비면 None.

    roi 가 마스크로 주어져도 그 모양이 아니라 `외접 박스`로 자른다(``Roi_to_box`` 규약) — roi 는 관심
    영역의 대략적 한정이지 정밀한 경계가 아니기 때문이다.
    """
    _box = Roi_to_box(roi)
    if _box is None:
        return None
    _y0, _y1, _x0, _x1 = _box
    _out = np.zeros_like(mask)
    _out[_y0:_y1, _x0:_x1] = mask[_y0:_y1, _x0:_x1]
    return _out


def Box_within_roi(box: BBOX | None, roi: BBOX | GRAY_IMAGE | None) -> bool:
    """bbox(XYXY)가 ``roi`` 의 **외접 박스** 안에 완전히 드는지 (한 변이라도 벗어나면 False).

    roi 가 마스크로 주어져도 그 모양이 아니라 외접 박스로 본다(``Roi_to_box`` 규약 — roi 는 관심 영역의
    대략적 한정이지 정밀 경계가 아니다). ``roi`` 가 None(미지정)이거나 비었으면, 또는 ``box`` 가 None
    (판정 근거 없음)이면 True — 이 함수는 "roi 밖에 걸친 것"만 걸러내지 그 밖의 이유로 떨구지 않는다.
    """
    if roi is None or box is None:
        return True
    _rb = Roi_to_box(roi)                       # (y0, y1, x0, x1) — 마스크/BBOX 모두 외접 박스로
    if _rb is None:                             # 빈 roi = 사실상 미지정
        return True
    _y0, _y1, _x0, _x1 = _rb
    return box[0] >= _x0 and box[1] >= _y0 and box[2] <= _x1 and box[3] <= _y1


def Crop_to_mask(image: np.ndarray, mask: GRAY_IMAGE) -> np.ndarray | None:
    """``mask`` 전경의 외접 박스로 ``image`` 를 자른다. 전경이 없으면 None."""
    _coords = np.argwhere(mask > 0)
    if _coords.size == 0:
        return None
    _min = _coords.min(axis=0)
    _max = _coords.max(axis=0) + 1
    return image[_min[0]:_max[0], _min[1]:_max[1]]


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
