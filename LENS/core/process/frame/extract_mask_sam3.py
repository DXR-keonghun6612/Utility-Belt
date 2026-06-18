"""SAM3 기반 단일 프레임 객체 마스크 추출 process.

extract_mask_with_hs_stats 와 동일한 계약(frame → {"mask"})을 따르되, 분할은
SAM3(facebookresearch/sam3)로 수행한다. 선택적으로 mask 입력을 받아 앵커(시각 프롬프트)로
사용한다 — box / points / mask 중 하나로 변환해 SAM3 에 전달한다.

무거운 의존성(torch, sam3)은 lazy import 하고 predictor 를 인스턴스에 1회 캐싱한다.
프레임 process 는 frame_batch 가 1회 생성 후 프레임마다 Run 하므로, 모델 로드는 첫 Run
에서 한 번만 일어난다.

NOTE: build_sam3 / SAM3ImagePredictor 의 정확한 심볼·시그니처는 sam3 레포 기준으로
      확인 필요(아래 _Build_predictor 한 곳에 격리).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

import cv2
import numpy as np

from python_toolbox.project.config import Base_Config

from ... import config_registry
from .. import pipeline_registry
from .._base import Base_Process, GRAY_IMAGE


NAME = "extract_mask_sam3"

_ANCHOR_MODES = ("box", "points", "mask", "none")


# ── 앵커(프롬프트) 변환 헬퍼 ──────────────────────────────────────────────────

def _mask_to_box(mask: GRAY_IMAGE) -> np.ndarray | None:
    """binary mask → SAM box 프롬프트 [x0, y0, x1, y1]."""
    _xs = np.argwhere(mask > 0)
    if _xs.size == 0:
        return None
    (_y0, _x0), (_y1, _x1) = _xs.min(0), _xs.max(0) + 1
    return np.array([_x0, _y0, _x1, _y1], dtype=np.float32)


def _mask_to_points(mask: GRAY_IMAGE, n: int) -> tuple[np.ndarray, np.ndarray] | None:
    """binary mask → 전경 point 프롬프트 (coords[N,2] xy, labels[N]=1).

    중심(centroid) 1점 + 전경 픽셀 균등 샘플 (n-1)점. 모두 positive(label=1).
    """
    _fg = np.argwhere(mask > 0)        # (K, 2) as (y, x)
    if _fg.size == 0:
        return None
    _cy, _cx = _fg.mean(0)
    _pts = [(_cx, _cy)]
    if n > 1 and len(_fg) > 1:
        _idx = np.linspace(0, len(_fg) - 1, num=min(n - 1, len(_fg)), dtype=int)
        _pts += [(_fg[i][1], _fg[i][0]) for i in _idx]
    _coords = np.array(_pts, dtype=np.float32)
    return _coords, np.ones(len(_coords), dtype=np.int32)


def _mask_to_lowres(mask: GRAY_IMAGE, lo: float = -8.0, hi: float = 8.0) -> np.ndarray:
    """binary mask → SAM mask_input 용 저해상도 logit (1, 256, 256)."""
    _small = cv2.resize(mask, (256, 256), interpolation=cv2.INTER_NEAREST)
    _logit = np.where(_small > 0, hi, lo).astype(np.float32)
    return _logit[None, ...]


# ── Config ────────────────────────────────────────────────────────────────────

@config_registry.Register_module(f"{NAME}_config")
@dataclass
class Extract_mask_sam3_config(Base_Config):
    """SAM3 마스크 추출 파라미터."""

    config_type: str = f"{NAME}_config"
    object_type: str = NAME

    checkpoint: str = field(default="", metadata={"ui": {
        "label": "SAM3 체크포인트 경로",
        "tip": "sam3 가중치(.pt) 경로",
    }})
    model_cfg: str = field(default="", metadata={"ui": {
        "label": "SAM3 모델 config",
        "tip": "build_sam3 에 넘길 모델 config 식별자/경로",
    }})
    device: str = field(default="cuda", metadata={"ui": {
        "label": "device",
        "tip": "cuda | cpu",
    }})
    anchor_mode: str = field(default="box", metadata={"ui": {
        "label": "앵커 변환 (box/points/mask/none)",
        "tip": "입력 mask 를 SAM 프롬프트로 변환하는 방식. none 이면 프롬프트 없이 실행",
    }})
    n_points: int = field(default=1, metadata={"ui": {
        "label": "point 앵커 개수",
        "tip": "anchor_mode=points 일 때 사용할 전경 point 수",
        "min": 1, "max": 16,
    }})
    min_contour_area: int = field(default=200, metadata={"ui": {
        "label": "객체 후보 최소 면적 (px²)",
        "tip": "이 면적 미만 컨투어는 노이즈로 제외",
        "min": 0, "max": 10000,
    }})


# ── Process ───────────────────────────────────────────────────────────────────

@pipeline_registry.Register_module(NAME)
@dataclass
class Extract_mask_sam3_process(Base_Process):
    """SAM3 로 단일 프레임에서 전경 객체 마스크를 추출한다.

    mask 입력이 있으면 anchor_mode 에 따라 시각 프롬프트로 변환해 사용한다.
    predictor 는 첫 Run 에서 1회 빌드해 인스턴스에 캐싱한다.
    """

    name:             str = NAME
    checkpoint:       str = ""
    model_cfg:        str = ""
    device:           str = "cuda"
    anchor_mode:      str = "box"
    n_points:         int = 1
    min_contour_area: int = 200

    # mask 는 선택적 앵커 입력 — 없으면 anchor_mode=none 처럼 동작.
    INPUTS:  ClassVar[tuple[str, ...]] = ("frame", "mask")
    OUTPUTS: ClassVar[tuple[str, ...]] = ("mask",)

    def __post_init__(self) -> None:
        if self.anchor_mode not in _ANCHOR_MODES:
            raise ValueError(
                f"anchor_mode 는 {_ANCHOR_MODES} 중 하나여야 함: {self.anchor_mode!r}")
        self._predictor: Any | None = None

    # ── 모델 (lazy, 1회) ──────────────────────────────────────────────────────

    def _Build_predictor(self) -> Any:
        """sam3 predictor 를 빌드한다. (sam3 레포 기준 심볼 확인 필요 지점)"""
        from sam3.build_sam import build_sam3            # noqa: PLC0415
        from sam3.sam3_image_predictor import SAM3ImagePredictor  # noqa: PLC0415

        _model = build_sam3(self.model_cfg, self.checkpoint, device=self.device)
        return SAM3ImagePredictor(_model)

    def _ensure_predictor(self) -> Any:
        if self._predictor is None:
            self._predictor = self._Build_predictor()
        return self._predictor

    # ── 프롬프트 구성 ─────────────────────────────────────────────────────────

    def _Build_prompt(self, mask: GRAY_IMAGE | None) -> dict[str, Any]:
        """anchor_mode + mask 로 predictor.predict kwargs 를 만든다."""
        if mask is None or self.anchor_mode == "none":
            return {}
        if self.anchor_mode == "box":
            _box = _mask_to_box(mask)
            return {"box": _box} if _box is not None else {}
        if self.anchor_mode == "points":
            _pts = _mask_to_points(mask, self.n_points)
            if _pts is None:
                return {}
            return {"point_coords": _pts[0], "point_labels": _pts[1]}
        # mask
        return {"mask_input": _mask_to_lowres(mask)}

    # ── Run ───────────────────────────────────────────────────────────────────

    def Run(
        self,
        frame: np.ndarray,
        mask:  GRAY_IMAGE | None = None,
        **kwargs,
    ) -> dict[str, np.ndarray]:
        """프레임을 SAM3 로 분할해 전경 마스크를 반환한다.

        Args:
            frame: BGR 이미지.
            mask:  선택적 앵커 마스크. anchor_mode 로 box/points/mask 프롬프트 변환.

        Returns:
            {"mask": 0/255 GRAY_IMAGE}. 분할 실패/유효 객체 없음이면 빈 dict.
        """
        _prompt = self._Build_prompt(mask)
        if not _prompt and self.anchor_mode != "none":
            return {}

        _predictor = self._ensure_predictor()
        _rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        _predictor.set_image(_rgb)

        # NOTE: predict 반환 형식은 sam3 기준 확인 필요. (masks, scores, logits) 가정.
        _masks, _scores, _ = _predictor.predict(multimask_output=False, **_prompt)
        if _masks is None or len(_masks) == 0:
            return {}

        _best = np.asarray(_masks[int(np.argmax(_scores))])
        _out = (_best > 0).astype(np.uint8) * np.uint8(255)

        if int((_out > 0).sum()) < self.min_contour_area:
            return {}
        return {"mask": _out}
