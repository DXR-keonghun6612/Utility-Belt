# sampler

staged 정본(`Dataset_Meta`)을 소비해 **task별 학습셋(`Sample_Set`)을 빌드**하는 스테이지 — `process` 의
Stage 엔진 위에서 `Staged_source`(순회) → `Sample_sink[task]`(트리 배치)를 잇는다. Run/Convert 와 **같은
엔진, 다른 source/sink** 다(`Sample = Stage(Staged_source, [], Sample_sink[task])`).

store(`Sample_Set`)는 [`../data/sample`](../data/sample)이 소유한다 — meta store↔converter 대칭으로
sample store↔sampler. 엔진·계약은 [`../process/README.md`](../process/README.md)(Stage·Source·Sink).

---

## 핵심 — task 마다 sample 구조가 다르다 (sink 가 짓는다)

목표는 staged 를 **train/val/test** 로 가르는 것인데, split 안의 구성은 task 마다 다르다:

- **classification** — `{split}/{class}/{sample}` (class 가 폴더 계층 — meta 보다 한 계층 더)
- **COCO detection** — `{split}/{image}/{object}` + split 별 `instances_{split}.json`

이 depth 차이를 flat `Data_Ref` 가 흡수하고(stem 임의 중첩), **task 별로 변하는 건 sink 뿐**이다 —
트리 배치(`Place`)와 집계 export(`Finalize`). 순회·split 배정은 `Sample_sink` 베이스가 소유한다.

---

## 구조

```text
sampler/
├── source.py      Staged_source — staged 순회 (A+ 역참조 / materialize=crop resolve 두 모드)
├── stage.py       Sample_stage(Stage) — Staged_source + Sample_sink[task] 조립
├── tasker.py      tasker 레지스트리 — {root}/sample/taskers.yaml (name → sample config)
├── sink/
│   ├── _base.py         Sample_sink — split 결정적 배정 + 역참조(_sample_ref) + _attach_crop + Place/Finalize
│   ├── classification.py Classification_sink — {split}/{class}/{sample}
│   └── detection.py      Detection_sink — {split}/{image}/{object} + COCO manifest + id_map
└── __init__.py
```

**tasker (이름 붙은 파생)** — 한 tasker = 이름 + sample 설정. 산출물(`Sample_Set`)은 `{root}/sample/{name}/`,
이름↔설정 매칭은 `taskers.yaml`(`Load_taskers`/`Save_taskers`). 조율은 `Pipeline`(`Taskers`/`Sample(name,
cfg)`/`Load_sample`/`Delete_tasker`) — store↔recipe 분리는 converter/flow 와 동형.

**task = sink 파일** — 새 task/포맷은 `sink/` 에 파일로 추가하고 `SAMPLE_SINKS` 에 등록한다.

---

## Staged_source / Sample_sink

- **`Staged_source`** — staged 버킷을 `unit`(object/frame)으로 순회. 두 모드: **A+(기본)** = payload
  resolve 없이 정본 ref + inline attr 만 sink 로(순수 역참조); **materialize** = 프레임 leaf(base image·
  `segment`)를 resolve + obj mask(`segment==obj_id+1`)를 파생해 crop 체인 입력으로 올린다. `Sample_stage`
  가 `processes`(crop 체인)가 있으면 materialize 를 켠다.
- **`Sample_sink`**(베이스) — unit 당 `emit`: **split 을 frame stem 해시로 결정적 배정**(재실행 안정,
  leakage 방지 — 같은 image 는 한 split) → `Place`. `close` → `Finalize`. leaf 는 payload 가 아니라
  정본 `(source_stem, source_obj)` 역참조 + `class_id` attr(`_sample_ref`). source-store(meta) ≠
  sink-store(`target` = `Sample_Set`).
- **`Classification_sink`** — class = unit 의 `class_id`(없으면 `unlabeled`), `{split}/{class}/{sample}`.
- **`Detection_sink`** — frame stem 으로 묶어 image→object 2단, `Finalize` 가 class→정수 `id_map`(정본은
  이름만) + split 별 COCO manifest(images+annotations).

---

## Pipeline 단계

`Pipeline.Sample` = `Sample_Set` 새로 만들어 `Sample_stage(task=…, ratios=…, target=sset)(meta)` 구동 →
`sset.Scatter()`. config `sample.task` 가 sink 를, `ratios`/`salt`/`unit` 이 배정·순회를 정한다.

```text
Convert → Run → [staging 전이는 meta] → Sample → Verify
```

## crop 실체화 (완료)

`Sample_stage.processes` 에 crop 체인(`frame_crop`)을 끼우면 materialize source 가 프레임+obj mask 를
resolve → `Frame_crop(frame, mask)→crop` → `Sample_sink._attach_crop` 이 `{split}/{dir}/{sample_id}.png`
(handler)로 payload 를 떨구고 sample `info["crop"]` 에 leaf 를 단다(Run 과 같은 엔진). crop=파생(재생성)
이라 정본으로 write-back 하지 않는다 — class 등 attr 만 정본이 소유([[project_sample_tasker_layer]]).

## 다음 단계

- `excluded` 큐레이션 영속 (A+ = 재생성 + 솎아내기).
- detection COCO manifest 에 bbox/segmentation 채우기 (정본 object leaf 에서 추출).
- detection crop layout(`{split}/{image}/{object}`)·class 재배정 GUI (현재 뷰어는 classification 편집만).
