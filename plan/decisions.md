# 주요 결정 요약

| 영역 | 결정 |
|------|------|
| 계층 | core / parser / renderer 3계층 |
| 파이프라인 | 5단계, 단위 변화는 02→03 한 곳 |
| stereotype | abstraction(단일) + traits(set) 두 필드 분리, Type 카테고리에만 |
| 외부 클래스 | `origin: external`로 단순 표시, 보정 영향 없음 |
| abstraction 보정 | 03이 phase 2에서 수행 (관계 해석과 같은 단계) |
| 엣지 분류 | UML 4종(composition/aggregation/association/dependency) + inheritance/realization/include |
| 제거 | `friend`, `call` 엣지 |
| 다중 엣지 | 데이터에 다 기록, 시각화에서 우선순위 |
| 그래프 표현 | 인접 리스트 (행렬 안 씀) |
| 좌표 | 추상 단위 (layer/wing/col), 픽셀 변환은 renderer |
| 외부 라이브러리 | libclang + python_toolbox만, 그래프/레이아웃은 직접 구현 |
| 캐시 | yaml + blake2b 해시 4종(소스/의존/컨텍스트/단계) 체이닝 |
| 다언어 | 단일 CLI `code-chart` + `--language`가 언어 결정의 유일 기준 + 공통 Parser Protocol |
| 플로우 트랙 | 구조 트랙과 분리, 01_parser 공유 줄기, 01 직후 분기 |
| 간접 호출 해석 | 사용 측 앵커링 — 바인딩 환경, 전프로그램 points-to 안 함 |
| 시퀀스 모델 | `Trace_Model` 별도 (호출 트리), `Graph_Model`과 분리 |
