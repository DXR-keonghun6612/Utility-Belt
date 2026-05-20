# CHART 방법론

코드베이스 정적 분석 → 아키텍처 다이어그램 자동 생성 파이프라인의 설계 합의 문서.
(코드→다이어그램 변환의 *방법* 자체는 [`diagram_methodology.md`](diagram_methodology.md) 참고.)

---

## 1. 전체 구조

### 1.1 3계층

```
core       — 언어/백엔드 무관 뼈대 (IR, Graph, 직렬화, 무효화, 알고리즘)
parser     — 언어별 소스 → IR 변환
renderer   — 시각화 백엔드별 출력
```

### 1.2 5단계 파이프라인

```
[입력]   진입점(언어별) + --language 옵션
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

### 1.3 단위 변화

- 01·02: **파일별**
- 03·04·Renderer: **디렉토리별**
- 단위 변화 지점은 **02→03 한 곳**

### 1.4 핵심 invariants

- 노드 ID는 01에서 부여, 모든 단계를 관통
- abstraction은 03 통과 후가 최종 (02는 잠정)
- stereotype 어휘는 **Type 카테고리에만** 적용 (Callable / Data 카테고리는 메타필드만)
- 외부 클래스는 `origin: external`로 표시 (보정 영향 없음)
- 데이터는 단조적으로 풍부해짐 (단계가 진행될수록 정보 추가)

---

## 2. 중간 결과 저장

### 2.1 옵션

- `--debug` (기본값 `true`, 릴리즈 시 `false`로 전환)
- `--output-root <path>` (기본값 있음)

### 2.2 디렉토리 구조

```
{output_root}/
  debug/
    01_parser/{file_key}.yaml
    02_classifier/{file_key}.yaml
    03_linker/{dir}.yaml
    04_layout/{dir}.yaml
  result/
    {dir}.drawio
```

### 2.3 포맷

- yaml / json (확장자 기반 자동 직렬화, `python_toolbox` 활용)
- Data_Schema 상속으로 클래스 자동 직렬화
- 역직렬화 디스패치 키: yaml 본문의 `type` 필드 (클래스명)

---

## 3. 캐시 / 무효화

### 3.1 해시 알고리즘

`hashlib.blake2b(digest_size=16)` — 변경 감지 용도이므로 빠르고 가벼운 선택.

### 3.2 무효화 키

각 단계 yaml의 `meta`에 4종의 해시를 기록 → 자동 무효화 판정:

| 해시 | 의미 |
|------|------|
| `source_hash` | 자기 소스 파일 해시 |
| `dependency_hashes` | 의존 파일(C++의 transitive include / Python의 import) 각각의 해시 |
| `context_hash` | 언어별 빌드/실행 컨텍스트 (C++의 compile_flags, Python 버전 등) |
| `upstream_hash` | 직전 단계 출력 yaml의 해시 (단계 체이닝) |

### 3.3 재진입 규칙

- 단계별로 yaml 존재 여부 + 해시 일치 → 그대로 사용
- 어느 하나라도 불일치 → 그 단계부터 재실행 (이후 단계 자동 재실행)
- 의심 시 해당 단계 폴더 삭제로 강제 재실행

---

## 4. 단계별 책임과 스키마

### 4.1 [01_parser] — IR 추출

**책임**
- AST → 언어별 IR (`Class_Info`, `Method_Info`, `Module_Info`, 언어 확장)
- 노드 ID 부여
- 분류는 하지 않음 (`abstraction = concrete` 기본값, `traits = []`)
- 가능한 모든 메타데이터 추출 — 버리는 건 이후 단계 책임

**노드 ID 규칙**

```
{file_key}::{namespace_path}::{name}
```
- C++: `src/core/widget.cpp::core::Widget`
- Python: `src/core/widget.py::Widget`

**yaml 예시**

```yaml
# debug/01_parser/src__core__widget.cpp.yaml
meta:
  schema_version: 1
  language: cxx
  source_path: /abs/path/src/core/widget.cpp
  source_hash: <blake2b-16>
  dependency_hashes:
    /abs/path/src/core/widget.h: <hash>
    /abs/path/src/core/base.h:   <hash>
  context_hash: <hash of compile_flags + language version>

