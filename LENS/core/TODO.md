# TODO — core (잔여 작업)

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 남은 것만.

---

## ▶ 진행 중 — process 재편 (종류 우선) + analysis 흡수

**동기.** `process/` 가 **엔진**(Stage/source/sink)과 **연산 유닛**을 한 층에 섞고, 유닛은 한 종류
(스트리밍 `Base_Process`)뿐이다. 그런데 (1) `analysis/`(별도 `Analysis` 계약 — 집계→report/figure)를
`process` 로 흡수해야 하고, (2) 도메인 간 누수(edge 폴더가 mask 연산을 품음, `chroma`·`edge` 가
`utils.mask` 를 당김)가 쌓였다. → **연산 종류**를 한 층 더 세워 정리한다.

**확정 구조 — 종류 우선(stream / analysis) + 공유 primitive(func).** (Phase 1 완료·검증)

```
core/process/
├── _base.py source.py sink.py __init__.py   ← 엔진(그대로)
├── stream/     종류1: Base_Process (순수 도메인 함수)
│   ├── preprocess/ mask/ filter/ chroma/ model/ select/
├── analysis/   종류2: Analysis (top-level analysis/ 흡수)
│   ├── _base.py(Analysis·ANALYSIS_REGISTRY·present) · chroma/ · mask/(area,shape)
└── func/       primitive(연산 아님) — cv/{filter,geom} · chroma/{_core,_space} · mask/{fill,polar,instance}
```

**규칙 — 순수 도메인 함수.** 프로세스는 **연산(=출력)의 도메인**에 속한다(입력은 어느 도메인에서
와도 됨 = 데이터흐름). `stream/<domain>` 유닛은 `func/<domain>` + generic(`func/cv`)만 import,
**다른 도메인 func 금지**. 조합(combine/gate)·wiring 은 유닛이 아니라 엔진/config 몫.

**결정(합의).**
- import 는 **상대 dot** 유지. `stream/__init__` 이 엔진 계약(`Base_Process`/`UI`/`BBOX`/`GRAY_IMAGE`)을
  재노출해 유닛 import 를 얕게(`from .. import …`). (`func/` 는 표준 gitignore `lib/` 충돌 회피 개명.)
- registry 등록명은 **클래스 데코레이터 기반** → 유닛을 다른 모듈로 옮겨도 config `object_type` 무변경.
- `temp_*.py` 3개(기능별 병합용 임시)는 **손대지 않음**.

### Phase 1 — 이동·재배치 (완료: import·등록 스모크 + gui/analysis compile 검증. 커밋 대기)
- [x] `stream/`·`analysis/`·`func/` 트리 구성 (top-level `analysis/` 흡수, `temp_*.py` 잔류).
- [x] `utils/` → `func/{cv,chroma,mask}` 해체 — cv/filter(morph커널·LoG·hysteresis·면적·윤곽) ·
      cv/geom(roi변환·crop/pad) · chroma/{_core(+`_robust_mean_std`)·_space} · mask/{fill·polar}.
- [x] 도메인 개명·재분류 — `edge/`→`filter/`, `Fill_edge`·`Edge_blob`·`Remove_edge_holes`(연산=mask)
      → `stream/mask/from_edge.py`, `log_edges`→`func/cv/filter`.
- [x] 유닛 import 일괄 전환(stream 재노출 + func 경로) + analysis 스테일 4곳(`core.pipeline.*`) 수리.
- [x] GUI — `meta_page/verify/`→`edit/` 개명(뷰 `view/` 와 짝), vestigial `gui/verify/` 삭제,
      `sample/_tab.py`·`edit/_fill.py` import 재지정.
- [x] **stream 계산 추출** — 유닛 몸통의 순수 계산을 `func/` 로 내리고 근거 docstring 동반 이관.
      stream 1335→1019줄 / func 641→1397줄(역전). 신설: `func/cv/color`, `func/mask/{instance,combine,
      enclosure,flood}`. 옛 구현 대조로 동작 동일성 확인(무작위 config 수천 건). 서랍 README 3개
      (`mask`·`preprocess`·`filter`) 소멸 — 설명할 것이 남지 않음.
