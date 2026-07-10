# process

**연산**과, 연산을 잇는 **엔진**을 담는 패키지. 상위 구조·용어는 [`../README.md`](../README.md),
데이터 계층은 [`../data/README.md`](../data/README.md). 남은 작업은 [`../TODO.md`](../TODO.md).

각 심볼의 인자·반환·호출 예시는 그 심볼의 docstring에 있다. 이 문서는 **심볼 사이에 걸치는 것**만 다룬다.

---

## 왜 엔진이 하나인가

Convert(원본 적재) · Run(연산) · Sample(파생 생성)은 겉보기에 다른 작업이지만, 셋 다 *무언가를 순회하며
연산 체인을 태우고 결과를 어딘가에 쓴다*. 다른 건 **무엇을 순회하는가**(source)와 **어디에 쓰는가**(sink)
뿐이고, 그 사이 체인의 계약은 같다. 그래서 세 개의 파이프라인이 아니라 `Stage(source → 체인 → sink)`
**한 엔진**이고, 나머지는 양 끝을 갈아끼운 구성이다.

| stage | source | sink | 사는 곳 |
|---|---|---|---|
| **Convert** | `Raw_source` | `Register_sink` | [`../converter`](../converter) |
| **Run** (`Flow`) | `Frame_source` | `Meta_sink` | 여기 (`_base.py`) |
| **Sample** | `Staged_source` | `Sample_sink` | [`../sampler`](../sampler) |

`Flow` = Run 구성의 `Stage` 서브클래스. flow 의 *종류*는 서브클래스도 코드 preset 도 아니라 **config 가
직접 기술**한다 — 종류마다 클래스를 만들면 종류가 늘 때마다 코드가 는다. 복붙 템플릿은
[`presets.example.yaml`](presets.example.yaml)(코드가 읽지 않는다).

엔진은 순회 상태를 인스턴스에 남기지 않는다. 누산조차 `__call__` 지역 변수라, 같은 `Stage` 를 두 번 돌려도
서로를 오염시키지 않는다.

---

## 연산은 두 종류다

| 종류 | 계약 | 받는 것 → 내는 것 | 소비자 |
|---|---|---|---|
| `stream/` | `Base_Process` | ctx → ctx (프레임·객체 단위 스트리밍) | `Stage` 체인 |
| `analysis/` | `Analysis` | store·배열 통째 → report·figure | Verify, CLI/GUI |

스트리밍 유닛은 순회 안에서 한 단위씩 흐르고, 분석은 순회가 끝난 데이터셋을 통째로 본다. 축이 달라서 한
계약으로 묶으면 둘 다 왜곡된다. 도메인 수학(chroma 통계·polar 변환 등)은 `func/` 에서 공유한다.

`func/` 는 **연산이 아니다.** 자유함수 primitive 이고, 두 종류가 모두 여기서 계산을 빌린다.
(표준 `.gitignore` 의 `lib/` 와 충돌해 `func` 으로 이름지었다.)

### 순수 도메인 함수 규칙

프로세스는 **입력이 아니라 출력의 도메인**에 속한다. edge 를 읽어 mask 를 내는 유닛은 mask 유닛이다 —
입력은 어느 도메인에서 와도 되기 때문이다(그게 데이터흐름이다).

> `stream/<domain>` 유닛은 `func/<domain>` 과 제네릭 `func/cv` 만 import 한다. **다른 도메인의 func 금지.**

이 선을 넘기 시작하면 폴더가 도메인이 아니라 "예전에 누가 여기 뒀던 것"이 된다. 실제로 `edge/` 가 mask
연산을 품고 `chroma/` 가 mask 유틸을 당기던 게 이 재편의 이유다. 여러 도메인을 엮는 일(combine·gate·
wiring)은 유닛이 아니라 **엔진과 config** 의 몫이다.

---

## ctx — 두 스코프, 하나의 게이트

| 스코프 | 사는 곳 | 수명 |
|---|---|---|
| transient | `ctx` | `__call__` 과 함께 소멸 (step↔step, 누산기 포함) |
| persistent | `dataset_meta` | 실행을 넘어 생존 |

