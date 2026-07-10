# TODO — core (잔여 작업)

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 남은 것만.

---

## ▶ 진행 중 — process 재편 마무리

- [ ] **README 정합** — `core/README.md:175` 가 `analysis/` 흡수를 아직 "보류/다음"으로,
      `gui/README.md:86` 이 `meta_page/verify/` 를 서술한다. (`process`/`stream`/`func` README 는 완료.)
- [ ] **개념 폴더 README 재검토** — `stream/{chroma,model,select}/README.md` 만 남았다. 계산이 `func/`
      로 내려간 지금 이들도 소멸 가능한지 확인 — chroma 파이프라인 순서는 config 몫, `빈 dict=스킵`
      관례는 `Base_Process.__call__` 몫, 모델 주입 설명은 `process/README` 와 중복.

---

## ✅ 합의됨 (진행 전)

### 결과/디버그 분리

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

**방향.**
- **선언 위치가 의미를 정한다** — `process` 에 붙은 `outputs` = **디버그**(관찰), `flow` 에 붙은 `outputs`
  = **결과**(산출 계약). 키 이름·spec 스키마는 **양쪽 동일**하고, 구현은 재귀적으로 같은 spec 객체를
  공유한다(양쪽이 서로 다른 인자를 가질 필요 없음).
- **목적지도 갈린다** — 결과는 정본 버킷, 디버그는 별도 root(전이·병합 대상 아님, 통째 삭제 가능).
- **원칙** — flow 의 결과는 flow 가 선언한다. step 은 자기가 무엇을 계산했는지(port)만 말한다.
  영속은 계약이고 관찰은 부산물이다.

따라오는 것: `segment` 이중 write 소멸, `cacheable` 이 per-frame 결과까지 판정 가능(현재는 finalize
출력 키로만), `object: {}` 제거. Phase 2 와 같은 지층 — 세부 계획은 착수 시 작성.

### Phase 2 — 계약 변경 (유닛 본문)

- [ ] wiring 소유자 이동 — remap(`input_slots`)·OUTPUTS 검증·slot 재배선을 `Base_Process.__call__` 에서
      떼어 **`Stage` 엔진 체인 루프**로. 유닛은 순수 `Run`(+config)만.
- [ ] 출력 선언 대칭화 — `outputs=` 튜플 제거, `Run` **반환 어노테이션**(TypedDict/Ports, 이름+타입)에서
      OUTPUTS 유도(입력과 대칭). `{}`(스킵 관례)는 "출력 없음"과 구분해 보존.
- [ ] 입출력 포트가 시그니처만으로 타입까지 확보 → block+wiring(노드 그래프, gui/TODO B3) 준비 완료.

### stream 유닛의 store 직접 접근 제거

- [ ] `mask/order.py:33`·`model/segment/_base.py:60` 이 `meta.Find(stem)` 으로 store 를 뒤진다. 유닛의
      일탈이 아니라 `Meta_block.context`(`source.py:126`)가 ctx 에 store 핸들을 넣기 때문 — **source 가
      객체 목록을 ctx 로 resolve** 하도록 계약을 바꿔야 사라진다. (열린 질문: 재실행 시 객체를 어디서
      얻나 — 앞 step 의 ctx `object` vs source resolve.)

### Verify

- [ ] `Pipeline.Verify` 를 `staged` 위 Stage 로 구현. **두 종류를 다 소비** — per-stem check(`stream/`,
      `Base_Process` → pass/fail route) + 데이터셋 진단(`analysis/`, report/figure). 현재 `NotImplementedError`.

### 부채

- [ ] **`analysis/chroma` 의 vestigial `window`** — 옛 mode-window 추정기의 잔재. `Robust_mean_std` 는
      받지 않는데 `stats.py`·`analyze.py`·`_result.py` 가 여전히 인자로 나른다. 호출 크래시는 고쳤으나
      **지금은 조용히 무시된다.** report 까지 걷어내야 한다.
