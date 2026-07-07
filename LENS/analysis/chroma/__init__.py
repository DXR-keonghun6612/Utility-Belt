"""chroma — 배경 크로마 누산 히스토그램에 대한 분석 (데이터 타입: 누산 히스토그램).

``for_save_acc.yaml`` 류로 저장한 픽셀별 누산본(``c0_acc (H,W,B0)`` / ``c1_acc (H,W,B1)``)에서
배경 색의 **공간 의존성**을 진단해, 전역 vs 픽셀별(vs coarse-grid) 배경모델 결정을 정량화한다.

공유 관례 — 모든 데이터 타입 분석 패키지는 다음 3개를 노출해 CLI/GUI가 균일하게 바인딩한다:

    analyze(...) -> Result        # 순수 계산
    format_report(result) -> str  # 텍스트 표현
    build_figure(result) -> Figure  # 시각화 (저장·표시는 호출자)

CLI: ``python -m LENS.analysis.chroma --c0-acc ... --c1-acc ... --space hsv``
"""

from ._result import ChromaDiag
from .analyze import analyze
from .report import format_report, recommend
from .visualize import build_figure

__all__ = ["ChromaDiag", "analyze", "format_report", "recommend", "build_figure"]
