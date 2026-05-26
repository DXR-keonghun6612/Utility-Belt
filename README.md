# CHART — Code Hierarchy & Architecture Rendering Tool

코드베이스를 정적 분석하여 draw.io 아키텍처 다이어그램을 자동 생성하는 CLI 도구.

## 설계 이념

### 언어 독립 IR (Intermediate Representation)

모든 언어 백엔드는 동일한 IR로 수렴한다. `Class_Info`, `Method_Info`, `Module_Info`로 구성된 공통 데이터 모델이 파서와 렌더러 사이를 잇는 계약이다. 새 언어 지원은 이 IR을 채우는 파서를 추가하는 것으로 완결된다.

### 5단계 파이프라인

```
01_parser  →  02_classifier  →  03_linker  →  04_layout  →  Renderer
파일별         파일별            디렉토리별     디렉토리별     디렉토리별
```

- **01_parser**: AST → 언어별 IR, 노드 ID 부여, 무효화 메타(해시) 기록
- **02_classifier**: Type 카테고리에 `abstraction` + `traits` 부여 (잠정값)
- **03_linker**: 관계 해석 + 상속 체인 따라 `abstraction` 최종 보정
- **04_layout**: 추상 좌표(`layer / wing / col`) 부여
- **Renderer**: 백엔드별 출력 (drawio / mermaid / plantuml)

단계 사이는 yaml 캐시 + blake2b 해시 체이닝으로 자동 무효화. 어느 단계라도 입력이 바뀌면 이후 단계가 자동 재실행된다.

### 타입화 엣지 (Typed Edges)

관계선은 의미 없는 화살표가 아니다. UML 표기법에 따라 7종의 엣지 타입 중 하나를 부여한다:

| 엣지 | 의미 |
|------|------|
| `inheritance` | 일반 상속 (base가 interface 아님) |
| `realization` | 인터페이스 구현 (base의 `abstraction == interface`) |
| `composition` | 강한 소유 (value, `unique_ptr`, 컨테이너) |
| `aggregation` | 약한 소유 (`shared_ptr`) |
| `association` | 참조 보유 (raw pointer, reference, `weak_ptr`) |
| `dependency` | 일시적 사용 (메서드 시그니처 등장) |
| `include` | `#include` (C/C++) |

### 디렉토리 단위 출력

코드베이스를 하나의 거대한 다이어그램으로 표현하는 대신, 디렉토리 단위로 분할하여 각각 `.drawio` 파일로 저장한다. `--root`와 `--namespace` 필터로 분석 범위를 좁혀 노이즈를 줄일 수 있다.

## 아키텍처

3계층 구조 (`core` / `parser` / `render`).

```text
[parser/{lang}]   →   [core]            →   [render/{backend}]
 extractor.py          definition.py         drawio/
 classifier.py         graph.py              mermaid/
 linker.py             layout/               plantuml/
                       hashing.py
                       serialization.py
```

| 계층 | 역할 | 핵심 모듈 |
|------|------|-----------|
| Parser (언어별) | AST 탐색 → IR 채움 | `parser/{lang}/extractor.py` |
| Parser (언어별) | 분류 부여 | `parser/{lang}/classifier.py` |
| Parser (언어별) | 관계 해석 | `parser/{lang}/linker.py` |
| Core | 전역 심볼 테이블 | `core/registry.py` |
| Core | 추상 좌표 배치 | `core/layout/` |
| Core | 해시 / 무효화 | `core/hashing.py` |
| Renderer (백엔드별) | 좌표 → 출력 | `render/{backend}/builder.py` |

## 지원 언어

| 언어 | CLI | 진입점 | 상태 |
|------|-----|--------|------|
| C/C++ | `cchart` | `compile_commands.json` | 지원 |
| Python | `pychart` | 디렉토리 경로 | 개발 중 |

## 설치

```bash
make install
```

## 빠른 시작

```bash
# C/C++ 프로젝트 분석
cchart build/compile_commands.json

# 루트 디렉토리 필터 + 상세 모드
cchart build/compile_commands.json --root src/ -d
```

## 설계 문서

- [plan/](plan/README.md) — 단계별 책임, 스키마, 캐시·무효화, 다언어 지원 등 설계 합의 문서 모음
- [render/drawio/README.md](render/drawio/README.md) — Draw.io 백엔드의 추상 좌표 → 픽셀 변환 및 시각 매핑
