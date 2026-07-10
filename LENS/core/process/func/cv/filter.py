"""도메인 무관 OpenCV 필터 primitive — 어느 도메인 유닛이든 쓰는 generic 연산.

특정 도메인 의미가 없는 raster 필터(Canny·LoG edge·morphology 커널·hysteresis 임계·연결성분/윤곽 채움)
만 모은다. 그래서 chroma·filter·mask 어디서 써도 도메인 누수가 아니다. mask 전경·구멍 등 의미가 붙은
primitive 는 ``func/mask``, 좌표 변환은 ``func/cv/geom``.
"""

from __future__ import annotations

import cv2
import numpy as np

from ....typing import GRAY_IMAGE


def Make_morph_kernel(size: int = 3) -> np.ndarray:
    """사각형 morphology 커널을 생성한다."""
    return cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))


def Close_gaps(mask: GRAY_IMAGE, size: int = 5) -> GRAY_IMAGE:
    """morphology CLOSE 로 ``size`` px 이하의 틈을 메워 끊긴 구조를 잇는다.

    Canny edge 는 경계가 군데군데 끊겨 그대로 채우면 내부가 배경으로 샌다. CLOSE(팽창→침식)가 틈을
    메워 뒤의 채움을 가능하게 한다. OPEN(잡티 제거)은 얇은 edge 자체를 지워버려 여기 쓰지 않는다.
    """
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, Make_morph_kernel(size))


def Morph_clean(mask: GRAY_IMAGE, *, close_size: int = 3, open_size: int = 3,
                reverse: bool = False) -> GRAY_IMAGE:
    """morphology CLOSE 와 OPEN 을 차례로 적용해 이진 mask 를 다듬는다.

    기본 순서는 **CLOSE → OPEN** — 작은 구멍을 먼저 메운 뒤 가는 잡티를 털어낸다. 순서를 뒤집으면
    (``reverse``) 잡티를 먼저 털고 구멍을 메우므로, 잡티가 구멍에 붙어 있을 때 결과가 달라진다.

    Args:
        mask: 이진 mask ``(H,W)``.
        close_size: CLOSE 커널 크기(px).
        open_size: OPEN 커널 크기(px).
        reverse: True 면 OPEN → CLOSE 순서.

    Returns:
        다듬어진 mask (전부 0 일 수 있다 — 판단은 호출 측 몫).
    """
    _ops = ((cv2.MORPH_OPEN, open_size), (cv2.MORPH_CLOSE, close_size))
    if not reverse:                             # 기본: CLOSE → OPEN
        _ops = _ops[::-1]
    _m = mask
    for _op, _size in _ops:
        _m = cv2.morphologyEx(_m, _op, Make_morph_kernel(_size))
    return _m


def Canny_edges(image: np.ndarray, *, low: int = 50, high: int = 150,
                blur: int = 1, gray: bool = True) -> GRAY_IMAGE | None:
    """Canny edge(0/255)를 뽑는다. gray 한 장(기본) 또는 채널별 Canny 를 OR 로 합쳐서.

    gray 변환 후 한 장에서 검출하는 것이 OpenCV 표준이다 — 빠르고 노이즈가 적다. 다만 gray 는
    **등휘도 색차**(밝기가 같고 색만 다른 경계)를 놓치므로, ``gray=False`` 면 채널별로 Canny 를 돌려
    OR 로 합친다("어느 채널에서든 바뀌는 곳"). 색공간 변환·조명 정규화 없이 raw 에서 바로 검출한다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)``.
        low: Canny 하한 임계.
        high: Canny 상한 임계.
        blur: 검출 전 Gaussian blur 커널(홀수). ``1`` 이하면 생략. 짝수면 ``|1`` 로 홀수화.
        gray: True 면 gray 한 장, False 면 채널별 OR.

    Returns:
        ``(H,W)`` uint8 0/255 edge. 검출된 edge 가 하나도 없으면 None.
    """
    if image.ndim == 3:
        _chans = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),) if gray else cv2.split(image)
    else:
        _chans = (image,)
    _edge: GRAY_IMAGE | None = None
    for _c in _chans:
        if blur > 1:
            _k = blur | 1                       # 짝수면 +1 (Gaussian 커널은 홀수)
            _c = cv2.GaussianBlur(_c, (_k, _k), 0)
        _e = cv2.Canny(_c, low, high)
        _edge = _e if _edge is None else cv2.bitwise_or(_edge, _e)
    return _edge if _edge is not None and _edge.any() else None


