"""mask.shape — (r, θ) centroid-극좌표가 편한 형상 특징 + 데이터셋 임베딩 분석.

특징 추출은 **학습이 쓰는 것과 같은 모듈**이다
(``torch_toolbox.modules.transform.mask.geometry.Geometry_Embedding``). 예전에는 이 폴더에
numpy 사본(``align.py`` · ``polar.py`` · ``features.py``)이 있었고 학습 쪽과 갈라져 있었다
— ``fill_holes`` 로 구멍을 메워 inner 계열 70차원이 죽은 채였다. 사본은 걷어냈다.

per-mask:
  register   — register_rotation: reference 대비 잔여 회전을 profile shift 로 미세 정합(ICP-등가).
               입력 프로파일은 ``Geometry_Embedding.Forward_with_aux`` 의 ``r_outer`` 가 낸다.

데이터셋 단계(분석 패키지 공유 관례 analyze/format_report/build_figure):
  batch      — process_masks: 폴더 mask 들 → feature 행렬
  embed      — UMAP 임베딩 + HDBSCAN 클러스터 (무거운 deps 는 lazy import)
  analyze    — analyze: 폴더 → ShapeAnalysis
"""

from .register import best_shift, apply_shift, shift_to_angle, register_rotation
from .batch import process_masks, iter_masks, load_mask, to_canvas, feature_names
from .analyze import analyze
from .report import format_report
from .visualize import build_figure
from ._result import ShapeAnalysis

__all__ = [
    # per-mask
    "best_shift", "apply_shift", "shift_to_angle", "register_rotation",
    # dataset-level
    "process_masks", "iter_masks", "load_mask", "to_canvas", "feature_names",
    "analyze", "format_report", "build_figure", "ShapeAnalysis",
]
