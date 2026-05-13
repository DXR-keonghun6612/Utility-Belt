# CHART — Code Hierarchy & Architecture Rendering Tool

코드베이스를 정적 분석하여 draw.io 아키텍처 다이어그램을 자동 생성하는 CLI 도구.

## 설계 이념

### 언어 독립 IR (Intermediate Representation)

모든 언어 백엔드는 동일한 IR로 수렴한다. `Class_Info`, `Method_Info`, `Module_Info`로 구성된 공통 데이터 모델이 파서와 렌더러 사이를 잇는 계약이다. 새 언어 지원은 이 IR을 채우는 파서를 추가하는 것으로 완결된다.

### 2-Pass 파이프라인

- **Pass 1 — Parse**: 각 파일을 독립적으로 파싱하여 전역 심볼 테이블에 등록
- **Pass 2 — Link**: 심볼 테이블 전체를 순회하며 의존성 관계를 해석하고 `Graph_Model`을 생성

전역 심볼 테이블 기준으로 링킹하므로 파일 처리 순서에 영향받지 않는다.

### 타입화 엣지 (Typed Edges)

관계선은 의미 없는 화살표가 아니다. `inheritance`, `realization`, `composition`, `dependency`, `call`, `include`, `friend` 중 하나의 엣지 타입을 부여하고, 렌더러가 UML 표기법에 따라 시각화한다.

### 디렉토리 단위 출력

코드베이스를 하나의 거대한 다이어그램으로 표현하는 대신, 디렉토리 단위로 분할하여 각각 `.drawio` 파일로 저장한다. `--root`와 `--namespace` 필터로 분석 범위를 좁혀 노이즈를 줄일 수 있다.

## 아키텍처

```text
[언어별 파서]  →  [IR 레이어]       →  [Graph 레이어]  →  [Draw.io 렌더러]
 cchart /          core/definition      core/graph          core/form/drawio
 pychart           Class_Info           Graph_Model          Graph_Builder
                   Module_Info          Edge_Info            XML 직렬화
                   Method_Info
```

| 계층 | 역할 | 핵심 모듈 |
|------|------|-----------|
| Parser | AST 탐색 → IR 채움 | `{lang}/parser/extractor.py` |
| Registry | 전역 심볼 테이블 | `core/registry.py` |
| Linker | IR → 의존성 Graph | `{lang}/parser/linker.py` |
| Renderer | Graph → draw.io XML | `core/form/drawio/builder.py` |

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

자세한 예제는 [COOKBOOK.md](COOKBOOK.md)를 참고.
