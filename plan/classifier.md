# 02_classifier — 분류 부여

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
