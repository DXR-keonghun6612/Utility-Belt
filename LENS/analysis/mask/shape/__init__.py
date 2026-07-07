"""mask.shape — (r, θ) centroid-극좌표가 편한 형상 특징 + 데이터셋 임베딩 분석.

**정렬된 mask**(``mask.align.align_mask`` 결과)를 전제로 한다.

per-mask 파이프라인:
  polar      — mask_to_polar: mask → (r_outer, r_inner) radial profile
  register   — register_rotation: reference 대비 잔여 회전을 profile shift 로 미세 정합(ICP-등가)
  features   — extract_shape_features: 프로파일 통계 + thickness + Fourier descriptor → 특징 벡터

데이터셋 단계(분석 패키지 공유 관례 analyze/format_report/build_figure):
  batch      — process_masks: 폴더 mask 들 → feature 행렬
  embed      — UMAP 임베딩 + HDBSCAN 클러스터 (무거운 deps 는 lazy import)
  analyze    — analyze: 폴더 → ShapeAnalysis
"""

from .polar import mask_to_polar, polar_lut, fill_circular_nan
from .register import best_shift, apply_shift, shift_to_angle, register_rotation
from .features import extract_shape_features, ShapeResult, profile_stats, fourier_descriptor
from .batch import process_masks, iter_masks, load_mask
from .analyze import analyze
from .report import format_report
from .visualize import build_figure
from ._result import ShapeAnalysis

__all__ = [
    # per-mask
    "mask_to_polar", "polar_lut", "fill_circular_nan",
    "best_shift", "apply_shift", "shift_to_angle", "register_rotation",
    "extract_shape_features", "ShapeResult", "profile_stats", "fourier_descriptor",
    # dataset-level
    "process_masks", "iter_masks", "load_mask",
    "analyze", "format_report", "build_figure", "ShapeAnalysis",
]
