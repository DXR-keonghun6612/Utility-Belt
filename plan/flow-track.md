# 플로우 트랙 — call-flow → 시퀀스 다이어그램

구조 트랙(클래스 다이어그램)이 "무엇이 있고 어떻게 연결되어 있나"를 다룬다면,
플로우 트랙은 "무엇이 무엇을 어떤 순서로 호출하나"를 다룬다. 결과물은 시퀀스 다이어그램.

UML 자체가 structure diagram / behavior diagram으로 나뉘듯, 같은 코드를 두 관점으로
보는 것이라 분석 파이프라인을 둘로 가른다.

## 정적 call-flow 추적

플로우 트랙은 **런타임 트레이싱이 아니라 정적 call-flow 분석**이다.

- 런타임 트레이싱 — 계측 삽입 → 실행 → 호출 시퀀스 수집. 정확하지만 빌드·실행 환경 필요,
  "소스→다이어그램, 무실행" 전제를 깸. → 채택하지 않음.
- 정적 call-flow 추적 — 진입점부터 AST를 따라 호출 그래프를 펼침. libclang AST만으로 가능.

## 공유 줄기와 분기점

두 트랙은 AST를 한 번만 판다. 공유하는 줄기:

- `01_parser` — AST → IR. 단 **시그니처 + call-site를 둘 다** 추출 (구조 트랙은 call-site 무시).
- `core` IR 정의 — 플로우 트레이서도 callee 해석에 메서드 시그니처가 필요.
- 인프라 — hashing / serialization / cache / debug yaml.
- name resolution + 전역 심볼 테이블 — 두 트랙 모두 "이름 + namespace → 엔티티" 해석 필요.
  03_linker 안에 두지 말고 공통 모듈(`parser/cxx/resolve.py`)로 분리해 공유.
  resolve.py는 01의 IR 심볼 테이블만 의존 → 02·03 없이 01 직후 사용 가능 (02의 분류는 불필요).

분기점은 **01 직후**. 플로우 트랙은 `02_classifier`가 불필요하다 (lifeline은 객체지
interface/concrete 구분이 아님).

```
                [01_parser]   ← 공유 줄기 (AST→IR, 시그니처+call-site)
                     │
        ┌────────────┴────────────┐
   구조 트랙                  플로우 트랙
   02_classifier              trace            진입점부터 call-flow 펼침
   03_linker                  sequence-layout  lifeline 순서 + 메시지 세로 순서
   04_layout                  sequence renderer
   class renderer
   → 클래스 다이어그램          → 시퀀스 다이어그램
```

## 사용 측 앵커링 — 간접 호출 해석 원칙

가상 디스패치 / 함수 포인터 / 콜백은 정적으로 단일 대상을 확정하기 어렵다.
핵심 원칙: **정의 측이 아니라 사용 측에 앵커를 둔다.**

- 정의 측 (함수 포인터 타입 선언, 콜백 시그니처, 매크로 정의, 가상 함수 선언) — *open-world*.
  "누가 나를 쓸지 모름". 여기서 풀려면 전프로그램 points-to 분석 필요 → 비싸고 부정확.
- 사용 측 (포인터에 `&Foo` 대입, 콜백을 `register(handler)`로 넘김, 매크로 전개 지점) —
  충분히 *closed*. "여기서는 무엇이 붙는지 안다".

### 바인딩 환경

트레이서는 진입점부터 한 경로를 걷는다. 걸으면서 **바인딩 환경**(`슬롯 → 구체 callable` 맵)을
들고 다닌다. 콜백·함수 포인터가 파라미터로 전달되면, 트레이서가 그 함수로 들어갈 때 실인자
바인딩을 환경에 넣는다 → 내부의 간접 호출은 환경 조회로 풀린다.

```
run() ──call(handler=&Concrete::foo)──▶ dispatch(h)
   환경: {}                              환경: { h ↦ &Concrete::foo }
                                            h() 호출 → 환경 조회 → 해석
```

이 방식은 **자동으로 context-sensitive** — 같은 함수를 두 곳에서 부르면 두 시퀀스가 각자 다른
구체 대상으로 풀린다. "한 다이어그램 = 한 시나리오"라 정확히 맞는 동작이다.
전프로그램 points-to 분석이 필요 없다.

### 메커니즘별 처리

| 메커니즘 | 사용 지점 | 해석 |
|----------|----------|------|
| 함수 포인터 | 대입 `fp = &Foo` | 같은 본문 지역 대입 또는 파라미터 바인딩 → 환경. 멤버 필드면 setter가 추적 경로에 있을 때만. |
| 콜백 | 등록 `register(h)` | 동기 호출(파라미터 전달) → 환경. 비동기(멤버 저장 후 나중 호출) → 등록 지점을 바인딩 사실로 기록, 나중 호출이 경로 밖이면 미해석. |
| 가상 디스패치 | 객체 생성 지점 | 지역 생성·팩토리 반환 등 동적 타입을 경로상에서 알면 해석. 아니면 정적 타입의 선언 메서드로 폴백. |
| 매크로 함수 | 전개 지점 | libclang이 전개 → 01_parser가 전개된 AST 추출. 사실상 가장 쉬움. 매크로 출처만 메타로 기록. |

### 정적 타입 폴백

간접 호출을 바인딩 환경으로 못 풀어도 **선언된 정적 타입**이라는 바닥 답은 항상 있다.
2층 구조:

- 트레이서(플로우) — 바인딩 환경으로 구체 대상 시도. 경로 의존적, 더 정확.
- 폴백 — 못 풀리면 수신 표현식의 선언 타입을 `resolve.py`로 조회. 보통 인터페이스·typedef
  같은 역할(role)로 귀결.

이 폴백이 쓰는 것은 03_linker의 *출력*(`Graph_Model`)이 아니라 공유 모듈 `resolve.py`다 —
03_linker **단계 자체에는 의존하지 않는다**.

해석 결과는 `Message_Info.resolution` 필드로 기록 → [trace-model.md](trace-model.md) 참고.

## trace 단계

**책임**
- 진입점 함수부터 call-site를 펼쳐 호출 트리 생성
- 바인딩 환경 유지 + 사용 측 앵커링으로 간접 호출 해석
- 제어 흐름(if/loop)을 alt / opt / loop fragment로 보존
- 재귀 가드 + depth 제한, 외부/std 경계에서 하강 중단
- 결과를 `Trace_Model`로 직렬화

**분석 단위** — 구조 트랙은 디렉토리 단위지만 플로우 트랙은 **시나리오(진입점) 단위**.
`--entry <node-id>` 옵션으로 진입점 지정.

## sequence-layout 단계

**책임** — lifeline 가로 순서 결정(메시지 선 교차 최소화). 메시지 세로 순서는 트리 DFS
순서라 별도 계산 불필요. 구조 트랙의 04_layout(2D 의미 좌표)과 달리 1D 정렬이라 훨씬 단순.
출력은 `Positioned_Trace`.

## 중간 결과 저장

```
{output_root}/
  debug/
    trace/{scenario}.yaml
    sequence_layout/{scenario}.yaml
  result/
    {scenario}.{ext}
```
