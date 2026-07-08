# sample (store)

파생(derived) 스테이지의 **데이터 구조·영속**만 소유한다 — `Sample_Set`(`Bucket_Store`, 범주 = split).
정본→파생 **빌드는 [`../../sampler`](../../sampler)** 가 한다(meta store↔converter 대칭으로 sample
store↔sampler). 공유 컨테이너·leaf 는 [`../schema.py`](../schema.py), payload I/O 는 [`../handler`](../handler).

---

## Sample_Set — split 범주만 고정 (depth-agnostic)

`Bucket_Store`(forest 파사드)를 상속해 **범주(`CATEGORIES`) = split** 만 고정한다.

```python
class Sample_Set(Bucket_Store):
    CATEGORIES = SPLITS               # ("train", "val", "test")
    TOP_STEM   = "sample_set"
```

- root 규약 = `{dataset_root}/sample/{tasker}` (정본 root 아래 파생 서브트리, `SAMPLE_DIR`="sample").
  tasker(이름 붙은 파생) 목록·설정은 `{dataset_root}/sample/taskers.yaml` — 빌드·조율은 [`../../sampler`](../../sampler).
- 한 split 버킷(`buckets[split]`)의 **항목 key 가 무엇인지는 task(sampler)가 정한다** —
  classification 은 class(그 안에 sample 중첩), detection 은 image(그 안에 object 중첩). `Sample_Set`
  은 그 의미를 모른다 — split 안의 트리 모양은 `Data_Ref` stem 중첩이 임의 depth 로 흡수한다.
- 영속(`Scatter`/`Save_item`/`Load`)·전이·번들(`Gather`)은 전부 `Bucket_Store` 상속 — 정본과 **완전히
  같은 per-item 사이드카 메커니즘**이라 sample 전용 영속 코드가 없다. 사이드카 단위 = 범주(split) 직속
  항목(classification=class 통째 / detection=image 통째).

---

## 구성

```text
sample/
├── _base.py    Sample_Set(Bucket_Store) + SAMPLE_DIR·SPLITS (store 규약 상수)
└── __init__.py
```

빌드(누가 이 트리를 채우나)는 여기 없다 — [`../../sampler`](../../sampler)의 `Sample_sink[task]` 가
`process` Stage 엔진으로 staged 정본을 순회하며 배치한다. leaf 는 **A+ 역참조**(`source_stem`/`source_obj`)
가 기본이고, crop 체인을 끼우면 crop payload(`{split}/{dir}/{id}.png`)를 **실체화**해 `info["crop"]` 에
단다(재생성 가능한 파생 — class 등 정본 attr 은 여기서 안 씀).