body:
  type: Module_Info
  name: widget.cpp
  file_path: /abs/path/src/core/widget.cpp
  imported_symbols: {...}
  functions: [...]
  classes:
    - type: CXX_Class_Info
      id: src/core/widget.cpp::core::Widget
      name: Widget
      kind: class
      namespace_path: core
      template_params: []
      origin: internal
      abstraction: concrete       # 기본값 — 02에서 갱신
      traits: []                  # 기본값 — 02에서 채움
      bases: ["core::BaseWidget"]
      attributes: [...]
      methods: [...]
      source_line: 42
```

---

### 4.2 [02_classifier] — 분류 부여

**책임**
- Type 카테고리(class/struct/union)에 한해 `abstraction` + `traits` 부여
- Callable / Data 카테고리는 통과 (변경 없음)
- 자기 메서드만 본 **잠정 abstraction** 부여 (최종은 03 책임)

**분류 어휘 (두 축 분리)**

| 필드 | 타입 | 카디널리티 | 값 |
|------|------|----|----|
| `abstraction` | `Literal["interface","abstract","concrete"]` | **정확히 1개** | 추상화 수준 |
| `traits` | `set[Literal["template","macro","data"]]` | **0개 이상** | 구조적 특성 |

`concrete`는 기본값으로 항상 부여. 빈 값은 없음(invariant).
시각화에서는 `concrete`만 있는 경우 마커를 표시하지 않음(UML 관례).

**자동 분류 규칙**

| 조건 | 부여 |
|------|------|
| 메서드 ≥ 1개 AND 모든 메서드가 pure virtual | `abstraction = interface` |
| 일부 메서드만 pure virtual (1 ≤ pure < 전체) | `abstraction = abstract` |
| 위 둘 다 아님 (메서드 0개 포함) | `abstraction = concrete` |
| `template_params` 비어있지 않음 | `traits += template` |
| 매크로 expansion으로 정의됨 + `--macro-classes` 매칭 | `traits += macro` |
| ctor/dtor 외 사용자 정의 메서드 0개 | `traits += data` |

**yaml 예시**

```yaml
# debug/02_classifier/src__core__widget.cpp.yaml
meta:
  schema_version: 1
  upstream_hash: <01 출력 yaml의 해시>
  abstraction_finalized: false       # 03 통과 후 true로 갱신

body:
  type: Module_Info
  ...
  classes:
    - type: CXX_Class_Info
      id: src/core/widget.cpp::core::Widget
      name: Widget
      abstraction: abstract           # 자기 메서드만 본 잠정값
      traits: [template]
      ...
```

---

### 4.3 [03_linker] — 관계 해석 + abstraction 보정

**책임 (3 phase)**

```
phase 1: build_inheritance_graph
  - base 엣지 잠정 'inheritance'로 등록
  - 상속 인덱스 구축
phase 2: refine_abstraction
  - 상속 체인 따라 abstraction 보정
  - 순환 상속 가드 (visited set)
  - base들의 pure virtual 합집합 - 자식 override 제거 → 남으면 abstract
phase 3: build_other_edges
  - composition / aggregation / association / dependency / include 생성
  - base가 interface인 inheritance를 realization으로 갱신
```

**엣지 종류와 판정**

| 엣지 | 판정 기준 | UML 표기 |
|------|----------|----------|
| `inheritance` | `: public Base`이고 base가 interface 아님 | hollow triangle (실선) |
| `realization` | `: public Base`이고 base가 `abstraction == interface` | hollow triangle (점선) |
| `composition` | 멤버 변수: value, `unique_ptr<T>`, 컨테이너 등 | filled diamond |
| `aggregation` | 멤버 변수: `shared_ptr<T>` | hollow diamond |
| `association` | 멤버 변수: raw pointer, reference, `weak_ptr<T>` | 실선 |
| `dependency` | 메서드 파라미터·반환 타입에 등장 | dashed open arrow |
| `include` | `#include` directive | dashed open arrow (회색) |

**제거된 엣지**: `friend` (현대 C++ 회피 권장), `call` (UML 클래스 다이어그램 영역 아님)

**다중 엣지 정책**

- 같은 노드쌍에 여러 엣지 허용 (데이터에 모두 기록)
- 시각화에서 우선순위 적용:
  `inheritance > realization > composition > aggregation > association > dependency > include`

