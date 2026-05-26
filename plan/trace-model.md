# Trace_Model — 플로우 트랙 데이터 모델

플로우 트랙의 trace 단계 출력. 구조 트랙의 `Graph_Model`에 대응하지만 완전히 별개 모델이다.
시퀀스 다이어그램은 **순서가 있는 호출 트리** — 메서드 본문이 호출들을 순서대로 담고 일부는
if/loop로 묶임 — 이라 트리로 모델링한다. `Graph_Model`(노드+엣지, 시간 무관)에 욱여넣지 않는다.

모든 타입은 설계 규약을 따른다: `Data_Schema` 상속, `type` 필드를 역직렬화 디스패치 키로.

## 구성 요소

### `Trace_Model` — trace 단계 출력

| 필드 | 타입 | 의미 |
|------|------|------|
| `scenario` | str | 시나리오 이름 |
| `entry` | str | 진입점 노드 ID |
| `lifelines` | `list[Lifeline_Info]` | 참여자 목록 |
| `root` | `Message_Info` | 진입점 활성화 (synthetic actor → entry) |

### `Lifeline_Info` — 참여자 (구조 트랙 `Node_Info`에 대응)

| 필드 | 값 | 의미 |
|------|----|----|
| `id` | str | lifeline ID |
| `name` | str | 표시 이름 |
| `kind` | `actor / object / role / external` | role = 미해석 콜백·인터페이스 (실패 아님, 유효 UML) |
| `node_ref` | str \| null | 구조 트랙 `Node_Info` ID로의 교차 링크 |
| `origin` | `internal / external` | |

### `Message_Info` — 한 호출 = 한 메시지

자식 `steps`를 품어 트리를 이룬다.

| 필드 | 값 | 의미 |
|------|----|----|
| `from_lifeline_id` / `to_lifeline_id` | str | 호출자 / 수신자 |
| `signature` | str | `parse(path)` 등 |
| `kind` | `call / create` | create = 생성자/팩토리(lifeline 시작점). self 호출은 from==to로 파생 |
| `resolution` | 아래 표 | 해석 신뢰도 |
| `via_macro` | str \| null | 매크로 전개 출처 (직교적 provenance) |
| `traced` | bool | 콜리 본문으로 하강했는가 |
| `cut_reason` | `external / depth / recursion / unresolved` \| null | 미하강 사유 |
| `steps` | `list[Message_Info \| Fragment_Info]` | 콜리 본문 내 호출/프래그먼트 (순서대로) |
| `returns` | str \| null | 반환값 요약 (return 메시지는 암묵적, 렌더러가 그림) |
| `source_line` | int | |

### `Fragment_Info` — 제어 흐름 묶음

| 필드 | 값 |
|------|----|
| `kind` | `alt / opt / loop` |
| `branches` | `list[Branch_Info]` |
| `source_line` | int |

### `Branch_Info` — fragment의 한 분기

| 필드 | 값 |
|------|----|
| `guard` | str — 조건문 텍스트 또는 `else` |
| `steps` | `list[Message_Info \| Fragment_Info]` |

### `Positioned_Trace` — sequence-layout 단계 출력

`Trace_Model`에 더해 각 `Lifeline_Info`에 `order: int`(가로 위치)만 추가.
메시지 세로 순서는 트리 DFS 순서라 추가 필드 불필요. 구조 트랙 `Positioned_Graph`에 대응.

> 바인딩 환경은 트레이서의 작업 상태일 뿐 모델에 들어가지 않는다. 그 *결과*만 `resolution`
> 필드로 남는다.

## resolution 어휘

| 값 | 의미 | lifeline |
|----|------|----------|
| `direct` | 정적으로 단일 대상 확정되는 일반 호출 | 구체 object |
| `bound` | 간접 호출(fn ptr/콜백/가상)을 바인딩 환경으로 구체 해석 | 구체 object |
| `declared` | 못 풀어 선언 타입(linker 폴백)으로 표기 | 보통 role |
| `unresolved` | 어떤 정보로도 미상 → 미하강 | role |

`via_macro`는 직교적 provenance — 매크로 전개로 생긴 호출도 해석 자체는 위 4값 중 하나.
간접 호출 해석 원칙은 [flow-track.md](flow-track.md)의 사용 측 앵커링 참고.

## yaml 예시

```yaml
# debug/trace/load_config.yaml
meta:
  schema_version: 1
  scenario: load_config
  entry: src/app/config.cpp::app::Config_Loader::load
  upstream_hashes:                    # 추적 경로상 모든 01 yaml
    src/app/config.cpp: <01 해시>
    src/io/yaml_reader.cpp: <01 해시>
  depth_limit: 8

body:
  type: Trace_Model
  scenario: load_config
  entry: src/app/config.cpp::app::Config_Loader::load
  lifelines:
    - {type: Lifeline_Info, id: ll::actor,   name: caller,        kind: actor,  node_ref: null, origin: internal}
    - {type: Lifeline_Info, id: ll::loader,  name: Config_Loader, kind: object, node_ref: "src/app/config.cpp::app::Config_Loader", origin: internal}
    - {type: Lifeline_Info, id: ll::reader,  name: Yaml_Reader,   kind: object, node_ref: "src/io/yaml_reader.cpp::io::Yaml_Reader", origin: internal}
    - {type: Lifeline_Info, id: ll::handler, name: Error_Handler, kind: role,   node_ref: "src/app/error.h::app::Error_Handler", origin: internal}
  root:
    type: Message_Info
    from_lifeline_id: ll::actor
    to_lifeline_id: ll::loader
    signature: load(path)
    kind: call
    resolution: direct
    via_macro: null
    traced: true
    cut_reason: null
    returns: Config
    source_line: 12
    steps:
      - type: Message_Info
        from_lifeline_id: ll::loader
        to_lifeline_id: ll::reader
        signature: read(path)
        kind: call
        resolution: direct
        via_macro: null
        traced: true
        cut_reason: null
        returns: string
        source_line: 15
        steps: []
      - type: Fragment_Info
        kind: alt
        source_line: 18
        branches:
          - type: Branch_Info
            guard: "parse 실패"
            steps:
              - type: Message_Info
                from_lifeline_id: ll::loader
                to_lifeline_id: ll::handler
                signature: on_error(msg)
                kind: call
                resolution: unresolved      # 콜백, 바인딩 환경에 없음
                via_macro: null
                traced: false
                cut_reason: unresolved
                returns: null
                source_line: 20
                steps: []
          - type: Branch_Info
            guard: else
            steps: []
```
