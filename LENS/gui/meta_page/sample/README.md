# gui/meta_page/sample

파생 **tasker** 탭 창 — tasker 마다 탭 한 칸. 정본(staged `Dataset_Meta`)에서 이름 붙은 학습셋을 빌드하고
(Converter 창이 raw→meta 를 자체 실행하는 패턴과 대칭), 그 결과를 트리+미리보기로 보며 class 를 재배정
(정본 write-back)한다. split(train/val/test)은 편집엔 안 나오고 **내보내기(`▶ split 처리`)** 가 가른다. core
파생(sample) 계층 위에서 동작 — 설계는 [`../../../core/store/README.md`](../../../core/store/README.md)
(빌드는 `core/process/sample.py`, 내보내기는 `core/store/sample/export/`).

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
- **`Sample_view`**(임베드) — `Pipeline.Load_sample(name)` 트리. store 의 범주는 **split** 이고 sample 이
  곧 item 이다. **class 는 구조가 아니라 attr** 이라 트리의 class 그룹은 **표시용 group-by** 일 뿐이다
  (split 은 컬럼). sample 선택 시 **crop payload(있으면)** 또는 **정본 프레임 역참조**(`source_stem`→meta,
  `edit/_overlay` 재사용)로 미리보기.

---

## class 재배정 = attr 갱신 두 줄 (파일이 안 움직인다)

sample 은 정본의 **투영**이라, 뷰의 class 편집은 실제로 **정본 obj 의 `class_id`(인라인 attr)를 고치는
것**이다:

1. `source_stem`/`source_obj` 역참조로 정본 obj 를 찾아 `Set_attr("class_id", new)` + `meta.Save(stem)`.
2. 파생 sample 의 `class_id` attr 도 갱신 + `sset.Save(sid)` (그 sample 사이드카만, 증분).

**끝이다.** class 가 경로에 안 들어가므로(attr) **crop 파일이 안 움직인다** — 옛 모델은 class 가 폴더라
재배정이 crop 재저장 + 옛 파일 삭제 + 노드 이동 + 사이드카 2개 rewrite 였다. split 도 안 바뀐다(빌드가
정한 데이터셋 정체성이라 class 와 독립).

geometry(mask/segment)는 여기서 안 건드린다(`gui/meta_page/edit` 의 `Stem_editor` 소유). "학습셋에서
빼기"(exclude)는 정본 write-back 이 아니라 sample-local 큐레이션 — 별개(미구현). `meta_changed` 시그널을
탭→컨테이너→메인으로 forward 해 메인 meta 뷰를 갱신한다.

## split 은 편집이 아니라 내보내기

train/val/test 는 파생(frame stem 해시)이라 편집 트리엔 없고, `▶ split 처리`(=`Export_tasker`)가 레시피의
`ratios`/`salt` 로 갈라 `{dest}/{name}/{split}/…` 로 실체화한다(classification=ImageFolder, detection=+COCO
manifest·id_map). 분석·재배정을 다 끝낸 뒤 마지막에 부르는 단계다.

메인 진입은 `app/_main.py` 의 `Sampler…` 버튼(비모달, `get_pipeline` 주입).
