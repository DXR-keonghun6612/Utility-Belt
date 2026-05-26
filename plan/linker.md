# 03_linker — 관계 해석 + abstraction 보정

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

name resolution은 플로우 트랙의 trace 단계와 공유한다 — 공통 모듈로 분리 권장
(`parser/cxx/resolve.py`). [flow-track.md](flow-track.md)의 linker 폴백 참고.

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