**Name Resolution (C++ unqualified lookup의 단순 흉내)**

```
resolve(name, source_namespace):
  1) name이 fully qualified (`::` 포함) → 그대로 lookup
  2) source_namespace에서 가까운 순서로 시도 (자기 → 부모 → ... → global)
  3) 가장 먼저 매칭되는 후보 채택
  4) 못 찾으면 → external stub 생성
  5) 다중 후보 → meta에 warning + 가장 가까운 namespace 선택
```

가능하면 libclang이 제공하는 fully qualified name을 01에서 그대로 받아오기.

**외부 클래스 처리**
- `origin: external`인 빈 `Class_Info` stub 생성
- 보정 알고리즘에 영향 없음 (자기 정보로만 본 abstraction 유지)
- Renderer가 회색 표시 / 옵션으로 숨김

**yaml 예시**

```yaml
# debug/03_linker/src__core.yaml
meta:
  schema_version: 1
  upstream_hashes:
    src/core/widget.cpp: <02 해시>
    src/core/base.h:     <02 해시>
  abstraction_finalized: true        # 03 통과 후 갱신

body:
  type: Graph_Model
  nodes:
    - id: src/core/widget.cpp::core::Widget
      type: Node_Info
      name: Widget
      category: type                 # type | callable | data
      abstraction: abstract          # 보정된 최종값
      traits: [template]
      origin: internal
      ir_source: src__core__widget.cpp   # 상세는 02 yaml 참조
    - id: stub::std::exception
      type: Node_Info
      name: exception
      category: type
      abstraction: concrete
      traits: []
      origin: external
  edges:
    - source_id: src/core/widget.cpp::core::Widget
      target_id: src/core/base.h::core::BaseWidget
      edge_type: realization
    - source_id: src/core/widget.cpp::core::Widget
      target_id: stub::std::exception
      edge_type: inheritance
  namespaces:
    core: [src/core/widget.cpp::core::Widget, ...]
```

---

### 4.4 [04_layout] — 추상 좌표

**책임**
- 각 노드에 `(layer, wing, col)` 부여
- 같은 layer 내 col 순서를 교차 최소화로 결정 (barycenter heuristic 2회 반복)
- namespace 그룹화 정보 부여

**좌표 의미**

| 좌표 | 축 | 값 | 결정 기준 |
|------|----|----|----------|
| `layer` | y축 (세로) | 0이 최상단, 숫자 커질수록 아래 | abstraction + traits |
| `wing` | x축 영역 | left / center / right | traits ∋ macro, origin |
| `col` | wing 내 가로 순서 | 0, 1, 2, ... | 교차 최소화 휴리스틱 |

**layer / wing 자동 규칙**

| 조건 | layer | wing |
|------|-------|------|
| `abstraction == interface` | 0 | center |
| `abstraction == abstract` | 1 | center |
| `abstraction == concrete`, traits 없음 | 2 | center |
| `traits ∋ data` | 3 | center |
| `traits ∋ macro` | (원래 layer 유지) | right |
| `origin == external` | (원래 layer 유지) | left |

**사용자 hint (자리만, 동작 미구현)**
- CLI 옵션 자리만 비워둠: `--layer-hint`, `--wing-hint`, `--hide`
- 내부 hint 적용 함수가 별도 분리 → 추후 body만 채우면 동작

**04가 안 하는 일**
- 노드 크기 계산 (renderer 책임)
- 엣지 라우팅 (renderer 책임)
- 실제 픽셀 좌표 변환 (drawio renderer 책임)

**yaml 예시**

```yaml
# debug/04_layout/src__core.yaml
meta:
  schema_version: 1
  upstream_hash: <03 출력 해시>

body:
  type: Positioned_Graph
  nodes:
    - id: src/core/widget.cpp::core::Widget
      name: Widget
      abstraction: concrete
      traits: [template]
      origin: internal
      layer: 2
      wing: center
      col: 1
      namespace_group: core
  edges: [...]                       # 03과 동일 (라우팅 정보 없음)
  namespace_groups:
    core: [...]
```

---

### 4.5 [Renderer] — 백엔드별 출력

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

---

## 5. 데이터 모델

