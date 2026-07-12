# TODO — core (잔여 작업)

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 남은 것만.

---

## ▶ 진행 중 — process 재편 마무리

- [ ] **README 정합** — `core/README.md:175` 가 `analysis/` 흡수를 아직 "보류/다음"으로 서술한다.
      (`process`/`stream`/`func` README 는 완료. gui README/TODO 는 2026-07-11 최신화 — `verify/`→`edit/`,
      `STATES`→`CATEGORIES`, `Save_item`→`Save` 정정 완료.)
- [ ] **개념 폴더 README 재검토** — `stream/{chroma,model,select}/README.md` 만 남았다. 계산이 `func/`
      로 내려간 지금 이들도 소멸 가능한지 확인 — chroma 파이프라인 순서는 config 몫, `빈 dict=스킵`
      관례는 `Base_Process.__call__` 몫, 모델 주입 설명은 `process/README` 와 중복.

---

## ✅ 합의됨 (진행 전)

### ★ core 4분할 — schema / store / port / process  (2026-07-12 합의, 이번 재편의 상위 계획)

아래 다른 합의 항목들은 이 재편의 **하위·후속**이다. 순서가 걸리는 것은 각 항목에 표시.

**목표 구조.** 계층은 하는 일이 아니라 **아는 타입**으로 갈린다.

```text
core/schema.py    Data_Ref — 순수 재귀 트리 (의존 0 · 진짜 cv2-free)
core/store/       Bucket_Store · Dataset_Meta · Sample_Set — 범주·item 주소 + 라이프사이클 API
core/port/        handler · sidecar · scan(import) · export — 실체화·외부 입출력
core/process/     engine(Stage) · stream · func — 계산
core/_base.py     Pipeline — 계산 단계 조율만
```

의존은 DAG 한 방향뿐: `schema ← {port ← store} ← process ← _base`. **`port` 는 `store` 를 모른다** —
`store.Import()` 가 `port.Scan()` 을 불러 ref 를 받아 자기가 `Set` 하고, `store.Export()` 가 `port` 에 트리를
넘긴다. 이 방향은 산문이 아니라 **import 방향 검사**로 못박는다(재배치와 함께 도입).

**왜 — 두 바퀴를 돌게 만든 오진.** `Bucket_Store` 의 `Save`/`Restore`/`Move`/`Delete`/`Merge` 는 전부
handler 를 **함수 본문 안에서 지연 import** 한다. cv2-free 를 지키려는 위장이었고, 이 어색함이 *"라이프
사이클이 store 에 있으면 안 되나 보다"* 라는 오진을 낳아 `store_io` 분리(`843975b`)→재흡수를 왕복시켰다.

- **진짜 원인은 라이프사이클의 위치가 아니라 cv2-free 의 오적용이다.** 그건 `Data_Ref` **한 모듈**의
  성질인데 `data/` **계층 전체**의 계약으로 승격시켰다. store 는 원래 영속이다 — 디스크를 알아도 된다.
- **처방은 책임 이동이 아니라 순수한 것의 승격** — `Data_Ref` 를 `core/schema` 로 꺼내면 cv2-free 소비자는
  그것만 들이면 되고, `Bucket_Store` 는 `port` 를 **top-level 로** 당길 수 있다. 지연 import 5개 소멸.
