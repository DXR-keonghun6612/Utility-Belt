# converter

raw 데이터를 탐색해 정본(`Dataset_Meta.modified`)에 등록하는 **ingest 스테이지** — `process` 의 Stage
엔진 위에서 `Raw_source`(발견) → `Register_sink`(등록)를 잇는다. Run/Sample 과 **같은 엔진, 다른
source/sink** 다(`Convert = Stage(Raw_source, [], Register_sink)`).

옛 `Base_Converter.Convert(stem_root, params_root)` 계약을 걷어내고, converter 를 `data` 밖 top-level 로
승격했다 — data 는 표현·영속(store)만, ingest 는 계산 계층(생산자)으로. 엔진·계약은
[`../process/README.md`](../process/README.md)(Stage·Source·Sink), payload I/O 는
[`../data/handler`](../data/handler).

---

## 구조

```text
converter/
├── source.py   Raw_source — glob 발견(폴더의 흩어진 파일 → stem 그룹) + Raw_block
├── sink.py     Register_sink — 그룹을 handler.Save 하고 stem Data_Ref 를 modified 에 등록
├── stage.py    Convert_stage(Stage) — Raw_source + Register_sink 조립
└── __init__.py
```

- **`Raw_source`** — `Base_Source` 구현. `sources`/`globs`/`params` 로 raw 를 발견해 `Raw_block`(파일
  경로 + ref 템플릿)을 낸다. 실제 저장은 안 하고 **발견·템플릿**만 정한다. 정해진 포맷 파서(coco/yolo)는
  다른 Source 로 이 패키지에 파일로 추가.
- **`Register_sink`** — `Base_Sink` 구현. 체인이 비므로 unit 당 1회 `emit` 에서 구조를 만든다:
  `target="frame"` → stem `Data_Ref` 를 `modified` 버킷에, `target="params"` → root leaf 를
  `store.params` 에 (둘 다 payload 는 `handler.Save`).
- **`Convert_stage`** — `Pipeline.Convert` 가 config `sources`/`globs`/`params` 로 빌드해 meta 위에서 구동.

---

## Raw_source (glob 발견)

glob 패턴으로 raw 파일을 탐색해 stem 그룹으로 묶는다. glob key 마다 처리 `type` 을 선언한다(key 이름 =
데이터 이름). `type` 생략 시 패턴 확장자로 핸들러를 추론(`handler.Infer_type`); 추론 안 되는 확장자(txt
등)는 명시.

```yaml
converter:
  sources: [/data/raw]
  globs:
    frame:    {pattern: "*_pose.png"}                          # type 생략 → 확장자 추론(png→image)
    class_id: {pattern: "*_pose.txt", type: attr}              # txt 추론 안 됨 → type 명시
    mask:     {pattern: "*_mask.png", type: image, dir: raw_mask}  # dir 오버라이드
  params:
    roi: {pattern: /…/roi.png}                                 # dir 생략 → params
```

### 처리 흐름 (`Stage(Raw_source, [], Register_sink)`)

1. `Raw_source._scan()` → `{stem: {name: path}}` (모든 key 매칭 = inner join, stem 은 `_extract_stem`)
2. stem 마다 `Raw_block`(파일 + ref 템플릿, `target="frame"`) — params 는 dataset-wide 한 그룹(`target="params"`)
3. `Register_sink.emit` 가 각 그룹을 `handler.Save`(image=복사·attr=내용 인라인·rle=인코딩) 후 stem
   `Data_Ref` 를 modified 에 (params 는 root leaf 로)

key별 `type` → 핸들러 디스패치라 라벨 특수처리가 없다 — 라벨이 여러 개든 다른 종류(rle·array)든 동일 규칙.

---

## 확장

```python
# 새 발견 전략 (폴더 스캔) 또는 포맷 파서 — 새 Source 를 파일로 추가
class Coco_source(Base_Source):        # converter/coco.py
    def blocks(self, store): ...       # COCO json 파싱 → Raw_block

# raw→정본 변환이 필요하면 Convert_stage 의 processes 체인에 Base_Process 를 끼운다 (Run 과 같은 엔진).
```

---

## ⚠ 논의 필요 — 재-convert 시 덮어쓰기/중복 (미구현)

현재 `Register_sink.emit` 은 **아무 확인 없이** `store.Bucket(MODIFIED)[stem] = …` 로 무조건 등록한다.
두 가지 문제:

1. **modified 기존 stem 을 조용히 덮어씀** — payload(`handler.Save`)·구조를 갈아엎어 flow 로 만든
   mask/segment 까지 raw 로 초기화.
2. **교차상태 미검사(버그)** — `Category_of(stem)` 를 안 봐서, 이미 `staged`(검수)·`skipped`(보류)인
   stem 을 재-convert 하면 **modified 에도 등록** → 한 stem 이 두 버킷에(one-stem-one-state 위반).

**합의된 정책(구현 대기):** staged·skipped 는 **건너뜀**(검수·보류 보호), modified 는 덮어씀(작업본 갱신),
없으면 신규 추가. 완료 후 "건너뜀 N개" 안내. 단 이 영역은 전체적으로 재정리가 필요해 **논의 대상**으로
남긴다(현재는 무검사 상태 — 재-convert 시 위 위험 유효). 잔여: [`../TODO.md`](../TODO.md).
