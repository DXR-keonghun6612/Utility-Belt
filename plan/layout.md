# 04_layout — 추상 좌표

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