- **라이프사이클은 store 소유 그대로다**(`meta.Move(...)`). 바인더로 올리지 않는다 — 규칙은 옳았다.
  (원칙 개정: `claude-knowledge` 계층① "순수성은 모듈에 걸고 계층에 걸지 않는다" · 계층③ "`소유` = API
  표면이지 구현 위치가 아니다".)

**따라오는 것 — `converter`/`sampler` 소멸.** 셋(Convert/Run/Sample)은 `Stage` 엔진을 공유하고 양 끝만
다른데, 그 양 끝을 클래스로 세운 게 `source`/`sink` 계약이고 그 서브클래스를 담으려고 있던 폴더가
`converter`/`sampler` 다. 계약을 녹이면 **담을 게 없어 폴더가 사라진다.**

- **Convert 는 engine 을 하나도 안 쓴다** — 체인이 비고(`route` 미구현, `emit` 만), `Raw_block.context()` 는
  `{}`, resolve 도 없다. 빌려 쓰는 건 순회 루프와 진행바뿐. 하는 일은 `scan(외부) → Save → store.Set` 이라
  **계산이 아니라 store 진입 게이트**다 → `port` (`Export` 의 역함수. `Restore`/`Merge`/`Export` 의 빠진 형제).
- **Sample 은 engine 을 실제로 쓴다**(`attr_gate` 로 솎고 `frame_crop` 으로 실체화) → `process` 에 남는다.
  배치(`Sample_sink`)는 `sample_set.Place(...)` store 메서드로, `sampler/export.py`(COCO/ImageFolder)는
  `트리 → 외부 레이아웃` 축이라 `port` 로 (`Bucket_Store.Export` 와 같은 자리).
- `sampler/tasker.py`(이름 붙은 레시피 + `taskers.yaml`)는 산출물이 아니라 **레시피**라 바인더 소유
  (tooling 원칙 `config ↔ data` 분리).

**순서 — 해체 먼저, 이동 나중 (뒤집으면 새 이름을 쓴 옛 구조가 된다).** `mv` 는 집합 보존 연산이라
경계 변경을 표현할 수 없다. 게다가 **컴파일되는 제약**이기도 하다 — `converter/source.py` 가 지금
`from ..process.source import ...` 를 하므로, 계약을 녹이기 전에 폴더만 옮기면 `port → process` 역방향
의존이 생겨 계층이 뒤집힌다.

**1단계 — 경계 확정 (파일 제자리, `mv` 없음)**
- [x] `source`/`sink` 계약 해체 — `process/{source,sink}.py` 삭제. 8개 클래스(`Base_Source`·`Stem_Block`·
      `Base_Sink`·`Meta_block`·`Frame_source`·`Meta_sink`·`Raw_block`/`Raw_source`·`Register_sink`·
      `Staged_block`/`Staged_source`·`Sample_sink`) → **`Stage` + 서브클래스 2개**(`Flow`·`Sample_stage`).
      순회 = `store.Bucket(category)`(범주는 이제 **필드**), resolve/inline_ctx = 자유함수, route = handler
      직접. `Unit.extra` 탈출구 소멸. block→unit 2단은 근거대로 보존(resolve 1회).
- [x] **Convert 가 엔진을 떠났다** — `converter.Ingest` 자유함수(`scan → Save → store.Set`). `Convert_stage`
      삭제. `Pipeline.Convert` 가 직접 호출.
- [x] **배치는 store 소유로** — `Sample_sink._attach_crop`+`Set` → **`Sample_Set.Place(sid, ref, split, crop)`**.
      split *배정*(빌드 정책)은 `Sample_stage` 에 남고, *앉히는 일*(payload write + 범주 등록)만 store 가 든다.
- [x] **stream 유닛의 store 직접 접근 제거** — ctx 에 store 핸들을 **안 넣는다**. `Flow._block_ctx` 가
      `object`(프레임 객체 목록)를 store 에서 seed 하고 `split_objects` 등이 같은 키로 덮어쓴다 —
      입력과 출력이 같은 이름이라 대칭. `order_objects`/`segment` 의 `meta.Find(stem)` 소멸.
- [x] end-to-end 검증 — Convert→Run→전이→Sample→Export 전 구간 통과 (crop 실체화·segment route 포함).
- [ ] `Bucket_Store` 의 handler 지연 import 5개 → top-level (`Data_Ref` 승격 후 = 2단계).

**2단계 — 재배치 (`git mv`, 별도 커밋)**
- [ ] `data/data_ref.py` → `core/schema.py` · `data/` → `core/store/` · `data/handler` + import/export →
      `core/port/` · `converter`/`sampler` 삭제.
- [ ] import 방향 검사 도입 (`schema ← port ← store ← process ← _base`).
- [ ] 각 README·`core/README.md` 디렉토리 트리 정정.

**미해결 — `analysis/` 의 자리.** "해체해서 뿌린다"에 합의. 유력 가설은 **`carry` + `finalize` 로 접힌다**
(순회하며 누산 → 끝나면 1회 결과) — 그러면 계산은 `func/`, 누산은 `stream/` 유닛, report·figure 는 finalize
출력이 되고 `Analysis` 계약이 통째로 소멸한다. **단 검증 안 됨** — `__main__.py`·`batch.py`·`io.py` 의
오프라인 재분석·CLI 경로가 정말 접히는지 코드를 읽어야 한다. 1단계 착수 전에 확인.

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

### stream 유닛의 store 직접 접근 제거  ← 4분할 1단계에 흡수

- [ ] `mask/order.py:33`·`model/segment/_base.py:60` 이 `meta.Find(stem)` 으로 store 를 뒤진다. 유닛의
      일탈이 아니라 `Meta_block.context`(`source.py:126`)가 ctx 에 store 핸들을 넣기 때문 — **source 가
      객체 목록을 ctx 로 resolve** 하도록 계약을 바꿔야 사라진다. (열린 질문: 재실행 시 객체를 어디서
      얻나 — 앞 step 의 ctx `object` vs source resolve.)
      → source 계약을 녹이는 **1단계에서 같이 답한다**(ctx 에 store 핸들을 안 넣는 게 종료 조건).

### Verify

- [ ] `Pipeline.Verify` 를 `staged` 위 Stage 로 구현. **두 종류를 다 소비** — per-stem check(`stream/`,
      `Base_Process` → pass/fail route) + 데이터셋 진단(`analysis/`, report/figure). 현재 `NotImplementedError`.

### 부채

- [ ] **`DEFAULT_RATIOS`(0.8/0.1/0.1)가 한 번도 적용되지 않는다** — `Pipeline.Sample` 이
      `ratios=_cfg.get("ratios") or {}` 로 **빈 dict 를 명시 전달**해서 dataclass 기본값이 늘 덮인다.
      `_norm_ratios({})` → 합 0 → **균등 1/3** 이 된다(레시피에 `ratios` 가 없으면 항상). 1단계 검증에서
      3 stem → train 0 / val 2 / test 4 로 관측. **리팩터 이전부터 그랬다** — 동작 보존을 위해 그대로 뒀다.
      고치려면 split 배정이 바뀌므로(기존 tasker 재빌드 시 데이터가 이동) 의도적 결정이 필요하다.
- [ ] **`analysis/chroma` 의 vestigial `window`** — 옛 mode-window 추정기의 잔재. `Robust_mean_std` 는
      받지 않는데 `stats.py`·`analyze.py`·`_result.py` 가 여전히 인자로 나른다. 호출 크래시는 고쳤으나
      **지금은 조용히 무시된다.** report 까지 걷어내야 한다.
- [ ] **`meta/test_dataset.py`** — `test_meta_merge_*` 가 옛 kwarg(`modified=`/`staged=`)로 `Dataset_Meta`
      생성 → 지금은 `buckets=` 뿐이라 **깨짐**. `buckets=` 로 고치고 3-state(skipped) 반영, 상단 낡은
      namespace stub 제거. **여기에 라이프사이클(Convert→Run→Verify→Gather→학습)을 흡수** — 지금 그 흐름은
      `meta/README.md` 산문으로만 있다(워크플로는 테스트가 소유해야 함). 테스트가 생기면 README 는 가리키기만.
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
- [ ] **id_map 위치** — id_map 은 detection tasker(sample) 소유. gui 쪽 vestigial `Idmap_panel` 스텁은
      이미 소멸했다(2026-07-11 확인 — `gui/meta_page/view` 는 `Params_panel` 만 두고 id_map 을 params 의
      일반 `Data_Ref` 로 읽기전용 표시, class 재배정 후보는 sampler 가 `Pipeline.Id_map()` 로 뽑는다).
      남은 질문은 **소유권**뿐 — 정본 params 에 얹힌 id_map 이 파생(sample) 소유라는 계층과 어긋난다.
      정본을 class **이름**만 들게 두고 id_map 을 tasker 레시피로 내릴지 결정(내리면 gui 표시도 sample 로 이동).
