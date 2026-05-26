# Renderer — 백엔드별 출력

**책임 매트릭스**

| 백엔드 | layer/wing/col 사용 | 노드 크기 | 엣지 라우팅 |
|--------|-------------------|---------|------------|
| drawio | → 픽셀 변환 | 멤버 수 기반 동적 계산 | orthogonalEdgeStyle 자동 |
| mermaid | layer로 subgraph 그룹화 | 자동 | 자동 |
| plantuml | layer로 together 블록 | 자동 | 자동 |

**다중 엣지 시각화**
- 데이터에 다 있지만 화면에는 우선순위 hierarchy로 한 개만 표시 (옵션으로 다 표시 가능)

**외부 클래스**
- `origin == external` → 회색 흐림 처리 / 옵션으로 숨김
