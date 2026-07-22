# core

LENS 코어 — raw 데이터에서 **정본 annotation** 을 만들고, 그로부터 **학습셋**을 파생하는 계층.

이 문서는 **지도**다. 각 계층의 내부는 그 폴더의 README 가 소유하고, 여기선 **계층이 왜 이렇게 갈렸는지**와
**서로를 어떻게 부르는지**만 적는다.

---

## 계층은 "무엇을 아는가"로 갈린다

하는 일이 아니라 **아는 타입**이 계층을 정한다. 이 기준을 크기·편의로 바꾸면 경계가 무너진다.

**계층 번호(`lv`)는 이 표가 소유한다** — 낮은 번호가 아래다. 같은 번호끼리는 서로를 부르지 않는다.

| lv | 계층 | 아는 것 | 내부 설계 |
|---|---|---|---|
| 0 | [`schema.py`](schema.py) · `typing` · `constant` | **아무것도 모른다** — 횡단 primitive (의존 0) | 심볼 docstring |
| 0 | [`func/`](func) | 배열↔배열 순수 계산 — core 를 모른다 (numpy·cv2 뿐). 누구나 부른다 | [`func/README.md`](func/README.md) |
| 0 | [`format/`](format) | 데이터 **구조** + 그 연산 (bbox·polygon·rle) — `Data_Ref` 도 I/O 도 모른다 | 패키지 docstring |
| 1 | [`codec/`](codec) | 포맷 단위 **직렬화** (raster·npy·inline·docs) — 도메인을 모른다 | 패키지 docstring |
| 2 | [`port/`](port) | **domain** — 무엇으로 읽나 + 검증·정책 + 디스패치. 데이터 **하나** 읽기/쓰기 + 발견 | [`port/README.md`](port/README.md) |
| 3 | [`store/`](store) | 범주와 item 주소. 데이터 **여럿**의 관리 + 라이프사이클 | [`store/README.md`](store/README.md) |
| 4 | [`process/`](process) | 연산과 결과의 흐름 | [`process/README.md`](process/README.md) |
| 5 | [`_base.py`](_base.py) · [`export/`](export) · `tasker` · `__init__` | 위를 잇는다 (`Pipeline`·export) — 계산 조율 + read+compute+external-write | 심볼 docstring |

```text
schema · func · format          아무것도 안 당기는 밑바닥 (의존 0)
      ↑
    codec  ←  port  ←  store  ←  process  ←  _base
                       └── port 의 유일한 소비자는 store
```

- **`store` 만이 `port` 를 부른다.** 읽기/쓰기는 store 가 소유하고 위 계층은 **요청**한다
  (`store.Resolve`/`store.Route`). 그래서 `process` 는 파일 포맷·경로 파생을 **아예 모른다.**
- **`schema` 는 모두의 어휘다.** `Split_objects` 가 `Data_Ref` 를 만들고 store 의 트리가 그걸로 서 있다 —
  서술은 어느 계층의 소유물도 아니다.

**지켜야 할 불변식은 셋이다** — ① 아래 계층(`lv` 작은 쪽)이 위 계층을 import 하지 않는다 ② `port` 의
소비자는 `store` 뿐이다 ③ `core.schema` 만 들였을 때 cv2 가 딸려오지 않는다.

> ⚠ **지금 이 셋은 산문으로만 있다.** 이걸 `import 방향 검사`로 못박던 `test_layering.py` 는 테스트 전면
> 재구성을 위해 걷어냈다 — 재작성 대상이다([`TODO.md`](TODO.md)). 그때까지 경계는 사람이 지킨다.

### 왜 검사까지 뒀었나 — 같은 경계를 두 바퀴 돌았다

`cv2-free` 는 **`Data_Ref` 한 모듈**의 성질인데, 그걸 **계층 전체의 계약**으로 요구했다. 그러자
`Bucket_Store` 가 영속을 하면서 영속을 모르는 척해야 했고(메서드 본문 안 지연 import), 그 위장의 어색함이
*"라이프사이클이 store 에 있으면 안 되나 보다"* 라는 **2차 오진**을 낳아 `store_io` 분리 → 재흡수를
왕복시켰다.

