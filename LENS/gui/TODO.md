# TODO — gui/

dataset_meta 중심 — 보유 `Pipeline` 하나(meta 단일 소스), 본문은 stem 목록(3-상태 뱃지 작업/검수/보류)과
임베드 `Stem_editor`, id_map/params. Converter·flow·Sampler 는 비모달 창. 전이/삭제는 백그라운드.
구조는 [`README.md`](README.md).

완료 이력은 git. 여기엔 남은 것만 — **A. 전면 구조 리팩**(코드 정리) → **B. UI 확장**(제품 방향).

---

## A. 전면 구조 리팩 (W1–W4)

**진단.** 공유 인프라(`widgets`/`form`/`_worker`/`_io`/`_meta_tree`)는 이미 잘 정리됨 — `Pop_dialog`(5곳)·
`List_editor`(converter/run)·`Config_form`/`_Model_form`(flow_card)·`Pipeline_worker`(3곳)·`make_tree` 재사용
중, 복붙 중복 대부분 제거됨. 남은 냄새는 ① process-chain 편집이 `run/` 에 갇혀 sampler 가 몰래 씀 + step
관리 중복 ② `run/_flow_card.py` 807줄 모놀리스 ③ 오케스트레이션 파일(`page/_main` 454·`verify/_editor`
598) 비대 ④ 문서 drift. **순서: W1 → W1문서(W4일부) → W2 → W3.**

### W1 — process-chain 편집을 공통 모듈로 승격 (최우선)
`Process_step`·`_Process_picker`/`_Process_popup`·`_Outputs_editor`/`_Output_row` 가 전부 `run/_flow_card.py`
에 살고, `sampler/_dialog` 가 `from gui.run._flow_card import Process_step` 로 **레이어 위반**. step 관리
(`_add_step`/`_remove_step`/`_move_step`)가 `Flow_card`·`Sampler_dialog` 양쪽에 거의 동일 중복.

- [ ] 중립 모듈 **`gui/steps/`** 신설 — 소유: `Process_step`(picker+`Config_form`+`_Model_form`+outputs)·
      `Process_picker`(+popup)·`Outputs_editor`(+row)·**`Step_list`** 컨테이너(add/remove/move/reorder +
      min-count 정책 `min=`·finalize 모드 캡슐화).
- [ ] `run/_flow_card.py`(807→~250) 를 **Flow_card 조립만**(header/shared/carry + `Step_list` 2개: per-unit·
      finalize)으로 축소.
- [ ] `sampler/_dialog.py` 를 `Step_list` 소비로 전환 — hand-rolled step 관리 제거, run 私모듈 import 제거.
- [ ] `gui/steps/README.md` + `run`/`sampler` README 갱신(모듈 이동 반영).

> 대안 위치: `gui/form/_step.py`(Process_step 이 form 을 조합하니). 단 `PROCESS_REGISTRY` 의존이 붙어
> 별도 `gui/steps/` 가 더 깔끔 — 착수 시 확정.

### W2 — recipe-builder 다이얼로그 스캐폴드 (선택 — W1 후 재평가)
converter/run/sampler 셋 다 `Pop_dialog` + recipe(dict) 저장/불러오기(`_io`) + Pipeline stage 구동
(converter·sampler self-run `Pipeline_worker`, run 은 메인 위임). 공통은 얇음("save/load recipe + Pop_dialog").

- [ ] 이득 검토 후 얇은 `Recipe_dialog(Pop_dialog)` 베이스로 저장/불러오기·`to_config`/`load_config` 계약
      통일(+선택적 worker-run helper). 본문 shape 이 달라 payoff 얇으면 보류.

### W3 — 오케스트레이션 파일 분해
- [ ] `page/_main.py`(454): 핸들러가 (a)자식 다이얼로그 opener (b)worker/전이/삭제 (c)meta import/export/
      clear 로 뭉침 → **meta 라이프사이클 핸들러를 helper 로 분리**해 `Main_page` 슬림화.
- [ ] `verify/_editor.py`(598): 이미 `_draw`/`_annotation`/`_history` 위임 중 — undo/redo/snapshot 클러스터를
      `_history` 에 더 실어 축소. 응집도 높아 **우선순위 낮음**.

