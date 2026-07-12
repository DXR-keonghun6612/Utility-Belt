"""layer 합성 — 체크된 raster 들을 한 장으로.

**"base 이미지"라는 특별한 개념이 없다.** BGR 로 오는 layer 는 배경이 되고, 2D 로 오는 layer(mask·라벨맵)는
색을 입혀 겹친다. 무엇이 배경이고 무엇이 오버레이인지는 **모양이 말한다** — 트리에서 체크한 순서대로 쌓인다.
"""
from __future__ import annotations

import cv2
import numpy as np

_ALPHA = 0.45


def color_for(idx: int) -> tuple[int, int, int]:
    """인덱스 → BGR 색. 황금각으로 hue 를 돌려 인접 인덱스끼리 잘 구분되게 한다."""
    _hue = int(idx * 180 * 0.618033988749895) % 180        # OpenCV hue: 0~179
    _bgr = cv2.cvtColor(np.uint8([[[_hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0, 0]
    return int(_bgr[0]), int(_bgr[1]), int(_bgr[2])


def compose(layers: list[tuple[np.ndarray, str]],
            size: tuple[int, int] | None = None,
            boxes: list[tuple[list, int]] | None = None) -> np.ndarray | None:
    """``(raster, handler_type)`` 목록을 BGR 한 장으로 합성한다 (없으면 None).

    - **BGR(3채널)** — 배경. 여럿이면 평균 블렌딩(여러 base 를 겹쳐 보는 기존 동작).
    - **라벨맵(``segmap``)** — 픽셀값(= obj_id+1)마다 다른 색.
    - **이진 mask(그 외 2D)** — 한 색으로 반투명 오버레이.

    Args:
        layers: 트리 순서(위→아래)대로의 ``(raster, type)``.
        size: base 가 없을 때 캔버스 크기 ``(H, W)``.
        boxes: 겹쳐 그릴 bbox ``[(xyxy, 색 인덱스), …]`` — 객체 상자는 raster 가 아니라 attr 이라
            layer 로 안 오고 여기로 온다(색은 라벨과 맞춘다).
    """
    _bases = [_l for _l, _t in layers if _l.ndim == 3]
    _overlays = [(_l, _t) for _l, _t in layers if _l.ndim == 2]

    _out = _merge_bases(_bases)
    if _out is None:
        _h, _w = size or _infer_size(_overlays) or (480, 640)
        _out = np.zeros((_h, _w, 3), np.uint8)

    for _i, (_raster, _type) in enumerate(_overlays):
        if _raster.shape[:2] != _out.shape[:2]:
            continue
        if _type == "segmap":
            for _label in range(1, int(_raster.max()) + 1):
                _region = _raster == _label
                if _region.any():
                    _blend(_out, _region, color_for(_label - 1))
        else:                                              # 이진 mask
            _region = _raster > 0
            if _region.any():
                _blend(_out, _region, color_for(_i))

    for _box, _idx in (boxes or []):
        if _box and len(_box) == 4:
            _x0, _y0, _x1, _y1 = (int(round(float(_v))) for _v in _box)
            cv2.rectangle(_out, (_x0, _y0), (_x1, _y1), color_for(_idx), 2)
    return _out


def _blend(canvas: np.ndarray, region: np.ndarray, color, alpha: float = _ALPHA) -> None:
    """``region`` 을 ``color`` 로 반투명 덮는다 (in-place)."""
    canvas[region] = ((1 - alpha) * canvas[region]
                      + alpha * np.array(color, np.float32)).astype(np.uint8)


def _merge_bases(bases: list[np.ndarray]) -> np.ndarray | None:
    """BGR base 들을 동일 가중치로 평균한다 (첫 장 크기를 캔버스로)."""
    if not bases:
        return None
    if len(bases) == 1:
        return bases[0].copy()
    _h, _w = bases[0].shape[:2]
    _acc = np.zeros((_h, _w, 3), np.float32)
    for _b in bases:
        _acc += (cv2.resize(_b, (_w, _h)) if _b.shape[:2] != (_h, _w) else _b).astype(np.float32)
    return (_acc / len(bases)).astype(np.uint8)


def _infer_size(overlays) -> tuple[int, int] | None:
    return overlays[0][0].shape[:2] if overlays else None
