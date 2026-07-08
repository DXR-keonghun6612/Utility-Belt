# TODO — core (잔여 작업)

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 남은 것만.

---

## ▶ 진행 중 — source/sink 표준화 + schema.py 축소

**동기.** `data/schema.py`(`Bucket_Store`, 295줄)가 불어났다. 주 원인은 `process/` 의 source/sink 가
**구현 중심**으로 자라며 `converter`·`sampler` 를 붙일 때마다 "값 → `Data_Ref` 템플릿 → `handler.Save`"
쓰기 로직을 그 자리에서 즉석 재구현했고(표준 부재), sink 들이 store 내부(`Bucket`/`params`/`categories`)를
직접 찔러 `Bucket_Store` 가 저수준 표면을 다 열어줘야 했기 때문.

**진단 — 흩어진 쓰기(write) 로직.**
- Data_Ref 템플릿 생성 5개 지점: `process/sink.py::_data_ref`·`_params_ref`,
  `converter/source.py::_spec_ref`, `sampler/sink/_base.py::_sample_ref`·`_attach_crop`·`_set_param`.
- `attr` 템플릿만 3벌 중복: `_params_ref` 스칼라 분기 · `_set_param` · `schema.Set_attr`.
- `Frame.units` 스켈레톤 중복: `Meta_frame.units` ↔ `Staged_frame.units`(stem 자식→obj 분해 +
  object/frame 분기가 각자 구현, 차이는 ctx 채우기뿐).
- sink 들이 `store.Bucket(X)[k]=…`·`store.params[k]=…` 직접 조작 → 표면 노출.

**결정(합의).** write 프리미티브는 **`data/handler`** 에 둔다(I/O 게이트이자 type/format/dir·inline
판정의 진실원천). **R1(source/sink 표준화) 먼저**, store 표면 압력을 없앤 뒤 **R2(schema.py 분리)** 판단.

### R1 — source/sink 계약 표준화
- [x] **R1a. write 프리미티브** — `handler.Template(spec, value, *, params) -> Data_Ref` +
      `handler.Route(…)` (Template + `Save`) 추가 **완료**. value→type 추론을 중앙 테이블 대신 **각
      핸들러의 `INLINE`/`Claims` 선언**으로 병합(3d pts·mesh 는 파일 하나로 확장; `_STORAGE_CONTEXT`
      하드코딩 폐기). `Meta_sink.route`(`_data_ref`/`_params_ref` 제거)·`sampler/sink/_base`
      (`_attach_crop`·`_set_param`) 배선. 스모크(dispatch 재현 + 파일 왕복) 검증. `converter/source.py::
      _spec_ref` 는 패턴-확장자 추론·raise 가 고유라 유지(파일 template 공유는 R1c 에서 검토).
- [x] **R1b. source `Frame`→`Stem_Block` 정리** **완료** — 배치 클래스를 `Stem_Block`(하나의 stem 공유)
      으로 리네임하고(`Meta_block`/`Staged_block`/`Raw_block`), unit 분해 골격(`units`=자식 obj 추출 +
      object/frame 루프)을 베이스가 소유. 서브클래스는 `_unit`(ctx 채우기)·`_frame_unit`(frame-단위 정책;
      기본=프레임 자신, Meta 만 '첫 객체' override)만. Raw 는 obj 분해 없어 `units` override. `Base_Source.
      frames()`→`blocks()`. 스모크(Meta obj/frame·Staged·Raw 순회) 검증.
- [x] **R1c. store 쓰기 표면 정리** **완료** — sink 이 `store.params[k]=`·`Bucket(cat)[k]=` 로 내부 dict
      를 직접 만지던 걸 **단일 게이트 `Bucket_Store.Set(key, ref, *, category=None, is_param=False)`** 로
      통일(params 쓰기 = 버킷 stem 등록 = "dict 에 ref 삽입"이라 한 메서드). `Meta_sink`·`Register_sink`·
      `Sample_sink._set_param` 배선. 트리 노드 배치(`_stem.info[k]=`)는 sink 고유라 유지.
      **리네임**: 필드 `categories`→`buckets`(ClassVar `CATEGORIES` 와 대소문자만 달라 혼동 → `Bucket()`
      과 짝 맞춤). `Frame`→`Stem_Block` 은 R1b.

### R2 — schema.py 축소 (R1 이후)
- [x] **완료** — 영속(`Restore`/`Scatter`/`Save_item`/`Save_top`/`Drop`/`Gather`) + 전이(`Move`/`Copy`/
      `Delete`/`Merge`/`Merge_conflicts` + `_transit`/`_merge_ref`)를 신규 **`data/store_io.py` 자유함수**로
      분리(방식: 위임 없이 `store_io.Move(store, …)` — 데이터모델이 I/O 를 아예 모름). `schema.py` 는
      forest 파사드(`params`/`buckets`/`CATEGORIES`) + 범주 편의 + 순회(`Iter_*`/`_iter_leaves`) + `Attr`/
      `Set_attr`만. `_base.py`(`Restore`/`Scatter`) 배선 + 왕복 스모크 검증. core 문서 정합.
