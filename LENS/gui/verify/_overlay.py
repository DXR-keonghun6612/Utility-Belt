"""base 이미지 + annotation mask/bbox 합성 유틸 (검증 없이 보이는 대로)."""

from __future__ import annotations

import cv2
import numpy as np

from core.data import handler
from core.data.meta import Dataset_Meta


def color_for(idx: int) -> tuple[int, int, int]:
    """object 인덱스에 대응하는 BGR 색을 생성한다.

    황금각(golden angle)으로 hue 를 돌려 인접 인덱스끼리 색이 잘 구분되게 한다.

    Args:
        idx: object 인덱스.

    Returns:
        BGR ``(b, g, r)`` 튜플.
    """
    _hue = int(idx * 180 * 0.618033988749895) % 180  # OpenCV hue 범위: 0~179
    _bgr = cv2.cvtColor(np.uint8([[[_hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0, 0]
    return int(_bgr[0]), int(_bgr[1]), int(_bgr[2])


def load_base_images(meta: Dataset_Meta, stem: str) -> dict[str, np.ndarray]:
    """stem의 frame.info 중 이미지로 디코드되는 것을 모두 로드한다.

    경로 파생·디코드는 ``handler.Load`` 에 위임한다 (계산 계층은 위치·타입만 정함). attr·객체(stem) 등
    이미지가 아닌 값은 제외한다.

    Returns:
        ``{key: BGR ndarray}`` — 이미지가 아닌 키는 제외.
    """
    _out: dict[str, np.ndarray] = {}
    _frame = meta.Get(stem)
    if _frame is None:
        return _out
    _root = meta.State_root(meta.State_of(stem))   # 프레임 파일은 그 stem 의 상태 버킷에
    for _key, _ref in _frame.info.items():
        if _ref.Is_stem() or _ref.type == "segmap":   # 객체(컨테이너)·인스턴스 라벨맵은 base 아님
            continue
        _val = handler.Load(_root, stem, _key, _ref)
        if isinstance(_val, np.ndarray) and _val.ndim >= 2:
            _out[_key] = _val if _val.ndim == 3 else cv2.cvtColor(_val, cv2.COLOR_GRAY2BGR)
    return _out


def load_segment(meta: Dataset_Meta, stem: str) -> np.ndarray | None:
    """stem 의 ``frame.info["segment"]`` 인스턴스 라벨맵을 ``(H, W)`` uint8 로 로드한다.

    객체별 mask 는 더 이상 따로 저장하지 않고 이 한 장(픽셀값 = obj_id + 1, 0 = 배경)에서
    파생한다. segment 가 없으면 ``None``.
    """
    _frame = meta.Get(stem)
    if _frame is None:
        return None
    _ref = _frame.info.get("segment")
    if _ref is None:
        return None
    _root = meta.State_root(meta.State_of(stem))   # 프레임 파일은 그 stem 의 상태 버킷에
    _val = handler.Load(_root, stem, "segment", _ref)
    return _val if isinstance(_val, np.ndarray) and _val.ndim == 2 else None


def mask_from_segment(segment: np.ndarray | None, obj_id: str) -> np.ndarray | None:
    """인스턴스 라벨맵에서 한 객체(``segment == obj_id + 1``)의 이진 mask 를 뽑는다.

    Returns:
        ``(H, W)`` uint8 (0/1) mask. segment 가 없거나 obj_id 가 정수가 아니거나 해당 영역이
        비어 있으면 ``None``.
    """
    if segment is None:
        return None
    try:
        _v = int(obj_id) + 1
    except (TypeError, ValueError):
        return None
    _m = (segment == _v)
    return _m.astype(np.uint8) if _m.any() else None


def merge_bases(images: list[np.ndarray]) -> np.ndarray | None:
    """여러 base 이미지를 동일 가중치 투명도로 블렌딩해 한 장으로 병합한다.

    첫 이미지 크기를 캔버스로 삼고 나머지는 그 크기로 리사이즈한 뒤 평균한다.
    (N장이면 각 1/N 불투명도로 겹친 것과 같다.)

    Args:
        images: 병합할 BGR 이미지 리스트. ``None`` 항목은 무시한다.

    Returns:
        병합된 BGR uint8 이미지. 유효 이미지가 없으면 ``None``.
    """
    _imgs = [_im for _im in images if _im is not None]
    if not _imgs:
        return None
    if len(_imgs) == 1:
        return _imgs[0]
    _h, _w = _imgs[0].shape[:2]
    _acc = np.zeros((_h, _w, 3), dtype=np.float32)
    for _im in _imgs:
        if _im.shape[:2] != (_h, _w):
            _im = cv2.resize(_im, (_w, _h))
        _acc += _im.astype(np.float32)
    return (_acc / len(_imgs)).astype(np.uint8)


def compose(
    base: np.ndarray | None,
    layers: list[dict],
    *,
    size: tuple[int, int] | None = None,
    alpha: float = 0.45,
    handles: list[tuple[int, int]] | None = None,
    preview: tuple[int, int, int, int] | None = None,
    preview_circle: tuple[float, float, float] | None = None,
    preview_poly: list[tuple[int, int]] | None = None,
) -> np.ndarray:
    """base 이미지 위에 mask/bbox 레이어(+편집 핸들/미리보기)를 합성해 BGR 이미지를 만든다.

    Args:
        base: 배경 BGR 이미지. ``None`` 이면 검은 캔버스를 생성한다.
        layers: 각 annotation 레이어. 키 ``mask``/``bbox``/``color``/``show_mask``/
            ``show_bbox`` 를 갖는 dict 리스트.
        size: base 가 ``None`` 일 때 캔버스 크기 ``(H, W)``.
        alpha: mask 오버레이 불투명도.
        handles: 선택된 bbox 의 코너 핸들 좌표 ``[(x, y), …]`` (편집용 — 노란 사각형).
        preview: 그리는 중인 bbox ``(x0, y0, x1, y1)`` (점선 대용 얇은 노란 사각형).
        preview_circle: 그리는 중인 원 ``(cx, cy, radius)`` (얇은 노란 원).
        preview_poly: 그리는 중인 다각형 꼭짓점(+커서) ``[(x, y), …]`` (노란 폴리라인 + 꼭짓점 점).

    Returns:
        합성된 BGR uint8 이미지.
    """
    if base is not None:
        _out = base.copy()
    else:
        _h, _w = size if size else (480, 640)
        _out = np.zeros((_h, _w, 3), dtype=np.uint8)

    for _ly in layers:
        _mask = _ly.get("mask")
        if _ly.get("show_mask") and _mask is not None:
            _region = _mask > 0
            if _region.shape == _out.shape[:2]:
                _color = np.array(_ly["color"], dtype=np.float32)
                _out[_region] = (
                    (1 - alpha) * _out[_region] + alpha * _color
                ).astype(np.uint8)

    for _ly in layers:
        _bbox = _ly.get("bbox")
        if _ly.get("show_bbox") and _bbox and len(_bbox) == 4:
            _x0, _y0, _x1, _y1 = (int(round(_v)) for _v in _bbox)
            cv2.rectangle(_out, (_x0, _y0), (_x1, _y1), _ly["color"], 2)

    # 그리는 중 미리보기 사각형 (RoI)
    if preview is not None and len(preview) == 4:
        _x0, _y0, _x1, _y1 = (int(round(_v)) for _v in preview)
        cv2.rectangle(_out, (_x0, _y0), (_x1, _y1), (0, 255, 255), 1)

    # 그리는 중 미리보기 원
    if preview_circle is not None and len(preview_circle) == 3:
        _cx, _cy, _r = preview_circle
        cv2.circle(_out, (int(round(_cx)), int(round(_cy))),
                   max(1, int(round(_r))), (0, 255, 255), 1)

    # 그리는 중 미리보기 다각형 (폴리라인 + 꼭짓점 점, 마지막 점은 커서)
    if preview_poly:
        _pts = [(int(round(_x)), int(round(_y))) for _x, _y in preview_poly]
        for _i in range(len(_pts) - 1):
            cv2.line(_out, _pts[_i], _pts[_i + 1], (0, 255, 255), 1)
        for _px, _py in _pts:
            cv2.circle(_out, (_px, _py), 3, (0, 255, 255), -1)

    # 선택된 bbox 의 코너 핸들 (노란 사각형 + 검은 테두리)
    for _hx, _hy in (handles or []):
        _hx, _hy = int(_hx), int(_hy)
        cv2.rectangle(_out, (_hx - 4, _hy - 4), (_hx + 4, _hy + 4), (0, 255, 255), -1)
        cv2.rectangle(_out, (_hx - 4, _hy - 4), (_hx + 4, _hy + 4), (0, 0, 0), 1)

    return _out
