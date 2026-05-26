# 전체 구조

코드베이스 정적 분석 → 아키텍처 다이어그램 자동 생성 파이프라인의 설계.
인덱스는 [README.md](README.md) 참고.

## 3계층

```
core       — 언어/백엔드 무관 뼈대 (IR, Graph, 직렬화, 무효화, 알고리즘)
parser     — 언어별 소스 → IR 변환
renderer   — 시각화 백엔드별 출력
```

## 5단계 파이프라인

```
[입력]   소스 경로 + --language 옵션 (언어 결정의 유일 기준)
   ↓
[01_parser]      파일별 — AST → IR, 노드 ID 부여, 무효화 메타
   ↓
[02_classifier]  파일별 — abstraction(잠정) + traits 부여
   ↓
[03_linker]      디렉토리별 — 관계 해석 + abstraction 최종 보정
   ↓
[04_layout]      디렉토리별 — 추상 좌표(layer/wing/col) 부여
   ↓
[Renderer]       디렉토리별 — drawio / mermaid / plantuml
```

이는 **구조 트랙**(클래스 다이어그램) 파이프라인이다. 별도의 **플로우 트랙**(시퀀스
다이어그램)이 01_parser를 공유 줄기로 분기한다 — [flow-track.md](flow-track.md) 참고.

## 단위 변화

- 01·02: **파일별**
- 03·04·Renderer: **디렉토리별**
- 단위 변화 지점은 **02→03 한 곳**

## 핵심 invariants

- 노드 ID는 01에서 부여, 모든 단계를 관통
- abstraction은 03 통과 후가 최종 (02는 잠정)
- stereotype 어휘는 **Type 카테고리에만** 적용 (Callable / Data 카테고리는 메타필드만)
- 외부 클래스는 `origin: external`로 표시 (보정 영향 없음)
- 데이터는 단조적으로 풍부해짐 (단계가 진행될수록 정보 추가)