- [x] **gui/* store_io 배선** **완료** — `page/_main`(`Move`/`Delete`/`Gather`/`Restore`/`Merge_conflicts`/
      `Merge`)·`meta_view/_view`(`Save_item`/`Save_top`)·`sampler/_viewer`(`Save_item`/`Drop`)의 인스턴스
      호출을 `store_io.X(store, …)` 자유함수로 전환(+`from core.data import store_io`). gui/README 문구 정합.
      process/converter/sampler 리팩은 `Pipeline` 파사드 아래 갇혀 gui 코드 변경 불필요(직접 import 3곳
      `PROCESS_REGISTRY`/`log_edges`/`MODEL_BUILDERS` 전부 유지). **store_io.py: `Move`/`Copy` → 공유
      `_transfer(keep=…)` 병합.**
- [ ] **`test_dataset.py` 정리** — store_io 배선(`Scatter`/`Restore`/`Move`/`Delete`/`Merge*` 인스턴스 호출)
      **에 더해** 더 깊은 낡음까지: 생성자 `Dataset_Meta(modified={…}, staged={…})` 가 이제 무효(kwarg 아님
      → `buckets={…}`), 헤더 NOTE(구 sample eager-import stub)도 폐물. [[정리/검증]] 항목과 병합.

### Verify (R1 이후 — 거의 공짜)
- [ ] `Pipeline.Verify` 를 `staged` 위 Stage 로 구현(check process 체인 + 결과 params route).
      `analysis/` 흡수와 함께(아래 "외부 계층 재배치").

---

## 논의 필요 (미구현 — 재정리 대상)

- [ ] **재-convert 덮어쓰기/교차상태 중복** — `Register_sink` 가 무검사로 modified 에 등록 →
      기존 modified 덮어씀 + staged/skipped 인 stem 도 modified 에 재등록(one-stem-one-state 위반).
      **합의된 정책 없음.** 이 영역(R1c store 쓰기 표면) 재정리 후 구현. 상세
      [`converter/README.md`](converter/README.md) "⚠ 논의 필요".

## sampler / 파생

- [ ] **id_map 위치 정리** — id_map 은 detection tasker(sample) 소유(`Detection_sink.Finalize` → sample
      params). 그런데 `gui/meta_view` 는 아직 `Idmap_panel` 을 들고 빈 `{}` 를 로드하는 **vestigial 스텁**
      (`_view.py:99`). meta view 에서 제거하고 sampler 뷰어(detection tasker)로 옮길지 결정.
- [ ] `excluded` 큐레이션 영속 (A+ = 순수 재생성 + 솎아내기).
- [ ] detection COCO manifest 에 bbox/segmentation 채우기 + detection crop/class 재배정 GUI
      (뷰어는 현재 classification 편집만).

## 정리 / 검증

- [ ] **`meta/test_dataset.py`** — `test_meta_merge_*` 등이 옛 kwarg(`modified=`/`staged=`)로 `Dataset_Meta`
      를 생성 → 지금은 필드가 `buckets=` 뿐이라 **현재 깨짐**. `buckets=` 로 고치고 3-state(skipped)
      반영. 파일 상단 `core`/`core.data` namespace stub 도 이제 불필요(제거 검토).
- [ ] **GUI end-to-end 런타임 검증** — 코드·import·offscreen 은 검증됨. 실제 데스크톱에서 띄워
      Convert→Run→전이→Sample→뷰어 흐름 확인.

## 외부 계층 재배치

- [ ] `analysis/` → `core/` 흡수 + `Pipeline.Verify` 구현 (Sampling 이후/선택적 — 현재 `NotImplementedError`).
      `analysis/` 는 `_base.py`·`chroma/`·`mask/` + `temp_crop_mask.py`·`temp_shape_embed.py`·
      `temp_split_train_val.py`(임시 스크립트). (`__main__.py` 는 이미 삭제됨.)

## 미구현 기능 (future)

- [ ] coco/yolo 포맷 converter (glob 외 직접 파싱 경로)
- [ ] `process/_base` 데코레이터·라우팅 단위 테스트
- [ ] `model` 키 → `segment_predict_model` 개명 (다른 종류 모델 구성 추가 시)
- [ ] chroma n채널 일반화 (주목적: RGB 대응) — 현재 2채널 고정(명도 버림). `ChromaSpace`
      channels/bins/circular/labels 를 length-n 으로, 누산·통계 키를 per-channel(`c0_acc…`/`mean_c0…`)
      에서 배열값 단일 키(`chroma_acc`/`mean`/`std`)로 재설계(carry/finalize outputs 가 채널 수 무관해짐).
      `chroma_to_rgb` 는 RGB면 역변환 불필요·2크로마면 명도 fill 분기. 기존 config 키 마이그레이션 필요.
</content>
</invoke>