def log_edges(image: np.ndarray, *, sigma: float = 1.2, factor: float = 1.0) -> np.ndarray:
    """이미지 → LoG(Laplacian of Gaussian) edge 벽 (bool). 도메인 무관 edge 필터 primitive.

    가우시안 블러 후 Laplacian, ``|응답|`` 이 큰 곳 = 경계. 임계는 이미지마다 다르므로 LoG 표준편차에
    비례해 적응적으로 잡는다(``factor``). fill 의 색 유사 성분이 이 벽을 못 넘게 막는 데 쓴다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)``.
        sigma: 가우시안 블러 시그마.
        factor: edge 임계 = ``factor × LoG 표준편차`` (클수록 벽이 성김).

    Returns:
        ``(H,W)`` bool — True = LoG edge(벽).
    """
    _gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    _blur = cv2.GaussianBlur(_gray, (0, 0), sigma)
    _log  = cv2.Laplacian(_blur.astype(np.float32), cv2.CV_32F, ksize=3)
    _thr  = max(1.0, factor * float(np.std(_log)))
    return np.abs(_log) > _thr


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
    닫는다(``_close_border``) — 경계에 닿은 edge 끝점이 그 폭 이내로 떨어져 있을 때만 경계 변을
    따라 잇는다. 객체 사이의 **큰 배경 간격(> ``border_gap``)은 잇지 않으므로** 프레임 전체가
    한 윤곽으로 채워지는 일이 없다.

    Args:
        edge: 0/255 또는 bool edge ``(H, W)``.
        min_area: 이 값 미만 윤곽 제거 (``0`` 이면 하한 없음).
        max_area: 이 값 초과 윤곽 제거 (``None`` 이면 상한 없음).
        border_gap: 경계 틈 잇기 폭 (px, ``0`` 이면 끄기). 이미지 경계에 걸쳐 잘린 객체를 닫는다.

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


def Threshold_signed(
    score: np.ndarray, *, k: float, k_weak: float | None = None, invert: bool = False,
    min_area: int = 0, max_area: int | None = None,
) -> np.ndarray:
    """스코어 맵을 이진화한다 — ``invert`` 면 **작은 쪽**이 전경(배경 추출).

    ``Threshold_hysteresis`` 는 "큰 쪽이 전경"만 안다. 작은 쪽을 전경으로 삼으려면 맵의 부호를 뒤집어
    ``-score`` 에 음수 임계를 걸면 되는데, 이때 **strong/weak 의 역할도 함께 뒤집힌다** — 원래 느슨하던
    ``k_weak`` 가 부호 반전 후엔 더 엄격해지므로 둘을 맞바꿔 넣어야 hysteresis 방향이 보존된다.
    그 자리가 여기다.

    Args:
        score: 스코어/거리 맵 ``(H,W)``.
        k: strong 임계.
        k_weak: hysteresis 확장 임계. None 이면 단순 임계.
        invert: True 면 스코어가 **작은** 픽셀을 전경으로.
        min_area: strong 씨앗 최소 면적.
        max_area: strong 씨앗 최대 면적 (None = 상한 없음).

    Returns:
        ``(H,W)`` uint8 0/255 mask.
    """
    if not invert:
        return Threshold_hysteresis(score, k, k_weak, min_area, max_area)
    _k  = -k if k_weak is None else -k_weak     # 부호 반전 시 strong↔weak 교환
    _kw = None if k_weak is None else -k
    return Threshold_hysteresis(-score, _k, _kw, min_area, max_area)


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