### 5.1 IR Layer (`core/`)

- 공통: `Arg_Info`, `Method_Info`, `Class_Info`, `Module_Info`
- 언어 확장: `CXX_Class_Info`, `CXX_Method_Info`, `Translation_Unit_Info` 등
- 모두 `Data_Schema` 상속

### 5.2 Graph Layer (`core/`)

- `Node_Info` — Graph 노드 래퍼 (id, name, category, abstraction, traits, origin)
- `Edge_Info` — 엣지 (source_id, target_id, edge_type)
- `Graph_Model` — 03 출력
- `Positioned_Graph` — 04 출력 (Node_Info에 layer/wing/col 추가)

### 5.3 검출 대상 카테고리

| 카테고리 | 포함 | stereotype 적용 |
|---------|------|----------------|
| **Type** | class, struct, union | ✓ (abstraction + traits) |
| **Callable** | function, method | ✗ (메타필드만) |
| **Data** | field, variable | ✗ (메타필드만) |

### 5.4 `Module_Info.origin`

기존 `Module_Info.stereotype: Literal["«local»","«external»"]`를
`Module_Info.origin: Literal["internal","external"]`로 통일.
클래스 분류 stereotype과 의미 혼동 제거.

---

## 6. 다언어 지원

### 6.1 진입점

| 언어 | 진입점 | CLI |
|------|--------|-----|
| C/C++ | `compile_commands.json` | `cchart` |
| Python | 디렉토리 경로 | `pychart` |

언어별 CLI 유지 + `--language` 옵션을 명시적 오버라이드/안전장치로 제공.

### 6.2 Parser Protocol (공통 인터페이스)

모든 언어 parser는 동일 시그니처를 따름:

```
Parser.Parse_file(path) → (IR, dependency_files, context_hash)
```

- C++ 구현: libclang transitive include + compile_flags 해시
- Python 구현: AST import 분석 + Python 버전 해시
- 무효화 로직은 core에 한 번만 구현 → 언어별 차이는 Parser가 흡수

---

## 7. 외부 의존성 정책

### 사용
- **libclang** — C++ AST 추출 (대체 불가)
- **python_toolbox** — Data_Schema, Registry, 직렬화

### 사용하지 않음 (직접 구현)
- **networkx** 등 외부 그래프 라이브러리
  - 필요한 알고리즘(위상정렬, DFS, 사이클 감지)은 `core/graph_ops.py`에 직접 구현 (~100줄 예상)
- **graphviz / grandalf** 자동 레이아웃
  - 의미론적 휴리스틱이 도메인 지식 기반이므로 자체 구현(`core/layout/semantic.py`)

이유: 의존성 적을수록 배포·유지보수 편함. 우리 그래프 크기(디렉토리당 수십~수백 노드)에서는 직접 구현으로 충분.

---

## 8. 디렉토리 구조 (목표)

```
core/
  definition.py        # IR (Class_Info, Method_Info, Module_Info, ...)
  graph.py             # Graph_Model, Edge_Info, Node_Info, Positioned_Graph
  graph_ops.py         # 위상정렬, DFS, 사이클 감지 등 (직접 구현)
  registry.py          # 전역 심볼 테이블 베이스
  hashing.py           # 4종 해시 계산 + 무효화 판정
  serialization.py     # Data_Schema 기반 yaml/json 자동 직렬화
  layout/
    semantic.py        # 의미론적 layer/wing/col 부여
    crossing.py        # barycenter 교차 최소화

parser/                # 언어별 parser
  protocol.py          # Parser Protocol 인터페이스
  cxx/                 # C/C++
    extractor.py       # AST → IR
    classifier.py      # 02_classifier 로직 (C++ 한정)
    linker.py          # 03_linker 로직 (C++ 한정)
  python/              # Python
    extractor.py
    classifier.py
    linker.py

render/                # 시각화 백엔드 (3계층의 renderer)
  drawio/
  mermaid/
  plantuml/

# 진입점 (CLI)
cchart/__init__.py     # C++ 파이프라인 facade
pychart/__init__.py    # Python 파이프라인 facade
```

---

## 9. 주요 결정 요약

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
| 다언어 | 언어별 CLI + `--language` 명시 + 공통 Parser Protocol |
