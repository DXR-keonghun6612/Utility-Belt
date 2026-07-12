# process

**연산**과, 연산을 잇는 **엔진**. 데이터는 [`../store`](../store) 에만 요청한다 — 이 계층은 파일 포맷도
경로 파생도 **모른다**.

각 심볼의 인자·반환·호출 예시는 그 심볼의 docstring 에 있다. 이 문서는 **심볼 사이에 걸치는 것**만 다룬다.

---

## 왜 엔진이 하나인가

Run(연산)과 Sample(파생 생성)은 겉보기에 다른 작업이지만, 둘 다 *무언가를 순회하며 연산 체인을 태우고
결과를 어딘가에 앉힌다*. 다른 건 **양 끝**(무엇을 ctx 로 푸나 / 출력을 어디에 앉히나)뿐이고 그 사이 체인의
계약은 같다. 그래서 두 개의 파이프라인이 아니라 **`Stage` 한 엔진**이고, 나머지는 양 끝을 갈아끼운 구성이다.

| stage | 순회 | 출력 |
|---|---|---|
| **Run** (`Flow`) | `modified` 범주 | 같은 store 에 route |
| **Sample** (`Sample_stage`) | `staged` 범주 | 파생 store 에 배치 |
| **분석** (`Flow`) | 학습셋 **전 split** | 같은 store 에 route (결과는 `params`) |

**`Flow` 는 store 를 안 가린다.** `category` 는 필드라 `Flow(category=["train","val","test"])` 를 `Sample_Set`
위에서 돌릴 수 있다 — 분석이 별도 계층이 아니라 **flow 하나**인 이유다.

**범주를 여럿 줄 수 있는 이유는 `carry` 다.** 순회가 범주 경계에서 끊기지 않아 `finalize` 가 전체를 **한
덩어리로** 본다. 이게 없으면 split 마다 따로 군집이 돌아 **클러스터 id 가 서로 무의미해진다**(같은 형상이
split 마다 다른 번호를 받는다). 그래서 범주는 stage 의 설정이 아니라 **unit 의 주소**다 — 라우팅 경로가
거기서 나온다.

> **양 끝을 클래스로 세우지 마라 — 그게 지난번 실패였다.** 옛 `source`/`sink` 계약은 traversal 기계를
> 추상화했지만, 진짜 변주는 traversal 이 아니라 양 끝이었다. 그래서 추상이 stage 세 개 중 둘에만 맞았고
> (Convert 는 골격을 통째 override 했다), 결국 **파라미터와 훅 두어 개**로 충분했다. 순회는
> `store.Bucket(category)` 한 줄이고 **범주는 클래스가 아니라 필드**다.

**Convert 는 엔진에 없다.** 체인이 비어 ctx 도 resolve 도 안 쓰므로 빌릴 게 순회 루프뿐이었다 —
하는 일이 `scan → Save → Set` 이라 계산이 아니라 **store 진입 게이트**다(→ `store.Import`).

flow 의 *종류*는 서브클래스도 코드 preset 도 아니라 **config 가 직접 기술**한다 — 종류마다 클래스를 만들면
종류가 늘 때마다 코드가 는다. 엔진은 순회 상태를 인스턴스에 남기지 않는다(누산조차 `__call__` 지역 변수라
같은 `Stage` 를 두 번 돌려도 서로를 오염시키지 않는다).

---

## 계산은 두 층이다 — 경계는 "무엇을 아는가"

| 층 | 아는 것 |
|---|---|
| `stream/` | **저장 표현**(`Data_Ref`)을 알고 **계산을 모른다** |
| `func/` | **도메인 자료형**(배열·박스·id)만 알고 `Data_Ref` 를 모른다 |

`stream` 유닛이 하는 일은 ctx 에서 값을 꺼내고 → `func` 를 부르고 → 결과를 조립하는 것뿐이다. 이 방향이
지켜지면 **모든 계산이 store 없이 단독으로 호출·검증된다.** 각 층의 규칙은 그 층의 README 가 갖는다
([`stream/`](stream/README.md) · [`func/`](func/README.md)).

**프로세스는 입력이 아니라 출력의 도메인에 속한다** — edge 를 읽어 mask 를 내는 유닛은 mask 유닛이다
(입력은 어느 도메인에서 와도 된다. 그게 데이터흐름이다). 여러 도메인을 엮는 일(combine·gate·wiring)은
유닛이 아니라 **엔진과 config** 의 몫이다.

---