### W4 — 문서·네이밍 정합
- [ ] `store_io` 표기 정정 — `meta_view/README`·`verify/README` 의 `meta.Move`/`meta.Save_item`/`meta.Delete`
      → `store_io.*(meta, …)` (R2 반영; gui/README 는 이미 갱신됨).

---

## B. UI 확장 — 1과정 특화 → 2산출물 · 3과정 (제품 방향, 설계 단계)

**동기.** 지금 UI 의 중심은 정확히는 "**Dataset_Meta 데이터의 편집**" 하나다. 하지만 결과적으로 만들어지는
**산출물은 둘 — `Dataset_Meta`(정본) + `Sample`(파생)**. Sample 은 현재 `sampler/_viewer` 로 **단순 표시**만
하고, 빌드 3과정(Convert·Run·Sample)은 메인 버튼에 매달린 비모달 창으로 흩어져 있다. → 두 산출물을 나란한
편집 대상으로, 3과정을 직관적 흐름으로 승격한다.

### B1. 산출물 관점 재정의 — 편집 대상 = Dataset_Meta + Sample
- [ ] 메인을 "meta 편집" 단일 중심이 아니라 **두 산출물(정본·파생)** 을 오가는 구조로 재정리. meta 중심은
      유지하되(정본이 기준), Sample 을 **표시 전용이 아닌 제1 편집 산출물**로 격상. 3과정(Convert/Run/Sample)
      은 정본→파생 흐름의 단계로 노출(구체 패러다임은 아래 열린 질문).

### B2. Sample 편집 윈도우 확장 (현재 display-only → editable)
- [ ] `sampler/_viewer` 를 뷰어에서 **편집 surface** 로 확장 — 별도 윈도우. 현재 유일 편집인 class 재배정
      (정본 write-back)을 넘어 sample 산출물 자체를 다룰 수 있게.
- [ ] sample-local 큐레이션(정본 write-back 아님) 스코프 확정 — 예: "**학습셋에서 빼기(exclude)**"(현재
      미구현, README 언급). 정본 편집과 sample-local 편집의 경계를 UI 에서 명확히.

### B3. Sample 데이터 모델 — 입력(기준) vs 라벨(연동) 구분
Sample 항목을 두 성격으로 가른다:

- **입력 데이터(input)** — 생성되면 **기준(baseline)**. 불변 (예: crop 픽셀은 class 무관하게 고정). 재-crop
      없이 산출물로 굳는다.
- **라벨 데이터(label)** — 정본에 **연동(sync)**. 수정 가능하고 write-back 으로 정본에 반영 (예: `class_id`
      인라인 attr → `source_stem`/`source_obj` 역참조로 정본 obj 갱신).

- [ ] 편집 윈도우(B2)에서 이 둘을 **명시적으로 분리** — 입력은 고정 참조로 보이고, 라벨은 편집·연동 레이어로.
- [ ] 데이터 모델 지지 검토 — 현재 `Data_Ref` 트리에서 입력/라벨 성격이 암묵적(crop=payload, class_id=attr).
      **core/sample 스키마에 input/label 구분을 명시**할지 판단(연동 방향·정본 write-back 계약 포함).
      → core 파급 가능성 있는 항목이라 착수 전 core 쪽과 함께 설계. cf. [[project_sample_tasker_layer]].

### 열린 설계 질문 (B 착수 전 확정)
- [ ] **UI 패러다임** — 3과정+2산출물을 어떻게 노출하나? meta 중심 유지가 전제. 후보: 상시 패널/사이드바 vs
      단계 네비. (사용자: "중심은 meta 편집이 맞다" — 급격한 stepper 전환은 아님.)
- [ ] Sample 편집 윈도우와 메인 meta 뷰의 **동기화 계약** — 라벨 write-back 시 `meta_changed` 전파(현
      `sampler/_viewer` 방식) 확장.
- [ ] 입력/라벨 구분이 classification 외 task(detection 등)에서 어떻게 매핑되나 (입력=image·라벨=bbox/mask).

---

## C. 기존 후속 기능 (소품)

- [ ] Run "중단" 협조적 처리 — `Pipeline.Run` 이 stop flag 를 받도록 core 보강 (현재 없음)
- [ ] `shared` dict 값 타입 보존 (현재 문자열만 입력됨)
- [ ] 새 converter 타입(coco/yolo 등) UI — `_CONVERTER_WIDGETS` 등록
