# core

LENS 코어 — raw 데이터에서 **정본 annotation(meta)** 을 만들고, 그로부터 **학습셋(sampling)** 을
파생하는 계산/데이터 계층.

데이터 라이프사이클을 **정본 / 파생 2단계**로 가르고, 폴더는 **3단계(meta → process → sampling) +
횡단 primitive(typing·constant·schema·handler)** 로 둔다. 계산(compute)과 데이터(data)를 분리하고,
바인더(`Pipeline`/`Sampling`)가 잇는다.

> 정본(meta)·파생(sample) 두 계층 모두 flat `Data_Ref` 스키마로 구현 완료. 실제 반영 정도는 맨 아래
> [구현 상태](#구현-상태) 참조.

---

## 2단계 — 정본(meta) / 파생(sampling)

경계 판별: **"task 가 바뀌어도 그 결과를 그대로 쓰나?"** → yes 면 정본, task-export 전용이면 파생.

| 관점 | 정본 (meta) | 파생 (sampling) |
|---|---|---|
| 데이터 | `Dataset_Meta` | `Sample_Set` |
| 계산 | `meta/converter`(값 채움) + `process`(**frame 축**) | `sampling`(**sample 축**) |
| 바인더 | `Annotating` | `Sampling` |
| 예 | segment · obj 정렬 · class 부여 · param 통계 | crop/normalize · split 배정 · task별 실체화 · 솎아내기 |

`obj 정렬` 같은 정본 속성은 정본에 남고, 파생은 "obj0 선택"처럼 **선택만** 한다. 파생은 **A+** — 순수
재생성 빌드 + `excluded` 솎아내기(원본 진실은 정본에만, 항상 staged 에서 재생성 가능). 뷰·매니페스트도
task-특화(classification=class 폴더, detection/seg=frame 축 + class 통계).

---

## 디렉토리

```text
core/                  ← 데이터(data) + 계산(process/converter/sampler) + 횡단(typing·constant) + 바인더(_base)
├── typing.py    횡단 타입 — Arg_Info·Arg(표시 힌트) · BBOX · GRAY_IMAGE
├── constant.py  횡단 상수 — MODIFIED·STAGED·META_STATES …
├── data/        데이터 계층(store) — schema(Data_Ref·Bucket_Store) · handler · meta(정본) · sample(파생)
├── process/     계산 엔진 — Base_Process 유닛 + Stage(source→체인→sink) + Run(Flow)
├── converter/   Convert 스테이지 — Raw_source(발견) → Register_sink(등록)  (raw → 정본)
├── sampler/     Sample 스테이지 — Staged_source(순회) → Sample_sink[task]  (정본 → 파생)
└── _base.py     Pipeline(Convert→Run→Sample→Verify) + 모델 풀
```

세 스테이지(Convert/Run/Sample)는 **단위 계약(`Base_Process`)이 같고 source/sink 만 다르다** — `process` 의
`Stage` 엔진을 공유하고, `converter`·`sampler` 는 그 위의 source/sink 를 얹는다. data 는 표현·영속(store)만.

하위 패키지는 범위별 `README.md`(설계)를 둔다. 데이터 계층 상세는 [`data/README.md`](data/README.md),
잔여 작업은 [`TODO.md`](TODO.md).

---

## 횡단 primitive

어느 단계에도 안 속하고 **둘 이상이 공유**하는 원시. 활용부(form·process·sample)가 여기 맞추지, 그
반대가 아니다. 도메인-로컬 상수/타입(`META_FILE`·`DEFAULT_SPACE` 등)은 여기로 안 올린다.

> **위치:** `typing`·`constant` 는 core 최상위. 데이터 공유 primitive **`schema`(Data_Ref·
> Bucket_Store)·`handler`** 는 **`data/` 계층 안**에 산다(정본·파생이 공유) — 아래 서술은 그 설계.
> 현재 구조·API 는 [`data/README.md`](data/README.md)·[`data/handler/README.md`](data/handler/README.md).

### `typing.py` — 타입

- **`Arg_Info`** — `__init__` 파라미터/필드에 `Annotated[type, Arg_Info(...)]` 로 붙이는 GUI 표시 힌트
  (label/tip/min/max/step/kind). 순수 데이터(Qt 비의존), `gui/form` 이 읽는다.
- **`Arg`** — 축약 생성자. `Arg(int, "라벨", min=1)` → `Annotated[int, Arg_Info(...)]`. 긴 이름은 정의부
  에만, 사용처는 짧게. `get_type_hints(include_extras=True)` 시점에 평가된다.
- 타입 별칭 **`BBOX`·`GRAY_IMAGE`**.

### `constant.py` — 값

- staging 상태 어휘 **`MODIFIED`·`STAGED`·`META_STATES`**(단일 소스 — 문자열 중복 방지).

### `schema.py` — flat 스키마 (Data_Ref · Bucket_Store)

정본·파생이 **같은 구조를 공유**하므로 core 로 둔다. 트리를 **단일 재귀 타입 `Data_Ref` 하나**로 압축한다
(구 Dataset_Meta/Frame/Object/Data_Ref 5타입 → 1타입 + forest 파사드).

- **`Data_Ref(type, format, info)`** — 트리의 **유일** 노드.
  - **leaf** (`type`=image/array/attr/rle/segmap): `info` = payload(인라인 값 or 파일 위치). `Is_inline()` 이
    인라인(attr/rle/bbox) vs 파일 참조(dir)를 가른다.
  - **컨테이너** (`type="stem"`): `info: {name → Data_Ref}` = 자식(leaf 든 중첩 stem 이든). `__post_init__` 이
    역직렬화 시 자식을 재구성하고, `Serialize` 는 중첩 `Data_Ref` 를 재귀 직렬화. **Frame/Object 를 흡수** —
    obj_id·이름은 부모 `info` 의 **key**, class 는 `info["class_id"]` attr(`schema.Attr`/`Set_attr`). 노드 클래스·
    필드가 없어 frame/object 가 균일한 stem.
- **`Bucket_Store`** — 트리 노드가 **아니라 forest 파사드**(`Data_Ref` 상속 안 함). `params`(범주 무관 root
  leaf) + `buckets: {category → {key: stem Data_Ref}}`(n개 독립 persistence root) + **`CATEGORIES`**
  ClassVar. 순회 헬퍼(`_iter_leaves`)만 데이터모델이 소유하고, **전이·병합·영속 I/O 는 [`store_io`](data/store_io.py)
  자유함수**가 store 를 받아 수행한다(데이터모델은 I/O 를 모름). 서브클래스는 CATEGORIES 만 고정:
  `Dataset_Meta`=`META_STATES`, `Sample_Set`=split(보류).

**흩기 / 모으기 — 두 구조 연산** (`store_io` 자유함수). leaf payload 는 `Data_Ref` → `handler` 위임,
차이는 **트리 레이아웃**뿐.

| 연산 | 하는 일 | 언제 |
|---|---|---|
| `store_io.Scatter(s)` / `Save_item(s, key)` | **흩기** — 전체(top+전 사이드카) / 항목 하나(증분) 구조 사이드카로 | 수정 시 |
| `store_io.Gather(s, categories)` | **모으기** — 흩어진 항목을 모아 자기완결 번들 한 파일로 | hand-off |

증분 저장이 `store_io.Save_item(s, stem)` 로 first-class 라 "하나 바뀌었다고 전체 내보내기" 없이 **실시간
편집**. flow resolve 는 `Bucket_Store.Iter_refs` + `handler` **직접**(payload Load/Save).

### `handler/` — Data_Ref 실체화

`Data_Ref.type` → 핸들러(image/array/attr/rle/segmap). `Load`(→값)/`Save`(→파일)/`Copy`/`Move`/`Delete`.
구조 사이드카(`type="stem"` 서브트리 JSON)는 `handler.Structure` 가 소유(`{root}/.meta/{stem}.json`).
schema·process(resolve/route)가 공유하는 payload/구조 I/O 게이트.

---

## process — 정본 계산 (frame 축)

- **process 유닛** — stateless 작업 단위(config = `@dataclass` 필드 + 주입 모델 핸들, 작업 state 는 ctx).
  `Base_Process` 계약: `Run` 구현 + `OUTPUTS` 선언, `__call__`(베이스)이 실행 → 검증 → slot 재배선.
- **Flow** — process 체인(callable). `Dataset_Meta` 위를 **frame 축**으로 순회하며 chain 을 실행하고,
  선언된 출력만 라우팅한다. flow 종류는 코드 preset 이 아니라 **config 가 직접 기술**.
- **데이터 2 스코프** — transient(`ctx`, 호출 끝 소멸) / persistent(`Dataset_Meta`). **resolve**(입력:
  persistent → `handler.Load` → ctx) / **route**(출력: 선언 키만 `handler.Save`). flow 간 데이터는 오직
  `Dataset_Meta` 경유(앞 flow 가 route 한 키 = 뒤 flow 가 resolve 하는 입력).
- **모델 주입** — 무거운 prediction 모델은 process 소유가 아니라 **`Pipeline` 이 모듈 전역 dict 풀에서
  빌드해 주입**(같은 스펙은 세션당 1회).

상세(계약·slot 재배선·라우팅 스키마)는 [`process/README.md`](process/README.md).

---

## sample — 파생 (sample 축)

`data/sample`. staged `Dataset_Meta` 를 소비해 task별 학습셋(train/val/test)으로 파생하는 계층. **task
마다 sample 구조가 다르다** — classification 은 `{split}/{class}/{sample}`(class 폴더로 한 계층 더),
COCO detection 은 `{split}/{image}/{object}` + split 별 manifest. 이 depth 차이는 flat `Data_Ref` 가
공짜로 흡수하고(stem 임의 중첩), task 별로 변하는 건 **트리 배치(`Place`)와 집계 export(`Finalize`)뿐**
— `Base_Sampler` 뼈대가 staged 순회·split 결정적 배정을 소유한다(`converter`↔`Convert` 대칭). class→정수
`id_map` 도 이 계층 소유(정본은 class 이름만). 상세는 [`data/sample/README.md`](data/sample/README.md).

---

## 바인더 — Pipeline (단일, 계산 오케스트레이션)

`core` 자체가 pipeline 이다. **하나의 slim `Pipeline`** 이 정본(`self.meta`)을 들고 **계산 단계**를 조율한다:

```text
Convert → Run → [staging 전이는 meta] → (Sample) → Verify
```

- **`Convert`** — raw → modified 에 stem 컨테이너 등록(`converter` + `store_io.Scatter`).
- **`Run`** — flow 시퀀스를 meta 위에서 구동(process 체인, frame 축) + `store_io.Scatter`.
- **`Sample`** — 이름 붙은 tasker 재생성(`Sample(name, cfg)` → `Sample_stage(staged meta)` → `Sample_Set.Scatter`
  → `taskers.yaml` 등록). `{root}/sample/{name}`, crop 체인 있으면 실체화.
- **`Verify`** — 품질 검수(선택적). 미구현.
- 무거운 prediction 모델은 **클래스 dict 풀**(`Pipeline._RESOURCE_POOL`)로 공유(프로세스 수명, 인스턴스
  공유 — GUI 가 실행마다 새 바인더를 만들어도 재사용).

**데이터 라이프사이클**(staging 전이·병합·내보내기 `Move`/`Delete`/`Merge`/`Gather`)은 바인더가 아니라
`data` 계층 **`store_io` 자유함수**가 수행한다(데이터모델 `Bucket_Store` 는 I/O 를 모른다) — 호출 측
(GUI 등)이 `store_io.Move(meta, …)` 등을 직접 부른다.

---

## 구현 상태

- **횡단** — `typing.py`(`Arg_Info`/`Arg`/`BBOX`/`GRAY_IMAGE`)·`constant.py`(`META_STATES` …) 안정.
- **`data/`** — 완료(store). `schema`(flat `Data_Ref` + forest `Bucket_Store` + stateless 재귀 헬퍼)
  · `handler`(payload I/O+RLE + `Structure` 구조 사이드카) · `meta`(정본 `Dataset_Meta` + 영속 `Scatter`/
  `Save_item`/`Gather`/`Load` + 전이 `Move`/`Delete`/`Merge`) · `sample`(파생 `Sample_Set` store만).
- **`process/`** — 완료. `Base_Process` 유닛 + **`Stage` 엔진**(source→체인→sink) + Run(`Flow`=`Frame_source`/
  `Meta_sink`) + 모델 풀. source/sink 계약은 `source.py`/`sink.py`.
- **`converter/`·`sampler/`** — 완료. process 기반 top-level 스테이지 — Convert=`Raw_source`/`Register_sink`,
  Sample=`Staged_source`/`Sample_sink[task]`(classification/detection, split 결정적 배정, crop 실체화, `id_map`).
  이름 붙은 tasker(`sampler/tasker.py` + `taskers.yaml`).
- **`_base.py`** — 완료. slim `Pipeline`(Convert→Run→Sample→Verify) + `self.meta` + tasker API
  (`Taskers`/`Sample(name,cfg)`/`Load_sample`/`Delete_tasker`), 모델 ClassVar 풀. `import core` 동작.
- **`gui/`** — 완료(코드). flat 스키마 전면 마이그레이션 + `gui/sampler`(tasker 빌더 + sample 뷰어, class
  write-back). offscreen 구성·핵심 흐름 검증, 실제 데스크톱 런타임은 미확인.
- **보류/다음** — `Pipeline.Verify` + `analysis/` 흡수, detection crop/재배정 GUI, GUI 데스크톱 런타임
  검증. 잔여 체크리스트는 [`TODO.md`](TODO.md).
