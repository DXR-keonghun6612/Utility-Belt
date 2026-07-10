"""analysis — 종류2 연산: 데이터셋/집계 레벨 분석 (``Analysis`` 계약: analyze/report/figure).

스트리밍 ``Base_Process``(→ ``stream``)와 달리 store/배열을 통째로 받아 순수 계산 → report·figure 를
낸다. Verify 스테이지가 소비한다. 도메인 수학은 ``stream``·``func`` 과 공유(chroma stats·polar 등).

무거운 하위 패키지(chroma=matplotlib, mask.shape=umap/hdbscan)는 지연 import 로 격리 — 여기선
가벼운 계약/레지스트리만 재노출하고, 도메인 패키지는 소비 시점에 직접 import 한다.
"""

from ._base import Analysis, ANALYSIS_REGISTRY, Get, Available, Run, present

__all__ = ["Analysis", "ANALYSIS_REGISTRY", "Get", "Available", "Run", "present"]