## ctx — 두 스코프, 하나의 게이트

| 스코프 | 사는 곳 | 수명 |
|---|---|---|
| transient | `ctx` | `__call__` 과 함께 소멸 (step↔step, 누산기 포함) |
| persistent | store | 실행을 넘어 생존 |

**스코프는 값의 속성이 아니라 라우팅된 결과다.** 누산기 같은 transient 값도 라우팅하면 영속으로 남는다.
`_route` 가 그 유일한 승격 게이트이고, `outputs` 에 선언되지 않은 키는 ctx 에 머물다 죽는다. 그래서 "이 값이
저장되나?"는 값을 봐서는 알 수 없고 config 를 봐야 안다 — 의도된 성질이다.

입력 쪽 대칭은 **resolve** 다. **불변인 가장 넓은 스코프에서 1회** — 프레임 이미지를 객체 수만큼 다시 읽지
않기 위한 규칙이고, block→unit 2단이 존재하는 이유다. 그래서 유닛은 `Data_Ref` 가 아니라 이미 디코드된
값만 본다.

**유닛은 store 를 모른다.** 객체 목록이 필요하면 ctx 의 `object` 를 읽는다 — 엔진이 store 에서 seed 하고
`split_objects` 가 같은 키로 덮어쓰므로 **입력과 출력이 같은 이름으로 대칭**이다.

---

## port ↔ slot — 같은 유닛을 두 번 쓰기

유닛이 선언한 출력 이름은 `port` 이고, ctx 에 실제로 얹히는 이름은 `slot` 이다. 기본은 같지만 config 의
`slots` 가 갈라놓을 수 있다. 이게 없으면 같은 유닛을 한 체인에서 두 번 쓸 때 서로의 출력을 덮어쓴다 —
`fill_edge` 를 두 번 돌려 하나를 `other` 로 보내고 `combine_mask` 의 두 입력에 잇는 식이 불가능해진다.

재배선 뒤의 **slot 이름이 진실**이다. 이후의 라우팅·`carry`·다음 step 입력이 모두 slot 을 본다. 입력 쪽
대칭은 `inputs`(ctx 키 → `Run` 파라미터 별칭) — producer 없이 ctx 에 얹힌 값(예: params 의 `roi`)을 이름이
다른 파라미터에 잇는 자리다.

---

## carry / finalize — 누산이 두 조각인 이유

`carry` 는 프레임 사이로 값을 이월하고, `finalize` 는 순회가 끝난 뒤 한 번 도는 체인이다. 둘로 나뉜 건
**누산기가 순회와 함께 죽기 때문**이다. 누산기는 ctx 에 살다 `__call__` 과 함께 사라지므로, 그걸 통계로
바꾸는 변환은 반드시 *같은 호출 안에서* 일어나야 한다. `finalize` 가 그 자리다.

`finalize` 는 per-frame 체인과 같은 엔진·같은 라우팅 규칙을 쓰고 차이는 **도는 시점**뿐이다. frame/object
위치가 없으므로 출력은 자동으로 dataset-wide(`params`)로 간다.

---

## 구성

```text
process/
├── __init__.py   PROCESS_REGISTRY · Build_process · Build_flow (+유닛 등록 트리거)
├── _base.py      Base_Process(유닛 계약) · Stage(엔진) · Flow(Run 구성)
├── sample.py     Sample_stage — 같은 엔진, 양 끝만 다름 (staged 순회 → 파생 store 배치)
├── stream/       배선 — 저장 표현을 알고 계산을 모른다     → stream/README.md
├── func/         계산 — 도메인 자료형만 안다               → func/README.md
└── analysis/     ⚠ 아직 흡수되지 않은 덩어리 (계층이 아니다)
```

**`analysis/` 는 계층이 아니다.** 옛 `Analysis` 계약(analyze/report/figure + 레지스트리)은 **구현자 0·등록
0·호출 0** 이라 삭제했다 — 아무도 구현하지 않는 추상이었고, 실제 소비처는 계약을 무시하고 모듈 함수를 직접
import 했다. 남은 모듈의 갈 곳은 [`TODO.md`](TODO.md) 가 소유한다(계산은 `func/` 로, 군집 분석은 **산출물
소비자**로 — 파이프라인과 수명이 다르므로 엔진에 접히지 않는다).

무거운 모델은 유닛이 소유하지 않는다. pipeline 이 스펙당 한 번 빌드해 주입하고, 유닛은 핸들만 든다.
