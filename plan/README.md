# CHART 설계 문서

코드베이스 정적 분석 → 아키텍처 다이어그램 자동 생성 파이프라인의 설계 합의 문서.
항목별로 분리되어 있으며, 아래 순서로 읽는 것을 권장한다.

## 공통 기반

- [overview.md](overview.md) — 3계층 구조, 5단계 파이프라인, 핵심 invariants
- [caching.md](caching.md) — 중간 결과 저장, blake2b 4종 해시 캐시/무효화
- [data-model.md](data-model.md) — IR / Graph / Trace 데이터 레이어
- [multilang.md](multilang.md) — 다언어 지원, Parser Protocol
- [dependencies.md](dependencies.md) — 외부 의존성 정책
- [directory.md](directory.md) — 목표 디렉토리 구조
- [decisions.md](decisions.md) — 주요 결정 요약

## 구조 트랙 (클래스 다이어그램)

- [parser.md](parser.md) — 01_parser, IR 추출
- [classifier.md](classifier.md) — 02_classifier, 분류 부여
- [linker.md](linker.md) — 03_linker, 관계 해석 + abstraction 보정
- [layout.md](layout.md) — 04_layout, 추상 좌표
- [renderer.md](renderer.md) — Renderer, 백엔드별 출력

## 플로우 트랙 (시퀀스 다이어그램)

- [flow-track.md](flow-track.md) — call-flow 추적, 사용 측 앵커링
- [trace-model.md](trace-model.md) — Trace_Model 데이터 모델
