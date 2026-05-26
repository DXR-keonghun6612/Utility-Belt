# 데이터 모델

## IR Layer (`core/`)

- 공통: `Arg_Info`, `Method_Info`, `Class_Info`, `Module_Info`
- 언어 확장: `CXX_Class_Info`, `CXX_Method_Info`, `Translation_Unit_Info` 등
- 모두 `Data_Schema` 상속

## Graph Layer (`core/`)

- `Node_Info` — Graph 노드 래퍼 (id, name, category, abstraction, traits, origin)
- `Edge_Info` — 엣지 (source_id, target_id, edge_type)
- `Graph_Model` — 03 출력
- `Positioned_Graph` — 04 출력 (Node_Info에 layer/wing/col 추가)

## Trace Layer (`core/`)

플로우 트랙(시퀀스 다이어그램)의 데이터 모델. `Trace_Model`, `Lifeline_Info`,
`Message_Info`, `Fragment_Info`, `Branch_Info`, `Positioned_Trace`.
상세는 [trace-model.md](trace-model.md) 참고.

## 검출 대상 카테고리

| 카테고리 | 포함 | stereotype 적용 |
|---------|------|----------------|
| **Type** | class, struct, union | ✓ (abstraction + traits) |
| **Callable** | function, method | ✗ (메타필드만) |
| **Data** | field, variable | ✗ (메타필드만) |

## `Module_Info.origin`

기존 `Module_Info.stereotype: Literal["«local»","«external»"]`를
`Module_Info.origin: Literal["internal","external"]`로 통일.
클래스 분류 stereotype과 의미 혼동 제거.
