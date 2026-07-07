# sample

파생(derived) 스테이지 — **staged 정본(`Dataset_Meta`)을 소비해 task별 학습셋으로 파생**한다.
데이터 구조(`Sample_Set`)와 그 영속 + 정본→파생 빌드(`Base_Sampler`)를 소유한다.

`data` 계층의 두 구체 스테이지 중 파생 쪽(정본은 [`../meta`](../meta)). 공유 컨테이너·leaf 는
[`../schema.py`](../schema.py), payload I/O 는 [`../handler`](../handler).

---

## 핵심 — task 마다 sample 구조가 다르다 (그런데 스키마는 그대로)

목표는 staged 데이터를 **train/val/test** 로 가르는 것인데, 그 안의 구성은 **task 마다 다르다**:

- **classification** — class 이름 폴더에 입력을 넣는 style. `{split}/{class}/{sample}` — meta 보다 **한
  계층 더** 깊다.
- **COCO detection** — `{split}/{image}/{object}` + split 별 `instances_{split}.json` 집계. meta 처럼
  image→object 2단(계층 안 늘어남).

이 depth 차이를 **flat `Data_Ref` 스키마가 공짜로 흡수**한다 — `Bucket_Store` 항목(범주 직속)은
`type="stem"` `Data_Ref` 라 임의 깊이로 중첩되고, 사이드카 영속(`Scatter`/`Load`)이 그 중첩을 재귀
직렬화로 그대로 담는다. 그래서 **`Sample_Set` 은 depth 를 모르고**, task 별로 변하는 건 딱 둘뿐이다:

| 변하는 것 | 소유 | meta 대칭 |
|---|---|---|
| 트리 모양을 어떻게 짓나 | `Base_Sampler.Place` (task 서브클래스) | `converter`(raw→meta) |
| 집계 export (COCO manifest·id_map) | `Base_Sampler.Finalize` | `process` finalize |

---

## 구성

```text
sample/
├── _base.py                 Sample_Set(Bucket_Store) + Base_Sampler(ABC) — store + 빌더 뼈대
├── classification/folder.py Classification_Sampler (ImageFolder style)
├── detection/coco.py        Detection_Sampler (COCO style)
└── __init__.py              SAMPLERS 팩토리 맵 (object_type → sampler 클래스)
```

**task = 서브패키지 / style = 파일** — 한 task 에 여러 포맷이 생기면 파일로 늘린다(detection 에
`yolo.py`·`voc.py`, classification 에 csv-manifest 등). `converter`(`_base.py`+`discover/glob.py`)·
`process`(카테고리 폴더+파일) 관례와 같은 결.

---

## Sample_Set — split 범주만 고정 (depth-agnostic)

`Bucket_Store`(forest 파사드)를 상속해 **범주(`CATEGORIES`) = split** 만 고정한다.

```python
class Sample_Set(Bucket_Store):
    CATEGORIES = SPLITS               # ("train", "val", "test")
    TOP_STEM   = "sample_set"
```

- root 규약 = `{dataset_root}/samples` (정본 root 아래 파생 서브트리, `SAMPLE_DIR`).
- 한 split 버킷(`categories[split]`)의 **항목 key 가 무엇인지는 task 가 정한다** — classification 은
  class(그 안에 sample 중첩), detection 은 image(그 안에 object 중첩). `Sample_Set` 은 그 의미를 모른다.
- 영속(`Scatter`/`Save_item`/`Load`)·전이·번들(`Gather`)은 전부 `Bucket_Store` 상속 — 정본과 **완전히
  같은 per-item 사이드카 메커니즘**이라 sample 전용 영속 코드가 없다. 사이드카 단위 = 범주(split) 직속
  항목(classification=class 통째 / detection=image 통째).

---

## Base_Sampler — 정본 → Sample_Set 빌드

`Build(meta)` 가 staged 순회·split 배정을 소유하고, **task 서브클래스는 `Place`(+선택적 `Finalize`)만
구현**한다.

```python
class Base_Sampler(ABC):
    ratios: dict[str, float]   # split 비율 (정규화됨)
    salt:   str                # 해시 배정 소금 (재현성 유지한 채 다른 분할)
    unit:   str = "object"     # object | frame — 순회 단위
    def Build(self, meta) -> Sample_Set: ...      # staged 순회 → _assign → Place → Finalize (재생성)
    def Place(self, sset, split, stem, obj_id, ref) -> None: ...   # task: 트리 배치 (abstract)
    def Finalize(self, sset, meta) -> None: ...   # task: 집계 export (기본 no-op)
```

- **A+ (순수 재생성)** — sample leaf 는 payload 실체화가 아니라 정본 `(source_stem, source_obj)`
  **역참조** + `class_id` attr 만 든다(원본 진실은 정본에만). 매 `Build` 가 staged 에서 트리를 새로 짓는다.
- **split 배정은 결정적** — `_assign(stem)` 이 **frame stem 해시**를 `ratios` 누적 구간에 떨군다. 재실행
  안정(배정을 저장 안 해도 재현) + **frame 단위 배정**(같은 image 의 object 가 train/val 로 흩어지는
  leakage 방지). `salt` 로 재현성 유지한 채 다른 분할.

### 구체 sampler

- **`Classification_Sampler`** (`classification/folder.py`) — `Place` 가 class 폴더를 한 계층 더 만든다:
  `categories[split][class][sample_id] = 역참조`. class = 단위의 `class_id`(없으면 `unlabeled`).
- **`Detection_Sampler`** (`detection/coco.py`) — `Place` 가 frame stem 으로 묶어 image→object 2단.
  `Finalize` 가 class→정수 **`id_map`**(정본은 class 이름만, 매핑은 파생 소유)을 `params` 에 짓고 split 별
  COCO manifest(images+annotations)를 `instances_{split}.json` 로 낸다.

---

## Pipeline 단계

`Pipeline` 은 `self.meta`(정본) + `self.sample`(파생)을 함께 들고, 파생을 한 **단계**로 돌린다:

```text
Convert → Run → [staging 전이는 meta] → Sample() → Verify
```

`Pipeline.Sample()` = `_build_sampler(cfg.sample)` → `sampler.Build(staged meta)` → `Sample_Set` 재생성
→ `sample.Scatter()`. config `sample.object_type` 이 task(classification/detection)를 고르고, `ratios`/
`salt`/`unit` 은 sampler 필드로 넘어간다(`_build_sampler` 팩토리, converter 대칭).

---

## 다음 단계

- **crop 실체화** — 지금 sample 은 `(source_stem, source_obj)` 역참조만 든다. `Base_Process` 체인
  (`frame_crop`/`normalize`)을 재사용해 crop 을 `{split}/{class}/{id}`(handler)로 떨궈 sample 에 `crop`
  ref 를 넣는 단계가 남았다.
- **`excluded` 큐레이션** 영속 (A+ = 재생성 + 솎아내기).
- detection COCO manifest 에 bbox/segmentation 채우기(정본 object leaf 에서 추출).