**처방은 책임 이동이 아니라 순수한 것의 승격이었다** — `Data_Ref` 를 `schema.py` 로 꺼내니 `store` 는
`port` 를 떳떳하게 top-level 로 당길 수 있고, 라이프사이클은 store 소유 그대로다. (규칙은 처음부터 옳았다.)
원칙은 `claude-knowledge` 계층① *"순수성은 모듈에 걸고 계층에 걸지 않는다"*.

---

## 두 단계 — 정본 / 파생

경계 판별: **"task 가 바뀌어도 그 결과를 그대로 쓰나?"** → yes 면 정본, 특정 task 전용이면 파생.

| | 정본 (meta) | 파생 (sample) |
|---|---|---|
| store | `Dataset_Meta` — 범주 = staging 상태 | `Sample_Set` — 범주 = split |
| 만드는 것 | segment · 객체 정렬 · class 부여 · 기하 측정 | 솎아내기 · crop 실체화 · split 배정 |
| 축 | frame | sample |

**`task` 는 빌드의 축이 아니라 내보내기의 축이다.** 파생 빌드는 "무엇을 뽑나"만 정하고,
classification 이냐 detection 이냐는 **내보낼 때** 비로소 의미를 갖는다(→ [`store/README.md`](store/README.md)).
그래서 파생 store 는 하나뿐이고 task 별 타입이 없다.

측정은 정본, 선택은 파생 — 기하 측정처럼 task 가 바뀌어도 쓰는 값은 정본에 남기고, task 특화 선별은
파생에서 솎아낸다(정본은 손실 없이).

---

## 바인더 — `Pipeline`

`core` 자체가 pipeline 이다. 하나의 slim `Pipeline` 이 정본을 들고 **계산 단계**를 조율한다:

```text
Convert → Run → [전이는 store 가] → Sample → Verify
```

- **`Convert`** — raw 를 들인다. **stage 가 아니다** — 체인이 비어 엔진을 안 쓰므로 `meta.Import(…)` 를
  부를 뿐이다(들이는 일은 라이프사이클이라 store 소유).
- **`Run`** — flow 시퀀스를 정본 위에서 구동(process 체인, frame 축).
- **`Sample`** — 이름 붙은 tasker 를 재생성. Run 과 **같은 엔진**이고 양 끝만 다르다.
- **`Verify`** — 미구현 ([`TODO.md`](TODO.md)).

**데이터 라이프사이클은 바인더에 없다** — 전이·삭제·병합·들이기·내보내기는 `store` **메서드**가 소유하고,
호출 측(GUI 등)이 `meta.Move(…)` 를 직접 부른다. 바인더는 계산 단계만 잇는다.

무거운 prediction 모델은 유닛이 소유하지 않는다 — `Pipeline` 이 스펙당 한 번 빌드해 **주입**한다
(프로세스 수명 풀, 같은 스펙은 세션당 1회).

바인더 심볼은 **지연 노출**된다(`from core import Pipeline` 은 되지만 import 자체가 cv2·sam3 을 안 끌고
온다) — 안 그러면 `import core.schema` 만 하려는 소비자가 부모 패키지 실행에 걸려 전부를 들이게 되고,
순수 코어를 따로 뺀 의미가 사라진다.

---

## 횡단 primitive

어느 계층에도 안 속하고 **둘 이상이 공유**하는 원시. 활용부가 여기 맞추지, 그 반대가 아니다.
도메인-로컬 상수·타입은 여기로 올리지 않는다.

- **[`typing.py`](typing.py)** — `Arg_Info`/`Arg`(GUI 표시 힌트, Qt 비의존) · 타입 별칭 `BBOX`·`GRAY_IMAGE`.
- **[`constant.py`](constant.py)** — staging 상태·split 어휘 (문자열 중복 방지).
- **[`tasker.py`](tasker.py)** — 이름 붙은 sample 레시피(`taskers.yaml`) 로드/저장. 산출물이 아니라
  **레시피**라 store 가 아니라 바인더 쪽이다(config ↔ data 분리).

잔여 작업·열린 논의는 [`TODO.md`](TODO.md).
