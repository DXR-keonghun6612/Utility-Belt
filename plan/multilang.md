# 다언어 지원

## 언어 특정 / 언어 무관 경계

파이프라인의 각 단계는 **언어 특정(language-specific)** 이거나 **언어 무관
(language-agnostic)** 둘 중 하나다. 핵심 원리:

> 언어 특정 단계가 언어 무관 모델을 출력하는 지점이 **seam**이다.
> 그 지점 이후의 단계는 언어를 전혀 모른다.

### 구조 트랙

| 단계 | 구분 | 위치 | 언어차 / 비고 |
|------|------|------|--------------|
| 01_parser | 언어 특정 | `parser/{lang}/extractor.py` | AST가 언어별 — libclang vs Python `ast` |
| 02_classifier | 언어 특정 | `parser/{lang}/classifier.py` | abstraction 판정이 다름 — C++ pure virtual vs Python ABC/`@abstractmethod` |
| 03_linker | 언어 특정 | `parser/{lang}/linker.py` + `resolve.py` | name resolution·관계 휴리스틱이 다름 — C++ unqualified lookup vs Python import |
| 04_layout | 언어 무관 | `core/layout/` | `Graph_Model`만 입력 |
| Renderer | 언어 무관 | `render/` | `Positioned_Graph`만 입력 |

**seam = 03_linker.** 03은 언어 확장 IR(`CXX_Class_Info` 등)을 입력받아 언어 무관
`Graph_Model`(`Node_Info`/`Edge_Info`)을 출력한다. 이 출력 이후 04·Renderer는 언어를 모른다.

### 플로우 트랙

| 단계 | 구분 | 위치 | 언어차 / 비고 |
|------|------|------|--------------|
| 01_parser (+call-site) | 언어 특정 | `parser/{lang}/extractor.py` | 구조 트랙과 공유 줄기 |
| resolve | 언어 특정 | `parser/{lang}/resolve.py` | 구조 트랙 03_linker와 공용 모듈 |
| trace | 언어 특정 | `parser/{lang}/tracer.py` | call-site 해석·바인딩 메커니즘이 언어별 |
| sequence-layout | 언어 무관 | `core/layout/` | `Trace_Model`만 입력 |
| sequence renderer | 언어 무관 | `render/` | `Positioned_Trace`만 입력 |

**seam = trace.** trace는 언어 특정 IR/call-site를 입력받아 언어 무관 `Trace_Model`을
출력한다. 이 출력 이후 sequence-layout·renderer는 언어를 모른다.

### 경계의 한 군데 회색지대

Renderer가 멤버(속성·메서드) 상세를 그릴 때 `Node_Info.ir_source`로 02 IR을 역참조한다 —
언어 무관 코드가 언어 확장 IR에 닿는 **유일한 지점**. 멤버 표시 문자열을 01_parser에서
언어 중립 형태로 정규화해 두면 이 접점이 사라진다.

## IR 레이어 이중 구조

- **언어 무관 베이스** — `Class_Info` / `Method_Info` / `Module_Info` (`core/definition.py`)
- **언어 확장** — `CXX_Class_Info` / `CXX_Method_Info` / `Translation_Unit_Info` 등
  (`parser/cxx/`; Python은 별도 확장)

01·02는 언어 확장 IR을 다루고, 03_linker(또는 trace)가 이를 언어 무관 모델로 사상한다.
이것이 위 seam의 데이터 측 표현이다.

## 진입점

CLI는 **단일 진입점 `code-chart`** 하나다. 언어는 `--language` 옵션이 **유일한 기준**으로
결정한다 — CLI 이름이나 경로 형태로 자동 추론하지 않으며, 필수 옵션이다.

```text
code-chart <path> --language cxx|python
```

| `--language` | `<path>` 해석 | parser 디스패치 |
|------|--------|-----|
| `cxx` | `compile_commands.json` 경로 | `parser/cxx/` |
| `python` | 소스 디렉토리 경로 | `parser/python/` |

## Parser Protocol (언어 특정 단계의 공통 인터페이스)

언어 특정 단계 중 진입점인 01_parser는 동일 시그니처를 따른다:

```text
Parser.Parse_file(path) → (IR, dependency_files, context_hash)
```

- C++ 구현: libclang transitive include + compile_flags 해시
- Python 구현: AST import 분석 + Python 버전 해시
- 무효화 로직은 `core`에 한 번만 구현 → 언어별 차이는 Parser가 흡수

02·03·resolve·trace도 언어별 구현이지만 입력이 IR로 정규화돼 있어, core의 단계
오케스트레이션·캐시 로직은 언어를 모른 채 동작한다.
