# gui/meta_page/sample

파생 **tasker** 빌더 창 + tasker별 **sample 뷰어**. 정본(staged `Dataset_Meta`)에서 이름 붙은 학습셋을
빌드하고(Converter 창이 raw→meta 를 자체 실행하는 패턴과 대칭), 그 결과를 트리+미리보기로 보며 class 를
재배정(정본 write-back)한다. core sample tasker 계층 위에서 동작 — 설계는
[`../../../core/sampler/README.md`](../../../core/sampler/README.md).

---

## 구성

```text
sampler/
├── _dialog.py   Sampler_dialog — tasker 목록 + 설정 폼(task/unit/ratios/salt/crop) + ▶ sample 실행
└── _viewer.py   Sample_viewer — split→class→sample 트리 + crop 미리보기 + class 재배정(write-back)
```

- **`Sampler_dialog`**(비모달) — 왼쪽 tasker 목록(`Pipeline.Taskers()`), 오른쪽 설정 폼. `▶ sample` 이
  `Pipeline.Sample(name, cfg)` 를 `Pipeline_worker` 로 백그라운드 실행한다. crop 체크 → `processes:
  [frame_crop]`(crop 실체화). `삭제` = `Pipeline.Delete_tasker`. 목록 더블클릭·`뷰어 열기` → `view_requested`.
- **`Sample_viewer`**(비모달, tasker당) — `Pipeline.Load_sample(name)` 트리. sample 선택 시 **crop payload
  (있으면)** 또는 **정본 프레임 역참조**(`source_stem`→meta, `gui/meta_page/verify/_overlay` 재사용)로 미리보기.

---

## class 재배정 = 정본 write-back + 부분 재파생

sample 은 정본의 **투영**이라, 뷰어의 class 편집은 실제로 **정본 obj 의 `class_id`(인라인 attr)를 고치는
것**이다([[project_sample_tasker_layer]]):

1. `source_stem`/`source_obj` 역참조로 정본 obj 를 찾아 `Set_attr(obj, "class_id", new)` + `store_io.Save_item(meta, …)`.
2. 그 sample 하나만 새 class 폴더로 이동 — crop 픽셀은 class 와 무관하니 **재-crop 없이 파일만 이동**
   (`handler` load→새 dir save→옛 삭제) + class 사이드카 증분 저장. 전체 tasker 재빌드 없음(부분 재파생).

geometry(mask/segment)는 여기서 안 건드린다(`gui/meta_page/verify` 의 `Stem_editor` 소유). "학습셋에서 빼기"(exclude)
는 정본 write-back 이 아니라 sample-local 큐레이션 — 별개(미구현). `meta_changed` 시그널로 메인 meta 뷰를 갱신.

메인 진입은 `page/_main.py` 의 `Sampler…` 버튼(비모달, `get_pipeline` 주입).
