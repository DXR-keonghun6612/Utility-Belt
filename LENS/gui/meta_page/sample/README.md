# gui/meta_page/sample

파생 **tasker** 탭 창 — tasker 마다 탭 한 칸. 정본(staged `Dataset_Meta`)에서 이름 붙은 학습셋을 빌드하고
(Converter 창이 raw→meta 를 자체 실행하는 패턴과 대칭), 그 결과를 트리+미리보기로 보며 class 를 재배정
(정본 write-back)한다. split(train/val/test)은 편집엔 안 나오고 **내보내기(`▶ split 처리`)** 가 가른다. core
sample tasker 계층 위에서 동작 — 설계는 [`../../../core/sampler/README.md`](../../../core/sampler/README.md).

---

## 구성

```text
sample/
├── _dialog.py       Sampler_dialog — QTabWidget 컨테이너 (탭=tasker, 코너 + 추가 · 탭 x 제거)
├── _tab.py          Tasker_tab     — 툴바(프로필 편집·▶ sample·▶ split 처리) + 임베드 Sample_view
├── _profile.py      Tasker_profile_dialog — 레시피 빌더(task/unit/ratios/salt/processes, 편집 전용)
└── _sample_view.py  Sample_view    — group→sample 트리 + crop 미리보기 + class 재배정(write-back)
```

- **`Sampler_dialog`**(비모달) — `QTabWidget` 컨테이너. 탭바 코너 `+`(`_on_new` — 이름 입력 → 빈 탭)·탭 `x`
  (`Delete_tasker`, 확인). tasker 가 0개면 QTabWidget 이 빈 화면이 되므로 안내 placeholder 로 전환하고,
  하단에도 항상 보이는 `새 tasker` 버튼을 둔다. 목록은 `Pipeline.List_taskers()`(레시피 ∪ 폴더)로 복원.
- **`Tasker_tab`** — tasker 한 개. **레시피(cfg)를 보유**하고 `프로필 편집` 이 `Tasker_profile_dialog` 로
  편집한다(빌더 ↔ 실행 분리 — `run` 갈래와 동형). `▶ sample` = `Pipeline.Sample(name, cfg)` 백그라운드
  빌드(탭별 상태 라벨), `▶ split 처리` = `Pipeline.Export_tasker(name, dest)` 로 train/val/test 실체화.
  무거운 작업은 워커 스레드 + 실행 중 툴바·편집 잠금(`Pipeline_worker`). 이후 **분석 호출 버튼**을 더할 자리.
- **`Tasker_profile_dialog`** — sample 레시피(task/unit/ratios/salt + 실체화 체인)만 편집(`run` 의
  `Run_dialog` 대응). tasker 이름은 탭이 소유하므로 레시피 cfg 엔 없다. 레시피 저장/불러오기 소유.
- **`Sample_view`**(임베드) — `Pipeline.Load_sample(name)` 트리. 작업 store 는 split 없는 단일 버킷이라
  트리는 2단(classification=class→sample, detection=image→object). sample 선택 시 **crop payload(있으면)**
  또는 **정본 프레임 역참조**(`source_stem`→meta, `verify/_overlay` 재사용)로 미리보기.

---

## class 재배정 = 정본 write-back + 부분 재파생

sample 은 정본의 **투영**이라, 뷰의 class 편집은 실제로 **정본 obj 의 `class_id`(인라인 attr)를 고치는
것**이다([[project_sample_tasker_layer]]):

1. `source_stem`/`source_obj` 역참조로 정본 obj 를 찾아 `Set_attr(obj, "class_id", new)` + `store_io.Save_item(meta, …)`.
2. 그 sample 하나만 새 class 폴더로 이동 — crop 픽셀은 class 와 무관하니 **재-crop 없이 파일만 이동**
   (`handler` load→새 dir save→옛 삭제) + class 사이드카 증분 저장. 전체 tasker 재빌드 없음(부분 재파생).

geometry(mask/segment)는 여기서 안 건드린다(`gui/meta_page/verify` 의 `Stem_editor` 소유). "학습셋에서
빼기"(exclude)는 정본 write-back 이 아니라 sample-local 큐레이션 — 별개(미구현). `meta_changed` 시그널을
탭→컨테이너→메인으로 forward 해 메인 meta 뷰를 갱신한다.

## split 은 편집이 아니라 내보내기

train/val/test 는 파생(frame stem 해시)이라 편집 트리엔 없고, `▶ split 처리`(=`Export_tasker`)가 레시피의
`ratios`/`salt` 로 갈라 `{dest}/{name}/{split}/…` 로 실체화한다(classification=ImageFolder, detection=+COCO
manifest·id_map). 분석·재배정을 다 끝낸 뒤 마지막에 부르는 단계다.

메인 진입은 `app/_main.py` 의 `Sampler…` 버튼(비모달, `get_pipeline` 주입).
