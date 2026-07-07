# TODO — core (잔여 작업)

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 남은 것만.

flat `Data_Ref` 스키마 마이그레이션은 **core/data(sample 제외)·process·_base·gui 완료** — `import core`
동작, meta 영속/전이·process flow·GUI 전부 flat 기준. 아래는 그 다음.

---

## sample 파생 — 보류 (flat 재설계)

`sample/` 은 아직 옛 `Node` API 기준이라 import 체인에서 빠져 있고 `Pipeline.Sample()` 은
`NotImplementedError`. flat `Data_Ref` 로 재작성 후 복구:

- [ ] **`sample/store.py`·`sampler.py` flat 전환** — `Sample_Set(Bucket_Store)` split→class→sample 을
      stem `Data_Ref`(`info` 중첩)로, `Place`/`Iter_samples`/`Assign`/`Build` 를 `categories`/`info` 기준으로.
- [ ] **`core/_base` 배선 복구** — `_build_sampler` 팩토리·`self.sample`·`Pipeline.Sample()` 되살리기.
- [ ] **id_map 연결** — converter `Load_id_map` 결과를 sample 스테이지가 수용(정본은 class 이름만).
      GUI `Idmap_panel` 연결(현재 빈 dict 스텁).
- [ ] **crop 실체화** — sample sink 가 `Base_Process` 체인(crop/normalize)을 태워 `{split}/{class}/{id}`
      (handler)로 payload 떨구고 sample `info["crop"]` 채움. (지금은 `(stem, obj_id)` 역참조만.)
- [ ] `excluded` 큐레이션 영속 (A+ = 순수 재생성 + 솎아내기).
- [ ] detection/seg task sampler (classification 다음).

## 잔여 정리

- [ ] **`meta/test_dataset.py`** — 4개 테스트(`test_meta_merge_*`)가 옛 kwarg(`modified=`/`staged=`) 사용 →
      `categories=` 로. 파일 상단 `core`/`core.data` namespace stub 은 이제 불필요(sample 만 마이그레이션되면
      제거 가능).
- [ ] **GUI end-to-end 런타임 검증** — 코드·import 는 검증됨. 실제 띄워 Convert→Run→Verify 흐름 확인.

## 외부 계층 재배치

- [ ] `analysis/` → `core/` 흡수 + `Pipeline.Verify` 구현 (Sampling 이후/선택적 — 현재 `NotImplementedError`).
      import 경로·`__main__.py` 포함.
- [ ] **converter 를 `core/data` 밖으로** (선택) — "생산자-scatter" 관점이면 converter 는 data 계층 설비가
      아니라 생산자(handler.Save 위임 + 자기 항목 저장). data 는 표현·영속만, ingest 는 생산자 쪽으로.

## 미구현 기능 (future)

- [ ] coco/yolo 포맷 converter (glob 외 직접 파싱 경로)
- [ ] `process/_base` 데코레이터·라우팅 단위 테스트
- [ ] `model` 키 → `segment_predict_model` 개명 (다른 종류 모델 구성 추가 시)
- [ ] chroma n채널 일반화 (주목적: RGB 대응) — 현재 2채널 고정(명도 버림). `ChromaSpace`
      channels/bins/circular/labels 를 length-n 으로, 누산·통계 키를 per-channel(`c0_acc…`/`mean_c0…`)
      에서 배열값 단일 키(`chroma_acc`/`mean`/`std`)로 재설계(carry/finalize outputs 가 채널 수 무관해짐).
      `chroma_to_rgb` 는 RGB면 역변환 불필요·2크로마면 명도 fill 분기. 기존 config 키 마이그레이션 필요.
