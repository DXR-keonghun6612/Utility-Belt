# TODO

[plan/](plan/README.md) 설계 문서에 따른 마이그레이션 진행 체크리스트.

---

## 진행 중 — C/C++ 백엔드 마이그레이션 (단계별)

### ✅ 0단계 — 설계 합의 / 인프라 구축

- [x] plan/ 설계 문서 작성 (3계층 + 5단계 파이프라인, 데이터 스키마, 캐시 전략)
- [x] 디렉토리 스켈레톤 생성 (`parser/`, `render/`, `core/layout/`)
- [x] `parser/protocol.py` — Parser_Protocol 인터페이스
- [x] `render/drawio/README.md` — drawio 백엔드 가이드
- [x] `core/definition.py` — IR Data_Schema 상속, `abstraction/traits/origin/id` 도입
- [x] `cchart/definition.py` — `CXX_Method_Info`에 `is_override/is_final/is_noexcept` 추가
- [x] `core/graph.py` — UML 4분류 엣지, `Node_Info / Positioned_Node / Positioned_Graph`
- [x] `core/hashing.py` — blake2b 4종 해시 + `Is_cache_valid`
- [x] `core/serialization.py` — `Save_stage / Load_stage / Embed_type / Stage_path`
- [x] `core/graph_ops.py` — 위상정렬 / 조상·후손 BFS / 사이클 감지

### ✅ 1단계 — 01_parser 마이그레이션

- [x] `parser/cxx/utils.py` (+ `Make_node_id`)
- [x] `parser/cxx/compile_db.py`
- [x] `parser/cxx/constants.py` (STEREOTYPE_* 제거)
- [x] `parser/cxx/extractor.py` (`CXX_Extractor` — Parser_Protocol 구현)

### ⬜ 2단계 — 02_classifier 신설

- [ ] `parser/cxx/classifier.py`
  - [ ] `abstraction` 잠정 부여 (자기 메서드만 본 1차 분류)
    - 모든 메서드 pure virtual → `interface`
    - 일부만 pure virtual → `abstract`
    - 그 외 → `concrete`
  - [ ] `traits` 부여
    - `template_params` 비어있지 않음 → `template`
    - `--macro-classes` 매칭 → `macro`
    - ctor/dtor 외 메서드 0개 → `data`

### ⬜ 3단계 — 03_linker 마이그레이션

- [ ] `parser/cxx/resolve.py` — name resolution (**공유 모듈** — 플로우 트랙 trace 단계와 공용)
  - [ ] 가까운 namespace 우선 + fully qualified 신뢰
  - [ ] 외부 stub 엔티티 생성 (`origin: external`)
  - [ ] 01 IR 심볼 테이블만 의존 → 02·03 없이 01 직후 사용 가능
- [ ] `parser/cxx/linker.py`
  - [ ] phase 1: build_inheritance_graph (base 엣지 잠정 inheritance)
  - [ ] phase 2: refine_abstraction (상속 체인 따라 보정, 순환 가드, 외부 base 무시)
  - [ ] phase 3: build_other_edges
    - composition / aggregation / association / dependency (UML 휴리스틱)
    - include
    - base가 interface → realization으로 갱신
  - [ ] `resolve.py`로 관계 해석
  - [ ] `Node_Info` 래핑 + `ir_source` 부착

### ⬜ 4단계 — 04_layout 신설

- [ ] `core/layout/semantic.py`
  - [ ] `(layer, wing, col)` 부여 (자동 규칙: plan/layout.md)
  - [ ] hint 적용 자리 (현재는 no-op)
  - [ ] namespace 그룹화 정보 부착
- [ ] `core/layout/crossing.py`
  - [ ] barycenter heuristic 2회 반복으로 col 순서 결정

### ⬜ 5단계 — Renderer 마이그레이션

- [ ] `render/drawio/` 본체
  - [ ] `style.py` (좌표 상수, swimlane / edge / child 스타일 빌더)
  - [ ] `models.py` (`Mx_Cell`, `Mx_Geometry`)
  - [ ] `utils.py` (XML escape 등)
  - [ ] `formatter.py` (속성/메서드 HTML 포맷)
  - [ ] `builder.py` (Positioned_Graph → XML)
  - [ ] (layer/wing/col → 픽셀 변환, 새 엣지 종류 매핑, abstraction/traits 시각 채널)
- [ ] `render/mermaid/` — 스켈레톤만
- [ ] `render/plantuml/` — 스켈레톤만

### ⬜ 6단계 — Pipeline facade 및 CLI

- [ ] `code_chart/` — 단일 CLI facade, 신 모듈들로 파이프라인 재구성
  - [ ] `--language`로 언어별 parser 디스패치 (언어 결정의 유일 기준)
  - [ ] 단계별 yaml 캐시 적재/저장 (`--debug` 옵션)
  - [ ] 해시 기반 자동 무효화 (`Is_cache_valid`)
  - [ ] 디렉토리 단위 출력 (`{output_root}/result/{dir}.drawio`)
- [ ] `pyproject.toml` — `cchart`/`pychart` 두 스크립트 → 단일 `code-chart`
- [ ] CLI 옵션 정리 (`--debug`, `--language` 필수, `--macro-classes`, hint 자리)
- [ ] 구 `cchart/parser/*`, `core/form/*`, `cchart/registry.py` 제거 / 이전

---

## 향후 작업

### 플로우 트랙 (call-flow → 시퀀스 다이어그램)

[plan/flow-track.md](plan/flow-track.md) · [plan/trace-model.md](plan/trace-model.md) 참고.
01_parser를 공유 줄기로 01 직후 분기.

- [ ] `01_parser`에 메서드 본문 call-site 추출 추가 (공유 줄기 보강)
- [ ] `parser/cxx/resolve.py` 활용 (3단계에서 분리 생성)
- [ ] `core/` Trace 데이터 모델 — `Trace_Model` / `Lifeline_Info` / `Message_Info` / `Fragment_Info` / `Branch_Info` / `Positioned_Trace`
- [ ] `parser/cxx/tracer.py` — trace 단계 (진입점부터 호출 트리, 바인딩 환경 + 사용 측 앵커링)
- [ ] sequence-layout — lifeline 가로 순서 결정 (`Positioned_Trace`)
- [ ] `render/` 시퀀스 렌더러 (mermaid / plantuml)
- [ ] CLI `--entry` 옵션, `result/{scenario}.{ext}` 출력

### Python 백엔드 (`parser/python/`)

- [ ] `parser/python/extractor.py` — AST 추출 + import 그래프로 의존성 도출
- [ ] `parser/python/classifier.py` — ABC 상속·`@abstractmethod` 등 Python식 abstraction 판정
- [ ] `parser/python/linker.py` — Python 모듈/패키지 관계 해석

### 부가 기능 (자리만 잡혀 있음)

- [ ] `--layer-hint`, `--wing-hint`, `--hide` 옵션 동작 구현 (현재 자리만)
- [ ] `render/mermaid/`, `render/plantuml/` 백엔드 본체
- [ ] `--show-all-edges` 옵션 (다중 엣지 우선순위 흡수 해제)