- [ ] **`meta/test_dataset.py`** — `test_meta_merge_*` 가 옛 kwarg(`modified=`/`staged=`)로 `Dataset_Meta`
      생성 → 지금은 `buckets=` 뿐이라 **깨짐**. `buckets=` 로 고치고 3-state(skipped) 반영, 상단 낡은
      namespace stub 제거. **여기에 라이프사이클(Convert→Run→Verify→Gather→학습)을 흡수** — 지금 그 흐름은
      `meta/README.md` 산문으로만 있다(워크플로는 테스트가 소유해야 함). 테스트가 생기면 README 는 가리키기만.
- [ ] **`store_io.Merge` params 별칭 비대칭** — 항목은 깊은 사본(`Data_Ref(**_item.Serialize())`)인데
      params 는 `other` 의 ref 를 그대로 대입(`store.params[_name] = _ref`)한다. `other` 를 버리는 통상
      사용엔 무해하나, 재사용하면 두 store 가 같은 ref 를 공유해 조용히 얽힌다. params 도 깊은 사본으로 통일.
- [ ] **라벨맵 `uint8` 한계** — `func/mask/instance.py` 의 `segment` 와 재라벨 LUT 가 `uint8` 이라
      인스턴스 255개를 넘으면 **조용히 wrap** 한다(numpy 1.26 은 `DeprecationWarning` 만). `uint16` 승격
      여부는 `segmap` 핸들러의 PNG 저장과 얽힘.
- [ ] **`LENS/analysis/` 잔재** — 패키지는 `core/process/analysis/` 로 이사했고 `temp_*.py` 3개만 남았다.
      기능별 병합용 임시 스크립트 — 흡수하거나 옮길 자리를 정한다.
- [ ] **`excluded` 큐레이션 영속** (A+ = 순수 재생성 + 솎아내기).
- [ ] **GUI end-to-end 런타임 검증** — 코드·import·offscreen 검증됨. 실제 데스크톱에서 Convert→Run→전이→
      Sample→뷰어 흐름 확인.

### 미구현 기능

- [ ] coco/yolo 포맷 converter (glob 외 직접 파싱 경로).
- [ ] `process/_base` 데코레이터·라우팅 단위 테스트.
- [ ] detection COCO manifest 에 bbox/segmentation 채우기 + detection crop/class 재배정 GUI.
- [ ] chroma n채널 일반화(주목적 RGB) — 현재 2채널 고정(명도 버림). `ChromaSpace` channels/bins/circular/
      labels 를 length-n 으로, 누산·통계 키를 per-channel(`c0_acc`/`mean_c0`)에서 배열 단일 키(`chroma_acc`/
      `mean`/`std`)로 재설계. 기존 config 키 마이그레이션 필요.

---

## ❓ 논의 대상 (정책·구조 미정)

- [ ] **재-convert 덮어쓰기/교차상태 중복** — `Register_sink` 가 무검사로 modified 에 등록 → 기존
      modified 덮어씀 + staged/skipped stem 도 재등록(one-stem-one-state 위반). **합의된 정책 없음.**
      상세 [`converter/README.md`](converter/README.md) "⚠ 논의 필요".
- [ ] **`_sam3.py` 의 자리 + 소비자의 깊은 직접 import** — `core/_base.py:30` 이
      `process.stream.model._sam3.Sam3_runner` 를, `gui/…/edit/_fill.py` 가 `process.func.cv.filter.log_edges`
      를 내부 모듈로 깊게 당긴다. `_sam3` 는 **상태를 든 런타임**이라 스트리밍 유닛도 자유함수도 아니다 —
      계층이 하나 부족하다는 신호. 모델 런타임의 자리 + `func` primitive 의 공개 경로를 함께 정한다.
- [ ] **id_map 위치** — id_map 은 detection tasker(sample) 소유인데 `gui/meta_view` 가 아직 빈 `{}` 를
      로드하는 vestigial `Idmap_panel` 스텁을 갖는다. meta view 에서 제거하고 sampler 뷰어로 옮길지 결정.