- [ ] **잔여: README 정합** — `core/README`·`gui/README` 가 구 구조(analysis 외부·verify) 서술 →
      갱신 필요. (`process/README`·`stream/README`·`func/README` 는 완료.)
- [ ] **개념 폴더 README 재검토** — `stream/{chroma,model,select}/README.md` 만 남았다. 계산이 내려간
      지금 이들도 소멸 가능한지 확인 — chroma 파이프라인 순서는 config 몫, `빈 dict=스킵` 관례는
      `Base_Process.__call__` 몫, 모델 주입은 `process/README` 와 중복.

### Phase 2 — 계약 변경 (유닛 본문, Phase 1 안정 후)
- [ ] wiring 소유자 이동 — remap(`input_slots`)·OUTPUTS 검증·slot 재배선을 `Base_Process.__call__` 에서
      떼어 **`Stage` 엔진 체인 루프**로. 유닛은 순수 `Run`(+config)만.
- [ ] 출력 선언 대칭화 — `outputs=` 튜플 제거, `Run` **반환 어노테이션**(TypedDict/Ports, 이름+타입)에서
      OUTPUTS 유도(입력과 대칭). `{}`(스킵 관례)는 "출력 없음"과 구분해 보존.
- [ ] 입출력 포트가 시그니처만으로 타입까지 확보 → block+wiring(노드 그래프, gui/TODO B3) 준비 완료.

---

## ✅ 합의됨 (진행 전) — 결과/디버그 분리

**문제.** `outputs` 게이트가 세 의도를 겸한다 — (1) flow 의 **산출 계약**(다음 스테이지가 소비), (2)
**관찰용 디버그**(지워도 파이프라인이 돎), (3) `object: {}` 같은 **구조 선언**. flow 의 산출 계약이
어디에도 선언되지 않아, 무엇이 결과인지 config 를 끝까지 읽고 `dir` 겹침을 눈으로 대조해야 안다.

관측된 실해(實害):
- `extract_raw_mask_by_flood` 에서 `split_objects`·`order_objects` 가 **같은 `dir: raw_mask` 에 `segment`
  를 두 번 write** → 프레임마다 PNG 한 장을 인코딩해 버린다(뒤엣것이 덮음).
- `object: {}` 는 no-op 인데 `Template({}, [Data_Ref])` → `attr(str)` 로 **첫 객체 info 에 쓰레기를 쓴다**.
  구조 교체가 그 객체를 버려서 우연히 무해할 뿐. 구조 교체는 `spec_map` 과 무관하므로 선언 자체가 불필요.
- 디버그 산출물(`flood_mask`·`sam3_seg`)이 정본 버킷(`Category_root(MODIFIED)`)에 살아 **staging 전이 때
  정본을 따라 움직인다.** 무엇을 지워도 되는지 파일시스템에 근거가 없다.

**합의된 방향.**
- **선언 위치가 의미를 정한다** — `process` 에 붙은 `outputs` = **디버그**(관찰), `flow` 에 붙은 `outputs`
  = **결과**(산출 계약). 키 이름·spec 스키마는 **양쪽 동일**하고, 구현은 재귀적으로 같은 spec 객체를
  공유한다(양쪽이 서로 다른 인자를 가질 필요 없음).
- **목적지도 갈린다** — 결과는 정본 버킷, 디버그는 별도 root(전이·병합 대상 아님, 통째 삭제 가능).
- **원칙** — flow 의 결과는 flow 가 선언한다. step 은 자기가 무엇을 계산했는지(port)만 말한다.
  영속은 계약이고 관찰은 부산물이다.

**따라오는 것.** `segment` 이중 write 소멸, `cacheable` 이 per-frame 결과까지 판정 가능(현재는 finalize
출력 키로만), `object: {}` 제거. Phase 2(wiring 소유자 이동)와 같은 지층 — 세부 계획은 착수 시 작성.