**스코프는 변수의 속성이 아니라 라우팅된 결과다.** 누산기 같은 transient 값도 라우팅하면 영속으로 남는다.
`sink.route` 가 그 유일한 승격 게이트이고, `outputs` 에 선언되지 않은 키는 ctx 에 머물다 죽는다. 그래서
"이 값이 저장되나?"는 값을 봐서는 알 수 없고 config 를 봐야 안다 — 의도된 성질이다.

입력 쪽 대칭은 resolve 다. persistent → ctx 로, **불변인 가장 넓은 스코프에서 1회**. 프레임 이미지를 객체
수만큼 다시 읽지 않기 위한 규칙이고, 그래서 유닛은 `Data_Ref` 가 아니라 이미 디코드된 값만 본다.

---

## port ↔ slot — 같은 유닛을 두 번 쓰기

유닛이 선언한 출력 이름은 `port` 이고, ctx 에 실제로 얹히는 이름은 `slot` 이다. 기본은 같지만 config 의
`slots` 가 갈라놓을 수 있다. 이게 없으면 같은 유닛을 한 체인에서 두 번 쓸 때 서로의 출력을 덮어쓴다 —
`fill_edge` 를 두 번 돌려 하나를 `other` 로 보내고 `combine_mask` 의 두 입력에 잇는 식이 불가능해진다.

재배선 뒤의 **slot 이름이 진실**이다. 이후의 `outputs` 라우팅·`carry`·다음 step 입력이 모두 slot 을 본다.
입력 쪽 대칭은 `inputs`(ctx 키 → `Run` 파라미터 별칭) — producer 없이 ctx 에 얹힌 값(예: params 의 `roi`)을
이름이 다른 파라미터에 잇는 자리다.

---

## carry / finalize — 누산이 두 조각인 이유

`carry` 는 프레임 사이로 값을 이월하고, `finalize` 는 순회가 끝난 뒤 한 번 도는 체인이다. 둘로 나뉜 건
**누산기가 순회와 함께 죽기 때문**이다. `c0_acc` 같은 누산기는 ctx 에 살다 `__call__` 과 함께 사라지므로,
그걸 통계로 바꾸는 변환은 반드시 *같은 호출 안에서* 일어나야 한다. `finalize` 가 그 자리다.

`finalize` 는 per-frame 체인과 같은 엔진·같은 라우팅 규칙을 쓰고, 차이는 **도는 시점**뿐이다. frame/object
위치가 없으므로 출력은 자동으로 dataset-wide(`params`)로 간다. 누산기 자신은 어느 step 의 출력으로도
선언되지 않으면 영속되지 않는다 — 위의 게이트 규칙 그대로다.

---

## 구성

```text
process/
├── __init__.py   PROCESS_REGISTRY · Build_process · Build_flow (+유닛 등록 트리거)
├── _base.py      Base_Process(유닛 계약) · Stage(엔진) · Flow(Run 구성)
├── source.py     Base_Source · Stem_Block · Unit — 무엇을 순회·resolve 하나
├── sink.py       Base_Sink — 출력을 어디로 (outputs spec 스키마는 여기 docstring)
├── stream/       종류1 — 배선 (저장 표현을 알고 계산을 모른다) → stream/README.md
├── analysis/     종류2 — 집계 분석 (Analysis 계약)
└── func/         primitive — 계산 (도메인 자료형만 안다) → func/README.md
```

**stream 과 func 의 경계는 "무엇을 아는가"다.** `func` 는 배열·박스·id 만 알고 `Data_Ref` 를 모른다.
`stream` 은 정확히 그 반대로, 저장 표현을 해체·조립하고 계산은 `func` 에 넘긴다. 이 방향이 지켜지면
모든 계산이 store 없이 단독으로 호출·검증된다. 각 층의 규칙은 그 층의 README 가 갖는다.

무거운 모델은 유닛이 소유하지 않는다. pipeline 이 스펙당 한 번 빌드해 주입하고, 유닛은 핸들만 든다.
