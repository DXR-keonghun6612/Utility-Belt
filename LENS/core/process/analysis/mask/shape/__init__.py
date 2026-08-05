"""shape — **legacy** 폴더 경로 형상 분석 (UMAP 임베딩 + HDBSCAN 클러스터).

**이 갈래는 걷는 중이다** — `core/analysis` 가 쓰는 검증 경로와 계약이 다르고(폴더 glob vs store,
`ShapeAnalysis` vs 기록지), 판정 근거로 UMAP·HDBSCAN 을 쓴다(`core/analysis/README.md` 원칙 1 이
transductive 라 배제한 방식이다). 소비처는 `gui/meta_page/sample/_tab.py` 하나뿐이고,
**sample 갈래 제거와 함께 이 폴더째 사라진다**(→ 루트 `TODO.md`).

그때까지 자기완결로 둔다 — `core/analysis` 쪽을 참조하지 않는다(그쪽은 이미 UMAP 을 걷었다).
"""

from .analyze import analyze
from ._result import ShapeAnalysis

__all__ = ["analyze", "ShapeAnalysis"]