---

## Verify (analysis 흡수 후)
- [ ] `Pipeline.Verify` 를 `staged` 위 Stage 로 구현. **두 종류를 다 소비** — per-stem check(`stream/`,
      Base_Process → pass/fail route) + 데이터셋 진단(`analysis/`, report/figure). 현재 `NotImplementedError`.

## 논의 필요
- [ ] **소비자의 process 내부 직접 import 정리 (구조)** — `core/_base.py`(Pipeline)가
      `process.stream.model._sam3.Sam3_runner` 를, `gui/…/edit/_fill.py` 가 `process.func.cv.filter.log_edges`
      를 **내부 모듈로 깊게 직접 import**한다. 잘못된 구조 — 소비자는 공개 facade/API 로만 접근해야
      (모델 런타임 노출·func primitive 공개 경로 재설계 필요). 재편 배선만 살려둔 상태, 정리는 나중에.
- [ ] **재-convert 덮어쓰기/교차상태 중복** — `Register_sink` 가 무검사로 modified 에 등록 → 기존
      modified 덮어씀 + staged/skipped stem 도 재등록(one-stem-one-state 위반). **합의된 정책 없음.**
      상세 [`converter/README.md`](converter/README.md) "⚠ 논의 필요".

## sampler / 파생
- [ ] **id_map 위치 정리** — id_map 은 detection tasker(sample) 소유인데 `gui/meta_view` 가 아직 빈 `{}` 를
      로드하는 vestigial `Idmap_panel` 스텁 보유. meta view 에서 제거하고 sampler 뷰어로 옮길지 결정.
- [ ] `excluded` 큐레이션 영속 (A+ = 순수 재생성 + 솎아내기).
- [ ] detection COCO manifest 에 bbox/segmentation 채우기 + detection crop/class 재배정 GUI.

## 정리 / 검증
- [ ] **`analysis/chroma` 의 vestigial `window`** — 옛 mode-window 추정기의 잔재. `Robust_mean_std` 는
      `window` 를 안 받는데 `stats.py`·`analyze.py`·`_result.py` 가 여전히 인자로 나른다. 호출 크래시
      (`takes 2 positional arguments but 3 were given`)는 고쳤으나 **지금은 조용히 무시된다** —
      `analyze`/`_result`/report 까지 걷어내야 한다. (analysis 재편과 함께)
- [ ] **TODO 구조화** — 항목을 `논의 대상` / `합의됨(진행 전)` / `진행 중` 세 갈래로 나눈다.
      수명이 다르다 — 논의는 답하면 README 로 승격, 합의는 착수하면 진행 중으로, 진행 중은 끝나면 삭제.
- [ ] **`meta/test_dataset.py`** — `test_meta_merge_*` 가 옛 kwarg(`modified=`/`staged=`)로 `Dataset_Meta`
      생성 → 지금은 `buckets=` 뿐이라 **깨짐**. `buckets=` 로 고치고 3-state(skipped) 반영, 상단 낡은
      namespace stub 제거.
- [ ] **GUI end-to-end 런타임 검증** — 코드·import·offscreen 검증됨. 실제 데스크톱에서 Convert→Run→전이→
      Sample→뷰어 흐름 확인.

## 미구현 기능 (future)
- [ ] coco/yolo 포맷 converter (glob 외 직접 파싱 경로).
- [ ] `process/_base` 데코레이터·라우팅 단위 테스트.
- [ ] chroma n채널 일반화(주목적 RGB) — 현재 2채널 고정(명도 버림). `ChromaSpace` channels/bins/circular/
      labels 를 length-n 으로, 누산·통계 키를 per-channel(`c0_acc`/`mean_c0`)에서 배열 단일 키(`chroma_acc`/
      `mean`/`std`)로 재설계. 기존 config 키 마이그레이션 필요.
