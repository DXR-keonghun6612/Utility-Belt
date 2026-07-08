# TODO — core (잔여 작업)

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 남은 것만.

---

## 논의 필요 (미구현 — 재정리 대상)

- [ ] **재-convert 덮어쓰기/교차상태 중복** — `Register_sink` 가 무검사로 modified 에 등록 →
      기존 modified 덮어씀 + staged/skipped 인 stem 도 modified 에 재등록(one-stem-one-state 위반).
      합의 정책: 정해진게 없음. **이 영역 전체 재정리 후 구현**
      (현재 무검사). 상세 [`converter/README.md`](converter/README.md) "⚠ 논의 필요".

## sampler / 파생

- [ ] **id_map 위치 정리** — id_map 은 detection tasker(sample) 소유(`Detection_sink.Finalize` → sample
      params). 그런데 `gui/meta_view` 는 아직 `Idmap_panel` 을 들고 빈 `{}` 를 로드하는 **vestigial 스텁**
      (`_view.py:99`). meta view 에서 제거하고 sampler 뷰어(detection tasker)로 옮길지 결정.
- [ ] `excluded` 큐레이션 영속 (A+ = 순수 재생성 + 솎아내기).
- [ ] detection COCO manifest 에 bbox/segmentation 채우기 + detection crop/class 재배정 GUI
      (뷰어는 현재 classification 편집만).

## 정리 / 검증

- [ ] **`meta/test_dataset.py`** — `test_meta_merge_*` 등이 옛 kwarg(`modified=`/`staged=`)로 `Dataset_Meta`
      를 생성 → 지금은 필드가 `categories=` 뿐이라 **현재 깨짐**. `categories=` 로 고치고 3-state(skipped)
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
