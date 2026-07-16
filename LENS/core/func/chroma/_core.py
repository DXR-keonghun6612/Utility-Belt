"""크로마 primitive — 색공간 변환 · 채널 거리 · 누산 · robust 배경 통계.

``_space.ChromaSpace`` 가 색공간 의존값(채널·bins·순환 여부·cvt code)을 들고, 여기 함수들은 그 spec 을
받아 계산만 한다. 이미지·배열만 알고 저장 표현은 모른다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ._space import ChromaSpace


def Cyclic_delta(values: np.ndarray, mu: float | np.ndarray, period: int) -> np.ndarray:
    """순환 채널(예: hue)의 wrap 보정 거리. ``mu`` 는 스칼라/배열 모두 허용(브로드캐스팅)."""
    d = np.abs(values - mu)
    return np.minimum(d, period - d)


def Channel_delta(
    values: np.ndarray, mu: float | np.ndarray, circular: bool, period: int
) -> np.ndarray:
    """채널 한 개의 평균 대비 편차. ``circular`` 이면 wrap 보정, 아니면 단순 차분."""
    if circular:
        return Cyclic_delta(values, mu, period)
    return values - mu


def To_chroma(image: np.ndarray, space: ChromaSpace) -> np.ndarray:
    """BGR 프레임을 ``space`` 로 옮겨 2채널 크로마 ``(H, W, 2)`` float32 를 뽑는다 (명도 버림).

    명도(HSV 의 ``V``, Lab 의 ``L``)는 조명에 취약해 배경모델에서 제외한다 — 색 2채널만으로 배경을
    모델링해야 조명이 흔들려도 같은 배경으로 인식된다.
    """
    _c0, _c1 = space.channels
    _img = cv2.cvtColor(image, space.cvt_code).astype(np.float32)
    return _img[..., (_c0, _c1)]


def Accumulate_histogram(
    chroma_image: np.ndarray, space: ChromaSpace, *,
    c0_acc: np.ndarray | None = None, c1_acc: np.ndarray | None = None,
    per_pixel: bool = False, selection: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """크로마 2채널을 누산 히스토그램에 더해 **갱신본**을 돌려준다 (순수 reducer).

    누산기를 입력으로 받아 출력하므로 호출 측이 프레임 간 이월(carry)하면 무상태로 cross-frame 누산이
    된다. 누산기가 ``None`` 이면 모양을 맞춰 새로 만든다(첫 프레임).

    ``per_pixel`` 이면 픽셀마다 ``(H,W,B)`` 히스토그램을 든다 — 각 ``(y,x)`` 는 마지막 축의 자기 bin
    하나만 증가하므로 ``take/put_along_axis`` 로 처리한다(인덱스 그리드 캐시가 필요 없어 무상태이고
    프레임당 그리드 할당도 없다). 전역이면 ``(B,)`` 1-D 로 합산한다.

    Args:
        chroma_image: ``(H,W,2)`` 크로마.
        space: 색공간 spec (bins 를 쓴다).
        c0_acc: 채널0 누산기. None 이면 생성.
        c1_acc: 채널1 누산기. None 이면 생성.
        per_pixel: 픽셀별 누산 여부.
        selection: 누산할 픽셀 bool ``(H,W)``. None 이면 전체.

    Returns:
        ``(c0_acc, c1_acc)`` 갱신본. 픽셀별은 ``uint16``, 전역은 ``float64``.
    """
    _b0, _b1 = space.bins
    _c0 = np.clip(chroma_image[..., 0], 0, _b0 - 1).astype(np.int32)
    _c1 = np.clip(chroma_image[..., 1], 0, _b1 - 1).astype(np.int32)

    if per_pixel:
        if c0_acc is None:
            _H, _W = _c0.shape
            c0_acc = np.zeros((_H, _W, _b0), dtype=np.uint16)
            c1_acc = np.zeros((_H, _W, _b1), dtype=np.uint16)
        _i0, _i1 = _c0[..., None], _c1[..., None]
        _inc = np.uint16(1) if selection is None else selection[..., None].astype(np.uint16)
        np.put_along_axis(c0_acc, _i0, np.take_along_axis(c0_acc, _i0, -1) + _inc, axis=-1)
        np.put_along_axis(c1_acc, _i1, np.take_along_axis(c1_acc, _i1, -1) + _inc, axis=-1)
    else:
        if c0_acc is None:
            c0_acc = np.zeros(_b0, dtype=np.float64)
            c1_acc = np.zeros(_b1, dtype=np.float64)
        if selection is not None:
            _c0, _c1 = _c0[selection], _c1[selection]
        c0_acc += np.bincount(_c0.ravel(), minlength=_b0)[:_b0]
        c1_acc += np.bincount(_c1.ravel(), minlength=_b1)[:_b1]

    return c0_acc, c1_acc


def Distance_map(
    image: np.ndarray, space: ChromaSpace, *,
    mean: tuple[np.ndarray, np.ndarray], std: tuple[np.ndarray, np.ndarray],
    sigma_floor: float = 1.0,
) -> np.ndarray | None:
    """배경 크로마 모델 대비 **정규화 편차 맵** ``√((Δc0/σ0)² + (Δc1/σ1)²)``.

    모델이 스칼라(전역)든 ``(H,W)``(픽셀별)든 브로드캐스팅으로 같은 코드가 처리한다. 순환 채널(hue)의
    wrap 은 :func:`Channel_delta` 가 보정하고, ``sigma_floor`` 가 작은 σ 로 인한 거리 폭주를 막는다.

    Args:
        image: BGR 프레임 ``(H,W,3)``.
        space: 색공간 spec.
        mean: ``(mean_c0, mean_c1)`` — 스칼라 또는 ``(H,W)``.
        std: ``(std_c0, std_c1)`` — 스칼라 또는 ``(H,W)``.
        sigma_floor: σ 하한.

    Returns:
        ``(H,W)`` float32 거리 맵. 픽셀별 모델의 크기가 프레임과 다르면 None(정적 카메라 가정 위반).
    """
    _m0 = np.asarray(mean[0], np.float32)
    _m1 = np.asarray(mean[1], np.float32)
    _s0 = np.maximum(np.asarray(std[0], np.float32), sigma_floor)
    _s1 = np.maximum(np.asarray(std[1], np.float32), sigma_floor)
    for _a in (_m0, _m1, _s0, _s1):
        if _a.ndim and _a.shape != image.shape[:2]:
            return None

    _ch0, _ch1   = space.channels
    _b0, _b1     = space.bins
    _cir0, _cir1 = space.circular
    _img = cv2.cvtColor(image, space.cvt_code).astype(np.float32)

    _d0 = Channel_delta(_img[..., _ch0], _m0, _cir0, _b0)
    _d1 = Channel_delta(_img[..., _ch1], _m1, _cir1, _b1)
    return np.sqrt((_d0 / _s0) ** 2 + (_d1 / _s1) ** 2).astype(np.float32)


def Robust_mean_std(hist: np.ndarray, circular: bool) -> tuple[np.ndarray, np.ndarray]:
    """히스토그램 → median + IQR robust 배경 평균/표준편차 (마지막 축, 벡터화, leading shape 무관).

    **왜 median+IQR 인가** — 배경이 분포의 다수이므로 가중 중앙값이 곧 배경색이고, ``IQR/1.349``
    (가우시안 σ 와 일치)가 robust σ 다. 분위수 기반이라 객체(소수 꼬리)는 둘 다 거의 못 흔든다
    (50% 미만 오염에 면역). 순환 채널(hue)은 mode 중심 ``±B/2`` 좌표로 gather 해 비순환처럼 처리한다.

    이전 mode-window 방식은 mode 에서 일정 bin 밖 표본을 통째로 버려 배경 퍼짐을 8~12배 **과소추정**
    했고, 작은 σ 가 정규화 거리를 폭주시켜 모든 픽셀이 전경이 됐다. 분위수 척도는 배경의 실제 spread 를
    보존하면서 객체 꼬리는 무시한다.

    Args:
        hist: 마지막 축이 bin 인 히스토그램. ``(B,)`` 또는 ``(H,W,B)``.
        circular: hue 처럼 0 과 끝이 이어지는 채널이면 True.

    Returns:
        ``(mean, std)`` float32. ``(B,)``→스칼라, ``(H,W,B)``→``(H,W)``. 표본이 없는 위치는 ``0``.
    """
    _b    = hist.shape[-1]
    _mode = np.argmax(hist, axis=-1).astype(np.int32)            # (...,) 최빈 bin = 좌표 중심
    if circular:
        # mode를 중심에 두는 ±B/2 좌표로 가중치만 gather → 순환을 비순환처럼 (좌표는 상수 offset)
        _idx   = (_mode[..., None] - _b // 2 + np.arange(_b, dtype=np.int32)) % _b
        _w     = np.take_along_axis(hist, _idx, axis=-1).astype(np.float64)
        _coord = np.arange(_b, dtype=np.float64) - _b // 2       # (B,) mode 기준 offset
    else:
        _w     = hist.astype(np.float64)
        _coord = np.arange(_b, dtype=np.float64)                 # (B,) 절대 bin

    _cw  = np.cumsum(_w, axis=-1)                                # (..., B) 누적 가중
    _tot = _cw[..., -1:]                                         # (..., 1) 총 표본

    def _q(p: float) -> np.ndarray:                             # 가중 분위수 (좌표 오름차순)
        _k = np.argmax(_cw >= _tot * p, axis=-1)                # 누적이 p 넘는 첫 bin
        return _coord[_k]

    _med   = _q(0.5)
    _sigma = (_q(0.75) - _q(0.25)) / 1.349                       # IQR → σ (robust)
    _mean  = (_mode.astype(np.float64) + _med) % _b if circular else _med

    _ok    = _tot[..., 0] > 0                                    # 표본 없는 위치 = 0
    _mean  = np.where(_ok, _mean,  0.0)
    _sigma = np.where(_ok, _sigma, 0.0)
    return _mean.astype(np.float32), _sigma.astype(np.float32)
