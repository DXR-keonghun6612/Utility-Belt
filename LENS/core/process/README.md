# process

process 유닛들과, 그걸 잇는 flow(체인 엔진)를 담는 패키지. `__init__`이 레지스트리·조립
(`PROCESS_REGISTRY`/`Build_process`/`Build_flow`)을, `_base.py`가 기본 구조
(`Base_Process` + Flow callable)를, 하위 패키지(preprocess/mask/edge/chroma/model/utils)가 구현을 갖는다.

flow — process 들을 잇는 한 체인. dataset 위를 순회하며 chain을 실행하고 결과를 선언된
것만 `dataset_meta`로 남긴다. callable — chain·`unit` 등 config는 dataclass 필드로 묶고
호출은 stateless다. flow는 config 의 step 목록으로 `Build_process` 가 만든 process 인스턴스를
들고, 무거운 모델은 pipeline 이 빌드해 주입한다(소유는 pipeline).

상위 구조·용어는 [`../README.md`](../README.md), 데이터 계층은
[`../dataset/README.md`](../dataset/README.md).

---

## 책임 — 조립 + 순회 + 라우팅, 그게 전부

```
resolve params        → params_ctx              (순회 전 1회)
for frame in dataset:
    resolve frame.info → frame_ctx = params_ctx + …   (프레임당 1회, leaf 만)
    for unit in units(frame):                          # unit=frame은 1회 / unit=object는 객체(stem)마다
        resolve unit.info → ctx = frame_ctx + …        (객체당 1회, leaf 만)
        run chain(ctx) using processes
        route(declared outputs)  → dataset_meta
    carry ← 다음 프레임으로 이월할 ctx 키 (있으면)
finalize(carry) → route                                (순회 후 1회)
```

flow는 순회 상태를 인스턴스에 남기지 않는다 (carry 누산도 `__call__` 지역 변수). process
인스턴스는 `Build_process` 가 config 에서 만들고, 무거운 모델은 pipeline 이 빌드해 주입한다 —
flow는 chain 정의(순서·step별 outputs)와 순회 구조만 안다.

---

## 데이터 = 2 스코프 (단일 게이트)

| 스코프 | 사는 곳 | 수명 |
|---|---|---|
| transient | `ctx` | `__call__` 소멸 (step↔step, 누산기 포함) |
| persistent | `dataset_meta` | 블록·실행을 넘어 생존 |

- resolve(입력) — persistent → ctx, 불변인 가장 넓은 스코프에서 1회. 안쪽 루프에서
  반복 로드 금지(프레임 이미지를 객체 수만큼 다시 안 읽음). `handler.Load` 위임 + ready-to-use
  형태로 정돈(디코드·도메인 객체 재구성) → process는 `Data_Ref`가 아니라 값만 본다.
- route(출력) — ctx 값 중 선언된 키만 persistent로. 미선언은 ctx에 머물다 소멸.
  `handler.Save` 위임 (위치/타입만 flow가 정함).

scope는 변수 속성이 아니라 라우팅 됐는가의 결과다. 누산기 같은 transient도 라우팅하면
storage로 남는다 — `route`가 그 승격 게이트다.

### route spec (출력키 → 라우팅)

```
{to: "meta"|"storage", level?: "frame"|"object", dir?, format?}
```

| 대상 | 핸들러 호출 |
|---|---|
| `meta` (인라인) | `handler.Save(root, stem, key, Data_Ref(type=rle/attr…), val, obj_id=…)` |
| `storage` (파일) | `handler.Save(root, stem, key, Data_Ref(type=image/array, dir, format), val, obj_id=…)` |
| dataset-wide (params) | `stem=None` (위치 없음) |

`level=frame`→`obj_id=None`(frame.info) / `level=object`→`obj_id`(객체 stem 의 info).
구 `_route`의 (to×level×타입) 분기가 전부 `handler.Save` 인자 구성으로 수렴한다.

라우팅 규칙 (`source[key]` 값·spec 기준):

```
[frame]    to=meta,    ndarray(2d), level=object → object.info[key] = rle 인라인
[frame]    to=meta,    ndarray(2d), level=frame  → frame.info[key]  = rle 인라인
[frame]    to=meta,    list/scalar               → (level) info[key] = attr 인라인
[frame]    to=storage, ndarray,     level=object → object.info[key] = image/array (파일)
[frame]    to=storage, ndarray,     level=frame  → frame.info[key]  = image/array (파일)
[finalize] to=meta,    ndarray                   → params[key]      = array(npy)
[finalize] to=meta,    스칼라/list/dict           → params[key]      = attr 인라인
[finalize] to=storage                            → params[key]      = (Infer_type) 파일
"object" list (per-frame)                        → frame.info 객체(stem) 교체 (obj_id=순번; leaf 보존, spec 무관)
```

`source[key]` 는 `Run` 출력을 slot 재배선한 뒤의 값이라, 표의 `key` 는 재배선된 slot 이름이다.
finalize step 은 frame/obj 위치가 없어 항상 params(dataset-wide)로 간다.

---

## process — config 가 빌드, 모델은 pipeline 이 주입

- stateless: config(=`@dataclass` 필드) + 주입된 모델 핸들만. 작업 state는 ctx에 있어 process엔 없다.
- 인스턴스는 `Build_process(name, param)` 이 레지스트리에서 만든다 (flow가 step config로 호출).
  무거운 prediction 모델은 process 소유가 아니라 pipeline 의 dict 풀에서 빌드해 주입한다
  (같은 스펙은 한 번만 빌드해 공유 — [`../README.md`](../README.md) 수명 모델).
