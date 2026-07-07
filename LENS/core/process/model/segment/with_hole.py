"""구멍 보존 segment 특화 — 채워진 mask 안의 관통부(hole·slit)를 파내는 프로세스.

**Segment_with_hole** 는 ``Base_segment`` 의 ``_segment_box`` 를 오버라이드해, backend best mask
에서 사출품의 구멍/슬릿을 파낸다. 전체 흐름:

0. **Pass-1** — RGB(+box+text) → backend best mask(구멍 메워진 solid) + low-res logit.
1. **색 씨앗** (``_color_seed``) — Pass-1 mask 안에서 rim 재질색과 **chroma 편차가 큰** 픽셀.
   "여기 비-객체 뭔가 있다" 를 국소화만 한다(정밀할 필요 없음).
2. **edge 확대** (``_edge_grow``) — Canny edge 를 장벽으로 씨앗을 ``iters`` px 만 경계 제한 팽창.
   색이 일부만 잡은 얇은 슬릿을 실제 경계까지 뻗는다(유한 팽창이라 누수 제한).
3. **morph-open 필터** (``_finalize_holes``) — 작은 조각 제거 + 얇은 누수 채널 절단, 씨앗을 품은
   성분만 최종 구멍 raw seg 로.
4. **Pass-2** (``_refine_holes``) — 구멍 raw seg 를 **negative point + mask_input logit 억제**로
   주고 box+text 로 재예측 → 객체seg. 경계를 모델 품질로 다시 그린다(하드 carve 없이 이 출력 채택).

backend 는 ``model`` 필드로 주입되는 promptable segmenter(``{type: sam3}`` → ``Sam3_runner``);
``encode``/``run`` 계약만 지키면 교체된다. ``hole_debug`` 면 중간값(seg_raw/씨앗/edge/구멍)을 저장.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

import cv2
import numpy as np

from ..._base import GRAY_IMAGE, UI
from ... import PROCESS_REGISTRY
from ._base import Base_segment, _to_binary


# 구멍 검출 색공간 → (BGR 변환 코드 | None, 밝기 채널 idx | None). 편차는 밝기 채널을 **뺀** chroma
# 로만 재고(반사·조명 영향 감소), 밝기 채널은 dark_boost(그림자진 구멍 보강)에만 쓴다.
# rgb 는 밝기 채널이 분리 안 돼 아무것도 안 버린다 — z-score 로 정규화해도 그림자/반사(상관된 밝기
# 변화)가 세 채널에 함께 실려 chroma 방식보다 밝기에 취약할 수 있다(실험용).
_SPACE = {
    "lab": (cv2.COLOR_BGR2LAB, 0),   # L(밝기), a, b → a,b 만
    "hsv": (cv2.COLOR_BGR2HSV, 2),   # H, S, V(밝기) → H,S 만
    "rgb": (None, None),             # B,G,R 전부 (밝기 분리 없음)
}


def _spread_points(comp_bool: np.ndarray, k: int) -> list[tuple[float, float]]:
    """성분(bool mask) 안에서 고르게 퍼진 ``k`` 개 픽셀 좌표 ``(x, y)`` 를 뽑는다.

    긴 슬릿은 중심점 하나로 SAM 이 다 못 파내므로, 성분을 따라 여러 negative point 를
    뿌리기 위한 샘플러. 실제 성분 픽셀을 고르므로 항상 구멍 내부에 위치한다.
    """
    _ys, _xs = np.where(comp_bool)
    _n = _xs.size
    if _n == 0:
        return []
    _idx = np.linspace(0, _n - 1, max(1, min(int(k), _n))).astype(int)
    return [(float(_xs[_i]), float(_ys[_i])) for _i in _idx]


def _color_seed(frame_bgr: np.ndarray, mask255: GRAY_IMAGE, *, space: str = "lab",
                color_thr: float = 3.0, var_max: float = 0.0, rim_px: int = 7,
                dark_pct: float = 15.0, dark_boost: bool = False,
                highlight_pct: float = 0.0, dense_win: int = 5, dense_min: int = 1) -> np.ndarray:
    """mask 안에서 rim 재질 색분포 기준 **Mahalanobis k 시그마 밖**인 픽셀(구멍 씨앗)을 bool 로 낸다.

    바깥 rim(재질) chroma 의 **평균 μ·공분산 Σ** 로 Mahalanobis 거리를 재, ``color_thr`` (=k) 이상
    벗어난 mask 내 픽셀을 이상치=구멍 후보로 고른다. 절대 편차가 아니라 **재질 자신의 분포 대비 상대
    편차**라, 조명·곡률로 재질색이 완만히 변하는 단색 몸통은 통과하고(가짜 씨앗 X), 구멍(배경색, 수 σ
    밖)만 남는다. **full 공분산**이라 재질 변동의 **고분산 주축(밝기 등)이 자동 down-weight** 돼 색공간
    선택·밝기 채널 제거에 둔감하다 — ``space`` 는 lab/hsv(chroma) 뿐 아니라 rgb(전 채널)도 쓸 수 있다.
    ``dark_boost`` 면 그림자진 구멍을 밝기 하위 백분위로 보강(rgb 는 밝기 채널이 없어 스킵).
    ``highlight_pct>0`` 이면 그 밝기 백분위보다 밝은 픽셀(정반사 하이라이트)을 **씨앗에서 제외** —
    반사는 재질과 chroma 가 달라 이상치로 잡히지만 구멍이 아니므로 flood 전에 뺀다(rgb 는 채널 평균 밝기).
    마지막에 **밀도 필터**(``dense_min>1``): ``dense_win`` 이웃에 씨앗이 ``dense_min`` 개 미만인 픽셀을
    제거해 고립 잡음을 걸러낸다(morph-open 대신 — 뭉친 씨앗=진짜 구멍만 남긴다).

    **기준 분포는 바깥 rim 밴드**(``rim_px``, mask 경계에서 안쪽으로 이만큼)에서 뽑는다 — SAM mask 의
    외곽 실루엣 안쪽 띠는 solid 든 도넛이든 **항상 재질**이라, 구멍이 mask 내부를 다 차지해도
    (도넛형) 대표색이 배경으로 뒤집히지 않는다. rim 이 너무 얇으면 mask 전체로 폴백. Σ 에 단위행렬을
    더해(σ²≥1) 특이·과민을 막는다. 씨앗 판정·게이트 모두 이 rim 기준.

    **분산 게이트** (``var_max>0``): 씨앗은 "균질한 재질 속 이상치" 라는 전제라, **rim chroma 의
    채널별 표준편차**(색 클러스터 퍼짐)가 ``var_max`` 를 넘으면(=재질 자체가 다색인 비-균질 객체)
    이상치 판정이 못 미더워 **빈 씨앗을 반환**한다(→ 구멍 없음 → 원본 solid 유지). 단색 객체만 색으로
    구멍을 판다. spread 는 blur 한 chroma 로 재 **픽셀 노이즈가 아니라 지역 톤 차이**만 잡고, rim
    에서 재 내부 구멍(도넛)에 안 흔들린다. (게이트 var_max 는 절대 chroma std, color_thr 는 σ 배수)
    """
    _m = mask255 > 0
    if not _m.any():
        return np.zeros(mask255.shape[:2], bool)
    if space not in _SPACE:
        raise ValueError(f"space 는 {tuple(_SPACE)} 중 하나여야 한다: {space!r}")
    _code, _light = _SPACE[space]
    _col   = (frame_bgr if _code is None else cv2.cvtColor(frame_bgr, _code)).astype(np.float32)
    _chrom = _col if _light is None else np.delete(_col, _light, axis=2)   # 밝기 채널 제외(rgb=전부)
    _inner = (cv2.erode(_m.astype(np.uint8), np.ones((rim_px, rim_px), np.uint8)).astype(bool)
              if rim_px > 1 else np.zeros_like(_m))
    _rim   = _m & ~_inner                                    # 바깥 테두리 밴드 = 재질(구멍 무관)
    _ref   = _rim if int(_rim.sum()) > 50 else _m            # 너무 얇으면 mask 전체로 폴백
    _R     = _chrom[_ref].reshape(-1, _chrom.shape[2])       # rim 재질 픽셀 (N, C)
    _mu    = _R.mean(axis=0)                                 # 재질 평균색
    _cov   = np.cov(_R, rowvar=False).reshape(_R.shape[1], _R.shape[1])
    _cov  += np.eye(_cov.shape[0], dtype=_cov.dtype)         # σ²≥1 정칙화 (특이·과민 방지)
    _inv   = np.linalg.inv(_cov)                             # Mahalanobis 용 Σ⁻¹
    if var_max > 0:                                          # 게이트: 재질 색 퍼짐(다색) → 스킵
        _blur = cv2.GaussianBlur(_chrom, (5, 5), 0)          # 픽셀 노이즈 제거(지역 톤만)
        if float(np.mean(np.std(_blur[_ref], axis=0))) > var_max:
            return np.zeros(mask255.shape[:2], bool)
    _d     = _chrom - _mu                                    # (H, W, C)
    # rim 재질 분포의 Mahalanobis 거리 — 고분산 주축(밝기 등)은 자동 down-weight → 색공간 무관.
    _z     = np.sqrt(np.maximum(np.einsum("...i,ij,...j->...", _d, _inv, _d), 0.0))
    _seed  = (_z > color_thr) & _m                           # k 시그마(Mahalanobis) 밖 = 구멍 후보
    if dark_boost and _light is not None:                    # 그림자진 구멍 보강 (밝기 채널 필요 — rgb 는 스킵)
        _seed |= (_col[..., _light] < np.percentile(_col[_ref, _light], dark_pct)) & _m
    if highlight_pct > 0:                                    # 정반사 하이라이트 제거 (씨앗에서 뺌)
        _bright = _col[..., _light] if _light is not None else _col.mean(axis=2)
        _seed &= ~(_bright > np.percentile(_bright[_m], highlight_pct))
    if dense_min > 1:                                        # 밀도 필터: dense_win 이웃에 씨앗 dense_min 개 미만이면 제거
        _cnt = cv2.boxFilter(_seed.astype(np.float32), -1, (dense_win, dense_win),
                             normalize=False)                # 이웃 씨앗 개수(자기 포함)
        _seed &= _cnt >= dense_min                           # 뭉친 씨앗만 유지(고립 잡음 제거)
    return _seed


def _canny_edge(frame: np.ndarray, *, low: int = 50, high: int = 150,
                blur: int = 3, gray: bool = True) -> GRAY_IMAGE | None:
    """프레임 → cv2 Canny edge(0/255). gray 한 장(기본) / 채널별 OR(``gray=False``). 비면 None.

    (edge/Detect_edge 와 로직 동일 — 지금은 segment 안에 둔다, 나중에 공용 util 로 정리.)
    """
    if frame.ndim == 3:
        _chans = (cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),) if gray else cv2.split(frame)
    else:
        _chans = (frame,)
    _edge: GRAY_IMAGE | None = None
    for _c in _chans:
        if blur > 1:
            _k = blur | 1                                    # 짝수면 +1 (Gaussian 커널은 홀수)
            _c = cv2.GaussianBlur(_c, (_k, _k), 0)
        _e = cv2.Canny(_c, low, high)
        _edge = _e if _edge is None else cv2.bitwise_or(_edge, _e)
    if _edge is None or not _edge.any():
        return None
    return _edge


def _edge_grow(mask255: GRAY_IMAGE, seed: np.ndarray, edge: GRAY_IMAGE, *,
               boundary_margin: int = 3, close_size: int = 5,
               barrier_thick: int = 3, iters: int = 12) -> np.ndarray:
    """씨앗을 **edge 를 못 넘게 ``iters`` 스텝만 팽창**(경계 제한 geodesic dilation) → bool.

    내부 edge(외곽 실루엣 제외)를 CLOSE 로 잇고 ``barrier_thick`` 로 두껍게 해 장벽을 만든 뒤,
    씨앗을 3×3 로 반복 팽창하되 매 스텝 ``mask & ~장벽`` 안으로 제한한다. 색이 일부만 잡은 얇은
    슬릿을 벽(edge)을 따라 뻗고, 씨앗(양성 증거)이 앵커라 개방 슬릿도 잡는다.

    **성분 전체 채택이 아니라 유한 팽창**인 게 핵심 — 실제 프레임의 내부 edge 는 구멍을 완전히
    둘러싼 닫힌 링이 아니라 표면·반사로 띄엄띄엄 나므로, "씨앗 포함 성분"을 통째로 쓰면 몸통 전체로
    샌다. ``iters`` 로 확대를 제한하면 링 틈으로 새더라도 최대 ``iters`` px 로 묶이고, 남은 얇은
    누수 채널은 후속 morph-open(``_finalize_holes``)이 끊는다. 긴 슬릿을 끝까지 뻗으려면 ``iters`` ↑.
    """
    _m = mask255 > 0
    _interior = (cv2.erode(_m.astype(np.uint8),
                           np.ones((boundary_margin, boundary_margin), np.uint8)) > 0
                 if boundary_margin else _m)
    _barrier = cv2.morphologyEx(((edge > 0) & _interior).astype(np.uint8), cv2.MORPH_CLOSE,
                                np.ones((close_size, close_size), np.uint8))
    if barrier_thick > 1:                                    # 1px 링을 solid 분리막으로
        _barrier = cv2.dilate(_barrier, np.ones((barrier_thick, barrier_thick), np.uint8))
    _free = _m & ~(_barrier > 0)                             # 확대 가능 영역 (mask 안, edge 밖)
    _grow = seed & _free
    _k    = np.ones((3, 3), np.uint8)
    for _ in range(max(int(iters), 0)):                      # 경계 제한 팽창 (유한)
        _d = (cv2.dilate(_grow.astype(np.uint8), _k) > 0) & _free
        if int(_d.sum()) == int(_grow.sum()):                # 수렴(막힘) → 중단
            break
        _grow = _d
    return _grow


def _finalize_holes(grown: np.ndarray, seed: np.ndarray, open_size: int = 5) -> GRAY_IMAGE:
    """확대 결과를 morph-open 으로 정리 → 최종 구멍(0/255).

    OPEN(``open_size``)이 작은 조각을 지우고 **얇은 누수 채널을 끊는다**(링 틈으로 몸통까지 샌 경우
    분리). 그 뒤 씨앗을 아직 품은 성분만 남겨, 끊겨 나간 몸통 조각(씨앗 없음)을 버린다.
    """
    _g = grown.astype(np.uint8)
    if open_size > 1:
        _g = cv2.morphologyEx(_g, cv2.MORPH_OPEN, np.ones((open_size, open_size), np.uint8))
    _n, _lbl = cv2.connectedComponents(_g)
    _keep = np.unique(_lbl[seed & (_g > 0)])                 # 씨앗을 아직 품은 성분만
    _keep = _keep[_keep > 0]
    if _keep.size == 0:
        return np.zeros(grown.shape[:2], np.uint8)
    return np.where(np.isin(_lbl, _keep), np.uint8(255), np.uint8(0))


@PROCESS_REGISTRY.Register_module()
@dataclass
class Segment_with_hole(Base_segment, outputs=("segment", "object"), category="모델/분할"):
    """구멍/슬릿을 보존하는 segment 정책 — 색 씨앗 → edge 확대 → morph-open 필터 → Pass-2 재예측.

    파이프라인·단계별 원리는 모듈 docstring 참조. ``class_id`` 유지·segment 재칠·bbox 재계산 등
    나머지는 ``Base_segment`` 그대로. ``hole_debug`` 면 중간값(씨앗/edge/확대)을 storage 로 뽑아
    튜닝에 쓴다(config ``outputs`` 로 라우팅).

    ── 튜닝 ──────────────────────────────────────────────────────────────────────
    구멍은 잘 파이는데 **물체까지 사라지면**(과검출) 아래를 (효과 큰 순):

    - ``hole_color_thr`` ↑ : 씨앗을 덜 민감하게 — 표면 얼룩·반사를 씨앗으로 안 삼음. 1차 노브.
    - ``hole_open_size`` ↑ : 확대 결과에서 작은 조각을 더 지우고, 링 틈으로 샌 **얇은 누수 채널을
      끊는다**. 몸통이 통째로 딸려오면 올린다.
    - ``hole_edge_close`` ↓ : 끊긴 edge 를 억지로 잇지 않아 없던 고리(→ 누수)를 안 만든다.
    - ``hole_dark_pct`` ↓ (또는 ``hole_dark_boost=false``) : 그림자를 씨앗으로 오인하는 걸 줄임.

    반대로 **구멍이 덜 파이면** 위를 반대로. 편차는 ``hole_space`` (lab/hsv)의 밝기 뺀 chroma 라
    공간 바꾸면 스케일이 달라져 ``hole_color_thr`` 도 재조정. 확대를 끄고 씨앗만 쓰려면
    ``hole_edge=false``, Pass-2 가 경계를 키우면 ``hole_refine=false``, 통째로 끄려면
    ``preserve_holes=false``.
    """

    preserve_holes: Annotated[bool, UI(label="구멍 보존", tip="채운 mask 안의 관통부(hole·slit)를 파냄")] = True
    hole_refine:    Annotated[bool, UI(label="Pass-2 정밀화", tip="negative-point + logit 억제로 구멍 경계를 모델 품질로 다시 그림")] = True
    hole_debug:     Annotated[bool, UI(label="중간값 저장", tip="씨앗/edge/확대 결과를 storage 로 (config outputs 로 라우팅)")] = False
    # ── 색 씨앗 ───────────────────────────────────────────────────────────────────
    hole_space:     Annotated[str, UI(label="구멍 검출 색공간", tip="lab | hsv | rgb — Mahalanobis 라 밝기 자동 보정(색공간 둔감)")] = "lab"
    hole_dark_boost: Annotated[bool, UI(label="어두움 단서", tip="그림자진 구멍을 밝기로 보강 — 밝기 영향을 더 줄이려면 끔")] = True
    hole_highlight_pct: Annotated[float, UI(label="하이라이트 제외 백분위 (0=끄기)", tip="이 밝기 백분위보다 밝은 픽셀(정반사)을 씨앗에서 제외 — 값↓ 더 공격적", min=0.0, max=100.0, step=1.0)] = 0.0
    hole_seed_dense_win: Annotated[int, UI(label="씨앗 밀도 이웃 크기 (px)", tip="씨앗 개수를 세는 이웃 창", min=1, max=31)] = 5
    hole_seed_dense_min: Annotated[int, UI(label="씨앗 밀도 최소 개수 (1=끄기)", tip="이웃 창에 씨앗이 이 개수 미만이면 고립 잡음으로 제거", min=1, max=100)] = 1
    hole_color_thr: Annotated[float, UI(label="씨앗 시그마 임계 (k)", tip="rim 재질 색분포 기준 k 시그마 밖이면 씨앗 — ↓ 하면 더 민감(2~4 권장, space 무관)", min=0.0, max=20.0, step=0.5)] = 3.0
    hole_seed_var_max: Annotated[float, UI(label="씨앗 분산 게이트 (0=끄기)", tip="바깥 rim chroma 편차 중앙값이 이보다 크면 비-균질 재질로 보고 구멍 검출 스킵(solid 유지)", min=0.0, max=100.0, step=1.0)] = 0.0
    hole_seed_rim:  Annotated[int, UI(label="대표색 rim 밴드 (px)", tip="mask 경계에서 안쪽으로 이만큼을 재질 참조로 — 도넛형(구멍>재질)에서 대표색 역전 방지", min=1, max=50)] = 7
    hole_dark_pct:  Annotated[float, UI(label="그림자 씨앗 밝기 하위 백분위", min=0.0, max=100.0, step=1.0)] = 15.0
    hole_open_size: Annotated[int, UI(label="크기 필터 OPEN (px, 확대 후)", tip="작은 조각 제거 + 얇은 누수 채널 절단", min=1, max=31)] = 5
    # ── edge 확대 ─────────────────────────────────────────────────────────────────
    hole_edge:       Annotated[bool, UI(label="edge 확대", tip="Canny edge 를 장벽으로 씨앗을 확대(끄면 씨앗 그대로)")] = True
    hole_edge_low:   Annotated[int, UI(label="Canny 하한 임계", min=0, max=500)]               = 50
    hole_edge_high:  Annotated[int, UI(label="Canny 상한 임계", min=0, max=500)]               = 150
    hole_edge_blur:  Annotated[int, UI(label="Canny blur (홀수, 1=생략)", min=1, max=21)]      = 3
    hole_edge_gray:  Annotated[bool, UI(label="gray Canny (끄면 채널별 OR)")]                  = True
    hole_edge_margin: Annotated[int, UI(label="edge 외곽 제외 침식 (px)", min=0, max=50)]      = 3
    hole_edge_close: Annotated[int, UI(label="edge 틈 잇기 CLOSE (px)", min=1, max=21)]        = 5
    hole_edge_thick: Annotated[int, UI(label="edge 장벽 두께 (px)", tip="1px 링을 solid 분리막으로 (8-연결 누수 차단)", min=1, max=15)] = 3
    hole_grow_iter:  Annotated[int, UI(label="확대 스텝 (px)", tip="씨앗을 edge 안에서 이만큼만 팽창 — 누수를 이 값으로 제한, 긴 슬릿은 ↑", min=0, max=100)] = 12
    # ── negative point 밀도 ───────────────────────────────────────────────────────
    hole_neg_pts_area_frac: Annotated[float, UI(label="negative point 밀도", tip="구멍 면적당", min=0.0, max=1.0, step=0.005)] = 0.01
    hole_max_pts:       Annotated[int, UI(label="구멍당 negative point 상한", min=1, max=32)] = 6
    hole_logit_neg:     Annotated[float, UI(label="Pass-2 구멍 logit 억제 강도", tip="구멍 위치 mask_input logit 값 — 음수가 강할수록 강제(0에 가까울수록 backend 자율 재판단)", min=-30.0, max=0.0, step=1.0)] = -6.0

    def Run(self, frame: np.ndarray, meta, stem: str, **kwargs) -> dict:
        # hole_debug 면 프레임 단위 중간값 누적기를 준비 → 순회 뒤 outputs 로 첨부.
        self._dbg = ({"seg_raw": np.zeros(frame.shape[:2], np.uint8),      # Pass-1 raw (구멍 메워진 solid)
                      "hole_seed": np.zeros(frame.shape[:2], np.uint8),
                      "hole_grown": np.zeros(frame.shape[:2], np.uint8)}
                     if self.hole_debug else None)
        _out = super().Run(frame, meta, stem, **kwargs)
        if _out and self._dbg is not None:
            _edge = (self._frame_edge if self._frame_edge is not None
                     else np.zeros(frame.shape[:2], np.uint8))
            _out = {**_out, "hole_edge": _edge, **self._dbg}
        return _out

    def _predict(self, frame_bgr: np.ndarray, boxes: list) -> list[GRAY_IMAGE | None]:
        # edge 는 프레임 공통 → 프레임당 1회만 계산해 각 box 의 _segment_box 가 공유.
        self._frame_edge = (
            _canny_edge(frame_bgr, low=self.hole_edge_low, high=self.hole_edge_high,
                        blur=self.hole_edge_blur, gray=self.hole_edge_gray)
            if (self.preserve_holes and (self.hole_edge or self.hole_debug)) else None)
        return super()._predict(frame_bgr, boxes)

    def _segment_box(self, state: Any, frame_bgr: np.ndarray,
                     box: np.ndarray) -> GRAY_IMAGE | None:
        """단일 box → best mask (0/255). ``preserve_holes`` 면 씨앗→확대→필터로 구멍을 파낸다."""
        _r = self.model.run(
            state, box=box, multimask_output=False,
            return_logits=self.preserve_holes)               # logit → >0 로 이진화(구멍 검출용)
        if _r is None:
            return None
        _masks, _sc, _low = _r
        _b = int(np.argmax(_sc))
        if float(_sc[_b]) < self.conf:                       # box 는 우리가 지목한 영역이라 보통 conf=0
            return None
        if not self.preserve_holes:
            return _to_binary(_masks[_b])

        _mask255 = (np.asarray(_masks[_b], dtype=np.float32) > 0).astype(np.uint8) * np.uint8(255)
        _seed = _color_seed(frame_bgr, _mask255, space=self.hole_space,
                            color_thr=self.hole_color_thr, var_max=self.hole_seed_var_max,
                            rim_px=self.hole_seed_rim, dark_pct=self.hole_dark_pct,
                            dark_boost=self.hole_dark_boost,
                            highlight_pct=self.hole_highlight_pct,
                            dense_win=self.hole_seed_dense_win,
                            dense_min=self.hole_seed_dense_min)              # 1) 색 씨앗(+게이트/하이라이트/밀도)
        if self.hole_edge and self._frame_edge is not None:                 # 2) edge 확대
            _grown = _edge_grow(_mask255, _seed, self._frame_edge,
                                boundary_margin=self.hole_edge_margin,
                                close_size=self.hole_edge_close,
                                barrier_thick=self.hole_edge_thick,
                                iters=self.hole_grow_iter)
        else:
            _grown = _seed
        _hole = _finalize_holes(_grown, _seed, self.hole_open_size)         # 3) morph-open 필터

        if self._dbg is not None:                            # 중간값 누적(프레임 단위 union) — refine 前 Pass-1
            self._dbg["seg_raw"]    = cv2.bitwise_or(self._dbg["seg_raw"], _mask255)
            self._dbg["hole_seed"]  = cv2.bitwise_or(self._dbg["hole_seed"],
                                                     _seed.astype(np.uint8) * np.uint8(255))
            self._dbg["hole_grown"] = cv2.bitwise_or(self._dbg["hole_grown"], _hole)

        # 5) 구멍 raw seg(→ negative point + logit 억제) + box + text 로 Pass-2 재예측 = 객체seg.
        _neg = self._sample_points(_mask255, _hole)
        if _neg and self.hole_refine:
            _low_best = None if _low is None else _low[_b]
            _mask255  = self._refine_holes(state, box, _mask255, _low_best, _neg, _hole)
        return cv2.bitwise_and(_mask255, cv2.bitwise_not(_hole))  # Pass-2 뒤 하드 carve (검출 구멍 확실히 제거)

    def _sample_points(self, mask255: GRAY_IMAGE, hole255: GRAY_IMAGE
                       ) -> list[tuple[float, float]]:
        """구멍 성분마다 negative point 를 뿌린다 (밀도=``hole_neg_pts_area_frac``, 상한=``hole_max_pts``)."""
        _pts: list[tuple[float, float]] = []
        if not hole255.any():
            return _pts
        _area_tot = max(int((mask255 > 0).sum()), 1)
        _per_pt   = max(1, int(self.hole_neg_pts_area_frac * _area_tot))
        _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(hole255)
        for _i in range(1, _n):
            _area = int(_stats[_i, cv2.CC_STAT_AREA])
            _pts += _spread_points(_lbl == _i, min(self.hole_max_pts, 1 + _area // _per_pt))
        return _pts

    def _refine_holes(self, state: Any, box: np.ndarray, mask255: GRAY_IMAGE,
                      low_best: np.ndarray | None, neg_pts: list[tuple[float, float]],
                      hole255: GRAY_IMAGE) -> GRAY_IMAGE:
        """Pass-2: 구멍에 negative point + mask_input logit 억제로 backend 재예측.

        객체 코어 중심에 positive point 를 앵커로 얹고 구멍마다 negative point 를 준다. 추가로
        Pass-1 low-res logit(``mask_input``)의 **구멍 위치를 음수로 억눌러**("구멍 뚫린 prior") backend
        가 관통부 경계를 **모델 품질** 로 다시 그리게 한다. 억제 강도는 ``hole_logit_neg`` (덜 강하게
        주면 backend 가 구멍을 더 자유롭게 재판단). 실패 시 입력 mask 그대로.
        """
        _core = cv2.erode((mask255 > 0).astype(np.uint8), np.ones((15, 15), np.uint8))
        _ys, _xs = np.where(_core > 0)
        _pos = [(float(_xs.mean()), float(_ys.mean()))] if _xs.size else []
        _pc  = np.asarray(_pos + neg_pts, dtype=np.float32)
        _pl  = np.asarray([1] * len(_pos) + [0] * len(neg_pts), dtype=np.int32)

        _mask_in = None
        if low_best is not None:
            _mi = low_best.astype(np.float32).copy()         # Pass-1 low-res logit prior
            if hole255.any():                                # 구멍 위치 logit 을 음수로 억제(강도=hole_logit_neg)
                _h_lr = cv2.resize(hole255, (_mi.shape[-1], _mi.shape[-2]),
                                   interpolation=cv2.INTER_NEAREST)
                _mi[..., _h_lr > 0] = self.hole_logit_neg
            _mask_in = _mi[None]

        _r = self.model.run(
            state, box=box, point_coords=_pc, point_labels=_pl,
            mask_input=_mask_in, multimask_output=False)
        if _r is None:
            return mask255
        _masks, _sc, _ = _r
        return _to_binary(_masks[int(np.argmax(_sc))])