- `class X(Base_Process, outputs=…)` — 서브클래스는 `Run` 을 구현하고 OUTPUTS(=산출 port)를 선언한다.
  `__init_subclass__` 이 OUTPUTS 주입 + INPUTS 자동추출(`Run` 시그니처), `__call__`(베이스 소유)이
  `Run` 실행 → OUTPUTS 검증 → port→slot 재배선의 계약 프레임이다. 등록은
  `@PROCESS_REGISTRY.Register_module()` 명시(`target_type=Base_Process` 하위 클래스만 통과).

### slot 재배선 — 출력 port ↔ ctx slot

step 출력 키(port)는 기본적으로 그대로 ctx slot 이 돼 다음 step·다음 flow 의 입력 이름이 된다.
step config 의 `slots: {port: slot}` 로 특정 출력을 다른 slot 으로 보낼 수 있다(미선언 port=identity).
`_build_chain` 이 인스턴스별로 `output_slots` 에 주입하고(미선언 port 를 slots 로 쓰면 빌드 시 KeyError),
`__call__` 이 `Run` 결과를 검증 후 재배선한다. 같은 process 를 여러 번 써도 slot 을 달리해 충돌을 피한다 —
예: `fill_edge` 를 `slots: {mask: other}` 로 재배선해 `combine_mask` 의 `other` 입력에 잇는다. 재배선 뒤
키가 이후 `outputs` 라우팅·`carry`·다음 step 입력의 이름이 된다(=slot 이 진실).

입력쪽 대칭은 `inputs: {param: ctx_key}` — ctx 키 이름이 `Run` 파라미터명과 다를 때 별칭으로 읽는다
(producer 없이 ctx 에 얹힌 값, 예: params `roi` 를 `combine_mask` 의 `mask` 로: `inputs: {mask: roi}`).
`_build_chain` 이 `input_slots` 로 주입(미선언 파라미터를 쓰면 빌드 시 KeyError), `__call__` 이 `Run`
호출 전 kwargs 를 remap 한다. `slots`(출력 rename) 없이 안 잡히는 "이름만 다른 입력"을 잇는 자리.

---

## carry / finalize — 누산의 두 조각

- `carry` — 프레임 간 이월할 ctx 키. 런타임 수명 도구일 뿐 state도 영속도 아니다
  (누산기 `c0_acc`는 ctx에 살다 `__call__`과 함께 죽는다).
- `finalize` — 순회 후 1회 도는 체인. carry 누산기(scope-1)를 받아 통계(scope-2)로 바꾸는
  다리. 누산기가 `__call__`과 함께 죽으니 같은 호출 안에서 변환해야 해 존재한다.
- per-frame `processes`와 `finalize`는 같은 체인 엔진이고 차이는 *도는 시점*뿐 —
  라우팅도 동일한 인라인 `outputs`로 통일됐다. `finalize` step은 frame/obj 위치가 없어 `_route`가
  자동으로 params(dataset-wide)로 보낸다. 누산기 자체는 어느 step의 출력도 아니면 영속되지 않는다.

---

## 패키지 구성 / flow 종류

```text
process/
├── __init__.py            PROCESS_REGISTRY · Build_process · Build_flow + 유닛 등록
├── _base.py               Base_Process(계약: Run/__call__)/UI/types + Flow callable + ref 헬퍼
├── presets.example.yaml   flow config 작성용 템플릿 (코드가 읽지 않음 — 복붙 참고용)
├── preprocess/            전처리 — crop(크롭) · color(색보정)
├── mask/                  마스크 — threshold(이진화) · cleanup(정리) · separate(분리)
├── edge/                  엣지 — canny(탐색) · edge(기본: 닫기·채우기·blob)
├── chroma/                색공간 — convert_to/distance/accumulate/robust_stats + _space/_core
├── model/                 모델 — segment(SAM3 분할) + _sam3 런타임
└── utils/                 공유 마스크 유틸
```

디렉토리 = CATEGORY 대분류, 파일 = 중분류. 새 process 는 해당 대분류 폴더의 중분류 파일에 더한다
(탐색법처럼 늘어나는 축은 파일로 분리 — 예: `edge/canny.py`). 각 대분류 폴더의 `README.md` 에
그 안 process 들의 알고리즘 배경을 둔다.

flow 종류는 subclass도 코드 preset도 아니라 config가 직접 기술한다 — `object_type`(라벨),
`unit`(frame/object), `processes`/`finalize_processes`, `carry`, `cacheable`, `shared` 를 config에서
채운다. `Build_flow(cfg)`가 그 dict로 단일 `Flow`를 만든다. 복붙용 예시는
[`presets.example.yaml`](presets.example.yaml) (chroma 배경모델 global/pixelwise). 색공간 `space`
처럼 흐름-공유 값은 제네릭 `shared` dict 로 빼 `_build_chain`이 각 step에 주입한다(선언 키만 받음).

---

## 현재 상태

재설계 완료 — handler 위임 resolve/route, `Base_Process`(`@dataclass`+`__init_subclass__`), 단일 `Flow`
callable, 코드 preset 제거(flow는 config 직접 기술), 라우팅 통일(인라인 `outputs`), stateless process,
모델은 pipeline 이 빌드해 주입(process 는 `model` 핸들만). 잔여 작업은 [`../TODO.md`](../TODO.md).
